import socket
import time
import cv2
import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

# ==========================================
# MISSION CONFIGURATION FLAGS
# ==========================================
IS_FLIGHT_MODE = False  # TRUE for 30k ft Launch | FALSE for Bench/Ethernet
USE_OVERLAY = True  # TRUE to draw telemetry | FALSE for raw video feed

# Network Settings
GROUND_STATION_IP = "10.42.0.1"
PORT = 10001

if IS_FLIGHT_MODE:
    BITRATE = 800000
    IDR_VAL = 15
else:
    BITRATE = 3000000
    IDR_VAL = 60


# ==========================================

def get_telemetry():
    """Simulated Telemetry for testing"""
    return {
        "alt": 30000, "vel": 1.2, "gps": "32.9904 N, 106.9750 W"
    }


picam2 = Picamera2()


def main():
    # 1. Hardware Config
    # If using overlay, we need RGB888. If not, YUV420 is more efficient for the encoder.
    fmt = "RGB888" if USE_OVERLAY else "YUV420"
    config = picam2.create_video_configuration(main={"size": (1280, 720), "format": fmt})
    picam2.configure(config)
    picam2.start()

    mode_str = "FLIGHT" if IS_FLIGHT_MODE else "BENCH"
    print(f"[*] Starting in {mode_str} MODE (Overlay: {USE_OVERLAY})")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)

    try:
        sock.connect((GROUND_STATION_IP, PORT))
        stream = sock.makefile("wb")

        encoder = H264Encoder(bitrate=BITRATE, iperiod=IDR_VAL)
        encoder.output = FileOutput(stream)
        encoder.start()

        print("[!] VIDEO LINK ACTIVE")

        while True:
            if USE_OVERLAY:
                # 1. Capture the frame into a request object
                request = picam2.capture_request()

                # 2. Get the numpy array from the request to draw on it
                frame = request.make_array("main")

                # --- DRAWING (OpenCV) ---
                data = get_telemetry()
                cv2.rectangle(frame, (0, 670), (1280, 720), (0, 0, 0), -1)
                cv2.putText(frame, f"ALT: {data['alt']}ft", (20, 700),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # 3. Hand the request (with the modified array) to the encoder
                # The encoder.encode method takes the stream and the request
                encoder.encode(picam2.streams["main"], request)

                # 4. Release the request back to the camera system
                picam2.release_request(request)
            else:
                # The high-speed path for no-overlay
                picam2.capture_file("main", encoder)
                time.sleep(0.01)

    except (socket.timeout, ConnectionRefusedError):
        print("[!] ERROR: Ground Station not found.")
    except KeyboardInterrupt:
        print("\n[!] Manual Stop.")
    finally:
        print("[*] Cleaning up...")
        encoder.stop()
        picam2.stop()
        sock.close()


if __name__ == "__main__":
    main()