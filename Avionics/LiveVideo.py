from datetime import datetime
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

    data = get_telemetry()
    # time.strftime dynamically fetches the current Hour:Min:Sec for every single frame
    ov_text = (f"ALT:{data['alt']}ft | GPS:{data['gps']} | "
               f"{Constants.MODE_STR} | {time.strftime('%H:%M:%S')}")

    # Iterate through both high-res ("main") and low-res ("lores") streams
    for stream_name in ["main", "lores"]:
        try:
            with MappedArray(request, stream_name) as m:
                # Dynamically fetch the height (h) and width (w) of the current stream
                h, w = m.array.shape[:2]

                # Scale the black bar and font relative to the dynamic height
                banner_h = max(30, int(h * 0.08))  # 8% of the frame height, minimum 30px
                font_scale = max(0.4, h / 720.0)  # Scale font relative to a 720p baseline
                font_thick = max(1, int(2 * font_scale))

                # Draw the black background bar across the bottom
                m.array[h - banner_h:h, :] = 0

                # Calculate text placement so it aligns nicely within the banner
                text_x = max(10, int(w * 0.02))
                text_y = int(h - (banner_h * 0.3))

                # Burn the text into the frame buffer
                cv2.putText(
                    m.array[:h], ov_text, (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, 255, font_thick, cv2.LINE_AA
                )
        except KeyError:
            # If the camera request doesn't include one of the streams for this specific frame, skip gracefully
            pass


def main():
    picam2 = Picamera2()

    # Force the sensor to exactly FPS
    fps_120 = {"FrameDurationLimits": (8333, 8333)}
    fps_60 = {"FrameDurationLimits": (16666, 16666)}

    # Configure the dual hardware streams
    config = picam2.create_video_configuration(
        main={"size": (1536, 864), "format": "YUV420"},  # High Res directly to SD Card
        lores={"size": (480, 270), "format": "YUV420"},  # Low Res to SDR (Test new sizes here)
        controls=fps_120
    )
    picam2.configure(config)

    if Constants.USE_OVERLAY:
        picam2.pre_callback = apply_overlay
        picam2.set_overlay()

    print(f"[*] Starting {Constants.MODE_STR} MODE (Overlay: {Constants.USE_OVERLAY})")

    flight_encoder = H264Encoder(bitrate=Constants.BITRATE, iperiod=Constants.IDR_VAL)
    flight_encoder.options = {
        "bitrate": Constants.BITRATE,
        "iperiod": Constants.IDR_VAL,
        "preset": "ultrafast",
        "tune": "zerolatency",
        "repeat_headers": True,
        "profile": "baseline",
        "x264opts": f"vbv-maxrate={Constants.BITRATE // 1000}:vbv-bufsize=100",
    }

    highres_encoder = H264Encoder(bitrate=10_000_000)  # 10 Mbps

    sock   = None

    try:
        if Constants.IS_FLIGHT_MODE:
            # Setup SDR output
            udp_url = "udp://127.0.0.1:9000?pkt_size=188&flush_packets=1"
            sdr_output = PyavOutput(udp_url, format="mpegts")

            # Setup the Local File with Timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Flight_HD_{timestamp}.h264"

            # Use raw unbuffered file writing for maximum crash protection
            local_file = open(filename, "wb", buffering=0)
            local_output = FileOutput(local_file)

            print(f"[*] FLIGHT MODE — Streaming SDR and Saving HD to {filename}")

            # Start BOTH encoders. The 'name' argument attaches them to the right stream.
            picam2.start_recording(highres_encoder, local_output, name="main")
            picam2.start_recording(flight_encoder, sdr_output, name="lores")

            print(f"[!] DUAL VIDEO LINK ACTIVE")
        else:
            print(f"[*] Connecting to Laptop at {Constants.Laptop_IP}:{Constants.Laptop_Port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((Constants.Laptop_IP, Constants.Laptop_Port))
            sock.settimeout(None)
            print(f"[*] Connected!")
            videoOutput = FileOutput(sock.makefile("wb"))
            picam2.start_recording(flight_encoder, videoOutput, name="lores")

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