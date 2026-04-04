import io
import time
from threading import Condition
from http import server
from picamera2 import Picamera2

# ==========================================
# CONFIGURATION
# ==========================================
STREAM_TO_LAPTOP = True
STREAM_TO_SDR = False
PORT = 8000


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):  # New JPEG frame
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                print(f"Client disconnected: {e}")


class StreamingServer(server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


# Global instances
picam2 = Picamera2()
output = StreamingOutput()


def main():
    # In version 0.3.34, use the default request and modify the dictionary
    config = picam2.create_video_configuration()

    # Manually set the parameters in the 'main' stream
    config["main"]["size"] = (1280, 720)
    config["main"]["format"] = "YUV420"  # Stay in YUV for the ISP

    # Set FPS via FrameDurationLimits (most stable for 0.3.x)
    config["controls"]["FrameDurationLimits"] = (33333, 33333)

    picam2.configure(config)

    if STREAM_TO_LAPTOP:
        # In this version, we pass the format as a positional string if 'format' kwarg fails
        # Or we rely on the Encoder helper:
        print(f"[*] Starting Avionics Stream on port {PORT}...")

        # Try this specific signature for 0.3.34:
        picam2.start_recording(output, format="mjpeg")

        try:
            address = ('', PORT)
            server = StreamingServer(address, StreamingHandler)
            server.serve_forever()
        except KeyboardInterrupt:
            picam2.stop_recording()
            print("\nShutting down...")


if __name__ == "__main__":
    main()