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
        if buf.startswith(b'\xff\xd8'):  # New JPEG frame start
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


# Global instances so the Handler can see them
picam2 = Picamera2()
output = StreamingOutput()


def main():
    # 1. Create a configuration with a 'video' stream for the encoder
    # On Pi 5, MJPEG encoding happens on the 'video' or 'main' stream
    # but must be declared in the request.
    config = picam2.create_video_configuration(
        video={"size": (1280, 720), "format": "MJPEG"}
    )

    # 2. Set FPS
    config.update({"fps": 30})

    # 3. Apply
    picam2.configure(config)

    if STREAM_TO_LAPTOP:
        # Start recording the 'video' stream into our output object
        # We specify 'name="video"' to match the config above
        picam2.start_recording(output, name="video")

        try:
            address = ('', PORT)
            server = StreamingServer(address, StreamingHandler)
            print(f"[*] Avionics Stream Live: http://10.42.0.100:{PORT}")
            server.serve_forever()
        except KeyboardInterrupt:
            picam2.stop_recording()
            print("\nShutting down...")


if __name__ == "__main__":
    main()