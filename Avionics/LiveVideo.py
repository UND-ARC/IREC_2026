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
IS_FLIGHT_MODE = True   # Set TRUE for 30k ft Launch
USE_OVERLAY    = True    # Set TRUE to draw telemetry overlay

GROUND_STATION_IP = "10.42.0.1"
PORT              = 10001

PLUTO_UDP_IP   = "127.0.0.1"
PLUTO_UDP_PORT = 10002
PLUTO_CHUNK    = 1024

if IS_FLIGHT_MODE:
    BITRATE = 800_000
    IDR_VAL = 15
else:
    BITRATE = 3_000_000
    IDR_VAL  = 60

MODE_STR = "FLIGHT" if IS_FLIGHT_MODE else "BENCH"
# ==========================================


def get_telemetry():
    """Simulated data — replace with real sensor reads for flight"""
    return {"alt": 0, "gps": "32.9904 N, 106.9750 W"}


def apply_overlay(request):
    if not USE_OVERLAY:
        return
    h, w, banner_h = 720, 1280, 50
    data   = get_telemetry()
    ov_text = (f"  ALT: {data['alt']} ft  |  GPS: {data['gps']}  |  "
               f"{MODE_STR}  |  {time.strftime('%H:%M:%S')}")
    with MappedArray(request, "main") as m:
        m.array[h - banner_h:h, :] = 0          # black bar
        cv2.putText(
            m.array[:h], ov_text, (10, h - 15),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, 255, 2, cv2.LINE_AA
        )


class PlutoOutput(io.RawIOBase):
    """Chunks H264 NAL units into UDP datagrams for pluto_tx.py"""
    def __init__(self, udp_sock):
        self._sock = udp_sock

    def write(self, b):
        for i in range(0, len(b), PLUTO_CHUNK):
            self._sock.sendto(b[i:i + PLUTO_CHUNK], (PLUTO_UDP_IP, PLUTO_UDP_PORT))
        return len(b)


class EthernetOutput(io.RawIOBase):
    """Streams H264 NAL units over TCP to ground station"""
    def __init__(self, tcp_sock):
        self._sock = tcp_sock

    def write(self, b):
        self._sock.sendall(b)
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

    encoder = H264Encoder(bitrate=BITRATE, iperiod=IDR_VAL)

    tcp_sock   = None
    pluto_sock = None

    try:
        if IS_FLIGHT_MODE:
            # --- FLIGHT: stream via PlutoSDR ---
            pluto_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            output     = FileOutput(PlutoOutput(pluto_sock))
            print(f"[*] FLIGHT MODE — sending H264 chunks to pluto_tx.py on UDP {PLUTO_UDP_PORT}")

        else:
            # --- BENCH: stream via Ethernet TCP ---
            print(f"[*] Connecting to GS at {GROUND_STATION_IP}:{PORT}...")
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.settimeout(10.0)
            tcp_sock.connect((GROUND_STATION_IP, PORT))
            tcp_sock.settimeout(None)
            print(f"[*] Connected!")
            output = FileOutput(tcp_sock.makefile("wb"))

        # Start recording AFTER output is ready
        picam2.start_recording(encoder, output)
        print(f"[!] VIDEO LINK ACTIVE")

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
        if tcp_sock:
            tcp_sock.close()
        if pluto_sock:
            pluto_sock.close()


if __name__ == "__main__":
    main()