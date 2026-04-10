import adi
import numpy as np
import struct
import cv2
import subprocess
import threading
import queue
import os
import signal

# ==========================================
TX_FREQ            = 915_000_000
TX_BW              = 5_000_000
SAMPLE_RATE        = 5_000_000
RX_GAIN            = 40
RX_BUFFER_SAMPLES  = 8192
PREAMBLE_LEN       = 64   # must match TX
# ==========================================

SYNC = b'\xDE\xAD\xBE\xEF'


def correct_frequency_offset(samples: np.ndarray) -> np.ndarray:
    """
    Coarse frequency offset correction using the preamble.
    The preamble is alternating +1/-1 (BPSK at Fs/2),
    so we can estimate CFO from the phase slope.
    """
    # Multiply signal by conjugate of delayed signal to get phase diff
    phase_diff = samples[1:] * np.conj(samples[:-1])
    # Estimate frequency offset from mean phase
    freq_offset = np.angle(np.mean(phase_diff)) / (2 * np.pi)
    # Correct it
    t = np.arange(len(samples))
    correction = np.exp(-1j * 2 * np.pi * freq_offset * t).astype(np.complex64)
    return samples * correction


def demod_qpsk(samples: np.ndarray) -> bytes:
    """QPSK demodulation with phase ambiguity resolution via sync word search."""
    # Try all 4 QPSK phase rotations (0, 90, 180, 270 degrees)
    rotations = [1+0j, 0+1j, -1+0j, 0-1j]

    # Skip preamble
    data_samples = samples[PREAMBLE_LEN:]

    for rot in rotations:
        rotated = data_samples * rot
        i = (np.real(rotated) > 0).astype(np.uint8)
        q = (np.imag(rotated) > 0).astype(np.uint8)
        bits = np.empty(len(i) * 2, dtype=np.uint8)
        bits[0::2] = i
        bits[1::2] = q
        bits = bits[:len(bits) - len(bits) % 8]
        candidate = np.packbits(bits).tobytes()
        # If this rotation contains our sync word, it's correct
        if SYNC in candidate:
            return candidate

    # No rotation matched — return best guess
    i = (np.real(data_samples) > 0).astype(np.uint8)
    q = (np.imag(data_samples) > 0).astype(np.uint8)
    bits = np.empty(len(i) * 2, dtype=np.uint8)
    bits[0::2] = i
    bits[1::2] = q
    bits = bits[:len(bits) - len(bits) % 8]
    return np.packbits(bits).tobytes()


def deframe(buf: bytearray):
    """Extract valid packets from buffer."""
    packets = []
    while len(buf) >= 11:
        idx = buf.find(SYNC)
        if idx == -1:
            buf = buf[-4:]
            break
        if idx > 0:
            buf = buf[idx:]
        if len(buf) < 11:
            break
        seq    = struct.unpack(">I", buf[4:8])[0]
        length = struct.unpack(">H", buf[8:10])[0]
        end    = 10 + length + 1
        if len(buf) < end:
            break
        payload  = buf[10:10 + length]
        crc_got  = buf[10 + length]
        crc_exp  = sum(payload) & 0xFF
        if crc_got == crc_exp:
            packets.append((seq, bytes(payload)))
        buf = buf[end:]
    return packets, buf


def display_worker(h264_queue: queue.Queue):
    """
    Feeds H264 data into ffmpeg, reads decoded frames,
    and displays them with OpenCV.
    """
    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel", "quiet",
        "-f", "h264",          # input is raw H264
        "-i", "pipe:0",        # read from stdin
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",   # OpenCV native format
        "-vf", "scale=1280:720",
        "pipe:1"               # output to stdout
    ]

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    frame_size = 1280 * 720 * 3  # bgr24

    def feed_ffmpeg():
        """Thread: pulls H264 chunks from queue → ffmpeg stdin."""
        while True:
            try:
                chunk = h264_queue.get(timeout=1.0)
                proc.stdin.write(chunk)
                proc.stdin.flush()
            except queue.Empty:
                continue
            except BrokenPipeError:
                break

    feeder = threading.Thread(target=feed_ffmpeg, daemon=True)
    feeder.start()

    cv2.namedWindow("IREC 2026 — Live Downlink", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("IREC 2026 — Live Downlink", 1280, 720)

    while True:
        raw = proc.stdout.read(frame_size)
        if len(raw) < frame_size:
            break
        frame = np.frombuffer(raw, dtype=np.uint8).reshape((720, 1280, 3))
        cv2.imshow("IREC 2026 — Live Downlink", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    proc.terminate()


def main():
    print("[*] Connecting to PlutoSDR RX...")
    sdr = adi.Pluto("usb:")
    sdr.sample_rate             = SAMPLE_RATE
    sdr.rx_rf_bandwidth         = TX_BW
    sdr.rx_lo                   = TX_FREQ
    sdr.gain_control_mode_chan0 = "manual"
    sdr.rx_hardwaregain_chan0   = RX_GAIN
    sdr.rx_buffer_size          = RX_BUFFER_SAMPLES
    print(f"[*] PlutoSDR RX ready at {TX_FREQ/1e6:.1f} MHz")

    h264_queue = queue.Queue(maxsize=60)

    display = threading.Thread(target=display_worker, args=(h264_queue,), daemon=True)
    display.start()

    buf      = bytearray()
    last_seq = -1
    total_pkts  = 0
    dropped_pkts = 0

    print("[*] Receiving — press Ctrl+C to stop")

    try:
        while True:
            samples  = sdr.rx()
            samples  = correct_frequency_offset(samples)
            raw      = demod_qpsk(samples)
            buf.extend(raw)

            # Cap buffer size to avoid unbounded growth
            if len(buf) > 1024 * 512:
                buf = buf[-1024 * 64:]

            packets, buf = deframe(buf)

            for seq, payload in packets:
                total_pkts += 1
                if last_seq != -1 and seq != (last_seq + 1) % 0xFFFFFFFF:
                    dropped = (seq - last_seq - 1) % 0xFFFFFFFF
                    dropped_pkts += dropped
                    print(f"[!] Gap: {dropped} pkts dropped "
                          f"(total {dropped_pkts}/{total_pkts})")
                last_seq = seq
                if not h264_queue.full():
                    h264_queue.put(payload)

    except KeyboardInterrupt:
        print(f"\n[*] Done. Received {total_pkts} packets, "
              f"dropped {dropped_pkts} ({100*dropped_pkts/max(total_pkts,1):.1f}%)")


if __name__ == "__main__":
    main()