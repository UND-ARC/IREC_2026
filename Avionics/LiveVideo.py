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


def main():
    picam2 = Picamera2()

    # RGB888 is required for OpenCV overlay
    fmt = "RGB888" if USE_OVERLAY else "YUV420"
    config = picam2.create_video_configuration(main={"size": (1280, 720), "format": fmt})
    picam2.configure(config)
    picam2.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)

    try:
        sock.connect((GROUND_STATION_IP, PORT))
        stream = sock.makefile("wb")

        # FIX: Explicitly pass the input format to the encoder
        # so it doesn't fail with KeyError: None
        encoder = H264Encoder(bitrate=BITRATE, idr_period=IDR_VAL, input_format=fmt)
        encoder.set_output(FileOutput(stream))
        encoder.start()

        print(f"[!] VIDEO LINK ACTIVE | MODE: {fmt}")

        while True:
            if USE_OVERLAY:
                # 1. Use capture_request to get the hardware buffer
                request = picam2.capture_request()

                # 2. Access the array directly (this is a view of the hardware buffer)
                frame = request.make_array("main")

                # --- DRAWING ---
                data = get_telemetry()
                cv2.rectangle(frame, (0, 670), (1280, 720), (0, 0, 0), -1)
                cv2.putText(frame, f"ALT: {data['alt']}ft | {time.strftime('%H:%M:%S')}",
                            (20, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # 3. Pass the hardware stream and the modified request to the encoder
                # This matches the (stream, request) requirement
                encoder.encode(picam2.streams["main"], request)

                # 4. Release the buffer back to the camera
                picam2.release_request(request)
            else:
                # Optimized path without overlay
                picam2.capture_file("main", encoder)
                time.sleep(0.01)

    except Exception as e:
        print(f"\n[!] ERROR: {e}")
    finally:
        print("[*] Cleaning up...")
        # Note: Added safety check because stop() can fail if start() didn't finish
        try:
            encoder.stop()
        except:
            pass
        picam2.stop()
        sock.close()


if __name__ == "__main__":
    main()