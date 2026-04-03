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


# ==========================================

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
                print(f"Removed streaming client {self.client_address}: {str(e)}")


class StreamingServer(server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def main():
    # --- Main Logic ---
    picam2 = Picamera2()
    output = StreamingOutput()

    # Create the config object first
    config = picam2.create_video_configuration(main={"size": (1280, 720)})

    # Then update it - this avoids the 'unexpected keyword argument' error
    config.update({"fps": 30})

    picam2.configure(config)

    if STREAM_TO_LAPTOP:
        picam2.start_recording(output, format="mjpeg")

        if STREAM_TO_SDR:
            print("[!] Logic for Pluto+ would go here (e.g. pipe to ffmpeg)")

        try:
            address = ('', PORT)
            server = StreamingServer(address, StreamingHandler)
            print(f"Server started on port {PORT}")
            server.serve_forever()
        except KeyboardInterrupt:
            picam2.stop_recording()
            print("Stopping...")



if __name__ == "__main__":
    main()
