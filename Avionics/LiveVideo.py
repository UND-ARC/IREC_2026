import socket
import time
import cv2
import numpy as np
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

    # Configure Camera
    fmt = "RGB888" if USE_OVERLAY else "YUV420"
    config = picam2.create_video_configuration(main={"size": (1280, 720), "format": fmt})
    picam2.configure(config)
    picam2.start()

    print(f"[*] Starting in {MODE_STR} MODE (Overlay: {USE_OVERLAY})")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)

    try:
        print(f"[*] Connecting to GS at {GROUND_STATION_IP}...")
        sock.connect((GROUND_STATION_IP, PORT))
        # Use unbuffered binary write mode for the socket
        socket_file = sock.makefile("wb", buffering=0)

        # Initialize Encoder for Pi 5 Libav backend
        encoder = H264Encoder()
        encoder.options = {
            "bitrate": BITRATE,
            "iperiod": IDR_VAL,
            "profile": "baseline",
            "preset": "ultrafast",
            "tune": "zerolatency"
        }

        encoder.output = FileOutput(socket_file)
        encoder.start()

        print(f"[!] VIDEO LINK ACTIVE")

        while True:
            if USE_OVERLAY:
                # Capture hardware request and wrap in context manager
                with picam2.capture_request() as request:
                    frame = request.make_array("main")

                    # --- TELEMETRY DRAWING ---
                    data = get_telemetry()
                    cv2.rectangle(frame, (0, 670), (1280, 720), (0, 0, 0), -1)
                    ts = time.strftime("%H:%M:%S")
                    ov_text = f"ALT: {data['alt']}ft | {MODE_STR} | {ts}"
                    cv2.putText(frame, ov_text, (20, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    # Encode the specific stream and request
                    encoder.encode(picam2.streams["main"], request)
            else:
                # Direct capture path
                picam2.capture_file("main", encoder)
                time.sleep(0.01)

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