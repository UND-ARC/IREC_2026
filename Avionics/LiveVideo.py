import socket
import time
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, H264Encoder
from picamera2.outputs import FileOutput

# ==========================================
# CONFIGURATION
# ==========================================
# For testing on your laptop, set this to your laptop's Ethernet IP
LAPTOP_IP = "10.42.0.1"
PORT = 10001
# ==========================================

picam2 = Picamera2()


def main():
    # 1. Hardware Config
    config = picam2.create_video_configuration()
    config["main"]["size"] = (1280, 720)
    config["main"]["format"] = "YUV420"
    config["controls"]["FrameDurationLimits"] = (33333, 33333)
    picam2.configure(config)

    print(f"[*] Connecting to {LAPTOP_IP}:{PORT}...")

    # 2. Create the Network Socket
    # We'll use TCP for this test because it's easier to verify connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((LAPTOP_IP, PORT))
        # Create a file-like object for the Pi to write into
        stream = sock.makefile("wb")

        # 3. Start Recording
        # Using H264 because it's what you'll use for the Pluto+ SDR
        encoder = H264Encoder(bitrate=2000000)
        picam2.start_recording(encoder, FileOutput(stream))

        print("[!] Streaming! Press Ctrl+C to stop.")
        while True:
            time.sleep(1)

    except Exception as e:
        print(f"Connection failed: {e}")
    except KeyboardInterrupt:
        print("\nStopping...")
        picam2.stop_recording()
    finally:
        sock.close()


if __name__ == "__main__":
    main()