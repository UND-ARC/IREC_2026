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

    # Create a blank config and manually inject the stream requirements
    # 'YUV420' is the internal processing format, 'MJPEG' is the external encoder
    config = picam2.create_video_configuration(main={"size": (1280, 720)})

    # Force the format to MJPEG in the configuration object directly
    # This avoids the keyword argument error entirely
    config["main"]["format"] = "MJPEG"
    config.update({"fps": 30})

    picam2.configure(config)

    if STREAM_TO_LAPTOP:
        # On this version, start_recording likely only wants the output object
        # since the format is already locked into the 'config' above
        picam2.start_recording(output)

        try:
            address = ('', PORT)
            server = StreamingServer(address, StreamingHandler)
            print(f"[*] IREC 2026 Avionics Feed: http://10.42.0.100:{PORT}")
            server.serve_forever()
        except KeyboardInterrupt:
            picam2.stop_recording()
            print("\nSafe shutdown complete.")


if __name__ == "__main__":
    main()