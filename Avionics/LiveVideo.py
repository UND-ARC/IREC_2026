import io
import time
import socket
from threading import Condition
from http import server
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, H264Encoder
from picamera2.outputs import FileOutput

# ==========================================
# CONFIGURATION
# ==========================================
STREAM_TO_LAPTOP = True  # HTTP MJPEG (Browser)
STREAM_TO_SDR = False  # UDP H.264 (Pluto+/Ground Station)

PORT_HTTP = 8000  # Web port
SDR_IP = "10.42.0.1"  # Destination IP for SDR/Ground Station
SDR_PORT = 10001  # Destination Port


# ==========================================

class StreamingOutput(FileOutput):
    """
    Custom output that holds the most recent JPEG frame in memory
    for the HTTP server to serve to browsers.
    """

    def __init__(self):
        super().__init__()
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        # Check if this buffer contains a JPEG start marker anywhere in the first few bytes
        if b'\xff\xd8' in buf[:20]:
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
                print(f"Browser client disconnected: {e}")


class StreamingServer(server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


# Global instances
picam2 = Picamera2()
output = StreamingOutput()


def main():
    # 1. Hardware Configuration (Pi 5 / IMX708)
    config = picam2.create_video_configuration()
    config["main"]["size"] = (1280, 720)
    config["main"]["format"] = "YUV420"
    config["controls"]["FrameDurationLimits"] = (33333, 33333)  # Lock 30 FPS
    picam2.configure(config)

    active_streams = []

    # 2. Setup Laptop Web Stream (MJPEG)
    if STREAM_TO_LAPTOP:
        print(f"[*] Initializing Web Stream on port {PORT_HTTP}...")
        enc_mjpeg = MJPEGEncoder()
        picam2.start_recording(enc_mjpeg, output)
        active_streams.append("HTTP")

    # 3. Setup SDR Stream (UDP H.264)
    if STREAM_TO_SDR:
        print(f"[*] Initializing SDR UDP Stream to {SDR_IP}:{SDR_PORT}...")
        # Create a raw UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect((SDR_IP, SDR_PORT))

        # Create a file-like object from the socket for Picamera2
        sdr_file_obj = sock.makefile("wb")
        sdr_output = FileOutput(sdr_file_obj)

        # Use H264 for radio efficiency (1Mbps bitrate)
        enc_h264 = H264Encoder(bitrate=1000000)
        picam2.start_recording(enc_h264, sdr_output)
        active_streams.append("SDR/UDP")

    # 4. Start Server or Loop
    if not active_streams:
        print("[!] No streams enabled. Check your flags!")
        return

    try:
        if STREAM_TO_LAPTOP:
            address = ('', PORT_HTTP)
            http_server = StreamingServer(address, StreamingHandler)
            print(f"[*] Avionics Live at http://10.42.0.100:{PORT_HTTP}")
            http_server.serve_forever()
        else:
            # If only SDR is active, just loop to keep script alive
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] Shutting down all streams...")
        picam2.stop_recording()
        if STREAM_TO_SDR:
            sdr_file_obj.close()
            sock.close()


if __name__ == "__main__":
    main()