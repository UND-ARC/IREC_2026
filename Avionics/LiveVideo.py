import socket
import time
import cv2
import io

from picamera2 import Picamera2, MappedArray
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput
from picamera2.outputs import PyavOutput
import Constants





def get_telemetry():
    """Simulated data — replace with real sensor reads for flight"""
    return {"alt": 0, "gps": "32.9904 N, 106.9750 W"}


def apply_overlay(request):
    if not Constants.USE_OVERLAY:
        return
    h, w, banner_h = 720, 1280, 50
    data   = get_telemetry()
    ov_text = (f"  ALT: {data['alt']} ft  |  GPS: {data['gps']}  |  "
               f"{Constants.MODE_STR}  |  {time.strftime('%H:%M:%S')}")
    with MappedArray(request, "main") as m:
        m.array[h - banner_h:h, :] = 0          # black bar
        cv2.putText(
            m.array[:h], ov_text, (10, h - 15),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, 255, 2, cv2.LINE_AA
        )


def main():
    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={"size": (640, 480), "format": "YUV420"}
    )
    picam2.configure(config)

    if Constants.USE_OVERLAY:
        picam2.pre_callback = apply_overlay

    print(f"[*] Starting {Constants.MODE_STR} MODE (Overlay: {Constants.USE_OVERLAY})")

    encoder = H264Encoder(bitrate=Constants.BITRATE, iperiod=Constants.IDR_VAL)
    encoder.options = {
        "bitrate": Constants.BITRATE,
        "iperiod": Constants.IDR_VAL,
        "preset": "ultrafast",
        "tune": "zerolatency",
        "repeat_headers": True,
        "profile": "baseline",
        "x264opts": f"vbv-maxrate={Constants.BITRATE // 1000}:vbv-bufsize=100",
    }

    sock   = None
    videoOutput = None

    try:
        if Constants.IS_FLIGHT_MODE:
            udp_url = f"udp://127.0.0.1:9000?pkt_size=1316&bitrate={Constants.MUXRATE}"

            # 2. Add options={"muxrate": ...} to PAD the stream with dummy data
            videoOutput = PyavOutput(
                udp_url,
                format="mpegts",
                options={"muxrate": str(Constants.MUXRATE)}
            )

            print("[*] FLIGHT MODE — streaming via PlutoSDR RF link")
        else:
            print(f"[*] Connecting to Laptop at {Constants.Laptop_IP}:{Constants.Laptop_Port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((Constants.Laptop_IP, Constants.Laptop_Port))
            sock.settimeout(None)
            print(f"[*] Connected!")
            videoOutput = FileOutput(sock.makefile("wb"))

        # Start recording AFTER output is ready
        picam2.start_recording(encoder, videoOutput)
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
        if sock:
            sock.close()
        



if __name__ == "__main__":
    main()