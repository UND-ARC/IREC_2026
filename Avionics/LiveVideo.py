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

    # We capture in RGB888 for OpenCV, but we will convert to YUV for the encoder
    config = picam2.create_video_configuration(main={"size": (1280, 720), "format": "RGB888"})
    picam2.configure(config)
    picam2.start()

    print(f"[*] Starting in {MODE_STR} MODE (Overlay: {USE_OVERLAY})")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)

    try:
        print(f"[*] Connecting to GS at {GROUND_STATION_IP}...")
        sock.connect((GROUND_STATION_IP, PORT))

        # Use a BufferedIOBase compatible wrapper
        raw_sock = sock.makefile("wb", buffering=0)
        socket_file = io.BufferedWriter(raw_sock)

        # Initialize Encoder - We let it auto-detect format from the first frame
        encoder = H264Encoder()
        encoder.options = {
            "bitrate": BITRATE,
            "iperiod": IDR_VAL,
            "preset": "ultrafast",
            "tune": "zerolatency"
        }
        encoder.output = FileOutput(socket_file)
        # Note: We don't call encoder.start() yet; some versions start on the first frame

        print(f"[!] VIDEO LINK ACTIVE - WAITING FOR FIRST FRAME")

        while True:
            # 1. Capture RGB frame
            frame_rgb = picam2.capture_array("main")

            # --- DRAWING ---
            data = get_telemetry()
            cv2.rectangle(frame_rgb, (0, 670), (1280, 720), (0, 0, 0), -1)
            ts = time.strftime("%H:%M:%S")
            ov_text = f"ALT: {data['alt']}ft | {MODE_STR} | {ts}"
            cv2.putText(frame_rgb, ov_text, (20, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # 2. CONVERT TO YUV420 (This is the magic fix for the "None" error)
            # H.264 hardware/software encoders on Pi prefer YUV420P
            frame_yuv = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2YUV_I420)

            # 3. Start encoder on first frame if not started
            if not encoder.running:
                encoder.start()

            # 4. Encode the YUV data
            encoder.encode_sample(frame_yuv)
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