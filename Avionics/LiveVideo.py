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

    # Split the data into multiple lines for a compact corner box
    lines = [
        f"ALT: {data['alt']} ft",
        f"GPS: {data['gps']}",
        f"MODE: {Constants.MODE_STR}",
        f"T: {time.strftime('%H:%M:%S')}"
    ]

    for stream_name in ["main", "lores"]:
        try:
            with MappedArray(request, stream_name) as m:
                h, w = m.array.shape[:2]

                # 1. Scale font dynamically based on frame height
                font_scale = max(0.4, h / 900.0)
                font_thick = max(1, int(2 * font_scale))
                font = cv2.FONT_HERSHEY_SIMPLEX

                # 2. Calculate the exact dimensions of the text block
                max_text_w = 0
                total_text_h = 0
                line_spacing = int(8 * font_scale)  # Space between lines
                text_metrics = []

                for line in lines:
                    # getTextSize returns the width/height of the string in pixels
                    (text_w, text_h), baseline = cv2.getTextSize(line, font, font_scale, font_thick)
                    max_text_w = max(max_text_w, text_w)
                    total_text_h += text_h + baseline + line_spacing
                    text_metrics.append((text_w, text_h, baseline))

                # 3. Define the High-Contrast Bounding Box
                padding = int(15 * font_scale)
                box_w = max_text_w + (padding * 2)
                box_h = total_text_h + (padding * 2)

                # Position the box in the bottom-right corner (with a small margin from the absolute edge)
                margin = int(10 * font_scale)
                box_x1 = w - box_w - margin
                box_y1 = h - box_h - margin
                box_x2 = w - margin
                box_y2 = h - margin

                # 4. Draw the stark black background box
                # Writing 0 to the Y-plane (luma) creates pure black
                cv2.rectangle(m.array[:h], (box_x1, box_y1), (box_x2, box_y2), 0, cv2.FILLED)

                # 5. Draw the pure white text line by line
                current_y = box_y1 + padding
                for i, line in enumerate(lines):
                    text_w, text_h, baseline = text_metrics[i]
                    current_y += text_h  # Move pen down to the baseline of the current text

                    # Writing 255 to the Y-plane creates pure white text
                    cv2.putText(
                        m.array[:h], line, (box_x1 + padding, current_y),
                        font, font_scale, 255, font_thick, cv2.LINE_AA
                    )
                    current_y += baseline + line_spacing  # Advance pen for the next line

        except KeyError:
            pass

def main():
    picam2 = Picamera2()

    target_fps = 30
    # Calculate microseconds per frame from the integer in Constants
    frame_time_us = 1_000_000 // target_fps
    dynamic_fps = {"FrameDurationLimits": (frame_time_us, frame_time_us)}

    # Configure the dual hardware streams
    config = picam2.create_video_configuration(
        main={"size": (2304, 1296), "format": "YUV420"},  # High Res directly to SD Card
        lores={"size": (480, 270), "format": "YUV420"},  # Low Res to SDR (Test new sizes here)
        controls=dynamic_fps
    )
    picam2.configure(config)

    if Constants.USE_OVERLAY:
        picam2.pre_callback = apply_overlay


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
            timestamp = datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
            filename = f"Flight_HD_{timestamp}.h264"

            # Use raw unbuffered file writing for maximum crash protection
            local_file = open(filename, "wb")
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