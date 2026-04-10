import socket
import time
import cv2
import numpy as np
import io
from picamera2 import Picamera2, MappedArray
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

# ==========================================
# MISSION CONFIGURATION
# ==========================================
IS_FLIGHT_MODE = True  # Set TRUE for 30k ft Launch
USE_OVERLAY = True       # Set TRUE to draw telemetry
GROUND_STATION_IP = "10.42.0.1"
PORT = 10001

if IS_FLIGHT_MODE:
    BITRATE = 800_000
    IDR_VAL = 15
else:
    BITRATE = 3_000_000
    IDR_VAL = 60

MODE_STR = "FLIGHT" if IS_FLIGHT_MODE else "BENCH"
# ==========================================

def get_telemetry():
    """Simulated data for IREC 2026 bench testing"""
    return {"alt": 0, "gps": "32.9904 N, 106.9750 W"}


class OverlayOutput(io.RawIOBase):
    """
    Sits between picamera2 and the socket.
    Receives raw H264 NAL units — we just forward them.
    The overlay is burned in before encoding via a pre-callback.
    """
    def __init__(self, sock):
        self._sock = sock

    def write(self, b):
        try:
            self._sock.sendall(b)
            return len(b)
        except Exception as e:
            raise


def apply_overlay(request):
    if not USE_OVERLAY:
        return

    h, w = 720, 1280
    banner_h = 50

    data = get_telemetry()
    ov_text = (f"  ALT: {data['alt']} ft  |  GPS: {data['gps']}  |  "
               f"{MODE_STR}  |  {time.strftime('%H:%M:%S')}")

    with MappedArray(request, "main") as m:
        # m.array is a writable YUV420 array — shape (1080, 1280) for luma+chroma
        # Black banner on Y plane
        m.array[h - banner_h:h, :] = 0
        # White text on Y plane
        cv2.putText(
            m.array[:h],
            ov_text,
            (10, h - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65, 255, 2, cv2.LINE_AA
        )


class PlutoOutput(io.RawIOBase):
    def write(self, b):
        # Chunk into 1024 byte pieces for the TX script
        for i in range(0, len(b), 1024):
            socket.sendto(b[i:i+1024], ("127.0.0.1", 10002))
        return len(b)


def main():
    picam2 = Picamera2()

    config = picam2.create_video_configuration(
        main={"size": (1280, 720), "format": "YUV420"}
    )
    picam2.configure(config)

    if USE_OVERLAY:
        picam2.pre_callback = apply_overlay

    print(f"[*] Starting {MODE_STR} MODE (Overlay: {USE_OVERLAY})")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)

    try:
        print(f"[*] Connecting to GS at {GROUND_STATION_IP}:{PORT}...")
        sock.connect((GROUND_STATION_IP, PORT))
        sock.settimeout(None)
        print(f"[*] Connected!")

        # makefile gives a proper BufferedIOBase that FileOutput accepts
        socket_file = sock.makefile("wb")

        encoder = H264Encoder(
            bitrate=BITRATE,
            iperiod=IDR_VAL,
        )

        picam2.start_recording(encoder, FileOutput(socket_file))
        if MODE_STR == "FLIGHT":
            _pluto_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"[!] VIDEO LINK ACTIVE — streaming to {GROUND_STATION_IP}:{PORT}")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[*] Stopped by user.")
    except Exception as e:
        import traceback
        print(f"\n[!] ERROR: {e}")
        traceback.print_exc()
    finally:
        print("[*] Cleaning up...")
        try:
            picam2.stop_recording()
        except:
            pass
        picam2.stop()
        sock.close()


if __name__ == "__main__":
    main()