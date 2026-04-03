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
    global picam2, output  # Ensure these are accessible to the server
    picam2 = Picamera2()
    output = StreamingOutput()

    # 1. Create a standard video configuration
    # Pi 5 prefers YUV420 or XBGR8888 for the 'main' stream
    config = picam2.create_video_configuration(main={"size": (1280, 720), "format": "YUV420"})

    # 2. Set the FPS using the dictionary update
    config.update({"fps": 30})

    # 3. Apply the config
    picam2.configure(config)

    if STREAM_TO_LAPTOP:
        # We specify the MJPEG format inside start_recording as an ENCODER option
        # This prevents the 'FATAL' error in the ISP pipeline
        picam2.start_recording(output, format="mjpeg")

        try:
            address = ('', PORT)
            server = StreamingServer(address, StreamingHandler)
            print(f"[*] Stream active at http://10.42.0.100:{PORT}")
            server.serve_forever()
        except KeyboardInterrupt:
            picam2.stop_recording()
            print("\nStopping...")



if __name__ == "__main__":
    main()
