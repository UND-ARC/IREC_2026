import socket
import time
import cv2
import numpy as np
import io
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

# ==========================================
# MISSION CONFIGURATION
# ==========================================
IS_FLIGHT_MODE = False  # Set TRUE for 30k ft Launch
USE_OVERLAY = True  # Set TRUE to draw telemetry

GROUND_STATION_IP = "10.42.0.1"
PORT = 10001

if IS_FLIGHT_MODE:
    BITRATE = 800000
    IDR_VAL = 15
else:
    BITRATE = 3000000
    IDR_VAL = 60

MODE_STR = "FLIGHT" if IS_FLIGHT_MODE else "BENCH"


# ==========================================

def get_telemetry():
    """Simulated data for IREC 2026 bench testing"""
    return {"alt": 0, "gps": "32.9904 N, 106.9750 W"}


def main():
    picam2 = Picamera2()

    # 1. Standard Video Configuration
    # We use YUV420 because the H.264 encoder LOVES it.
    # OpenCV can still draw on YUV, just slightly differently.
    config = picam2.create_video_configuration(main={"size": (1280, 720), "format": "YUV420"})
    picam2.configure(config)
    picam2.start()

    print(f"[*] Starting {MODE_STR} MODE (Overlay: {USE_OVERLAY})")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)

    try:
        print(f"[*] Connecting to GS at {GROUND_STATION_IP}...")
        sock.connect((GROUND_STATION_IP, PORT))

        # Use a proper BufferedIOBase wrapper
        socket_file = io.BufferedWriter(sock.makefile("wb", buffering=0))

        # 2. Setup Encoder simply
        encoder = H264Encoder()
        encoder.options = {
            "bitrate": BITRATE,
            "iperiod": IDR_VAL,
            "preset": "ultrafast",
            "tune": "zerolatency"
        }
        encoder.output = FileOutput(socket_file)
        encoder.start()

        print(f"[!] VIDEO LINK ACTIVE")

        while True:
            # 3. Capture a Request (The "Pro" way)
            with picam2.capture_request() as request:
                if USE_OVERLAY:
                    # Capture the YUV array
                    # Note: Drawing on YUV is different, but for a black box
                    # at the bottom, we only need to modify the 'Y' (Luminance) channel.
                    frame = request.make_array("main")

                    # Draw a black rectangle (Value 0 in Y-channel)
                    frame[670:720, :, 0] = 0

                    # Draw text (Value 255 in Y-channel for white text)
                    data = get_telemetry()
                    ov_text = f"ALT: {data['alt']}ft | {MODE_STR} | {time.strftime('%H:%M:%S')}"
                    cv2.putText(frame[:, :, 0], ov_text, (20, 700),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2)

                # 4. Feed the hardware-native request to the encoder
                encoder.encode(picam2.streams["main"], request)
                socket_file.flush()

    except Exception as e:
        print(f"\n[!] ERROR: {e}")
    finally:
        print("[*] Cleaning up...")
        try:
            encoder.stop()
        except:
            pass
        picam2.stop()
        sock.close()


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()