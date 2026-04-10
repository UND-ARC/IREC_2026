import adi
import numpy as np
import struct
import cv2
import subprocess
import threading
import queue

# ==========================================
TX_FREQ           = 915_000_000
TX_BW             = 5_000_000
SAMPLE_RATE       = 5_000_000
RX_GAIN           = 40
RX_BUFFER_SAMPLES = 8192
PREAMBLE_LEN      = 64
# ==========================================

SYNC = b'\xDE\xAD\xBE\xEF'


def correct_frequency_offset(samples: np.ndarray) -> np.ndarray:
    phase_diff   = samples[1:] * np.conj(samples[:-1])
    freq_offset  = np.angle(np.mean(phase_diff)) / (2 * np.pi)
    t            = np.arange(len(samples))
    correction   = np.exp(-1j * 2 * np.pi * freq_offset * t).astype(np.complex64)
    return samples * correction


def try_demod(samples: np.ndarray, offset: int, rotation: complex) -> bytes:
    """Demodulate starting at a given sample offset with a given phase rotation."""
    s = samples[offset:] * rotation
    i = (np.real(s) > 0).astype(np.uint8)
    q = (np.imag(s) > 0).astype(np.uint8)
    bits = np.empty(len(i) * 2, dtype=np.uint8)
    bits[0::2] = i
    bits[1::2] = q
    bits = bits[:len(bits) - len(bits) % 8]
    return np.packbits(bits).tobytes()


def demod_search(samples: np.ndarray) -> bytes | None:
    """
    Search across timing offsets (0,1) and all 4 phase rotations.
    Returns demodulated bytes if sync word found, else None.
    """
    rotations = [1+0j, 0+1j, -1+0j, 0-1j]

    # Try skipping the preamble at offset 0 and 1 (even/odd alignment)
    for offset in range(2):
        data_samples = samples[PREAMBLE_LEN + offset:]
        for rot in rotations:
            candidate = try_demod(data_samples, 0, rot)
            if SYNC in candidate:
                return candidate

    # Broader search — try every offset up to 8 in case preamble detection is off
    for offset in range(8):
        for rot in rotations:
            candidate = try_demod(samples, offset, rot)
            if SYNC in candidate:
                return candidate

    return None


def deframe(buf: bytearray):
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
        payload = buf[10:10 + length]
        crc_got = buf[10 + length]
        crc_exp = sum(payload) & 0xFF
        if crc_got == crc_exp:
            packets.append((seq, bytes(payload)))
        else:
            # CRC failed — skip past this sync word
            buf = buf[4:]
            continue
        buf = buf[end:]
    return packets, buf


def display_worker(h264_queue: queue.Queue):
    ffmpeg_cmd = [
        "ffmpeg", "-loglevel", "quiet",
        "-f", "h264", "-i", "pipe:0",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-vf", "scale=1280:720",
        "pipe:1"
    ]
    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    frame_size = 1280 * 720 * 3

    def feed_ffmpeg():
        while True:
            try:
                chunk = h264_queue.get(timeout=1.0)
                proc.stdin.write(chunk)
                proc.stdin.flush()
            except queue.Empty:
                continue
            except BrokenPipeError:
                break

    threading.Thread(target=feed_ffmpeg, daemon=True).start()

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
    threading.Thread(target=display_worker, args=(h264_queue,), daemon=True).start()

    buf         = bytearray()
    last_seq    = -1
    total_pkts  = 0
    dropped_pkts = 0
    rx_attempts  = 0
    sync_hits    = 0

    print("[*] Receiving — press Ctrl+C to stop")
    print("[*] Diagnostics every 100 buffers:\n")

    try:
        while True:
            samples     = sdr.rx()
            samples     = correct_frequency_offset(samples)
            rx_attempts += 1

            result = demod_search(samples)

            if result is not None:
                sync_hits += 1
                buf.extend(result)
            else:
                # Still append raw demod in case sync spans two buffers
                raw = try_demod(samples, 0, 1+0j)
                buf.extend(raw)

            # Cap buffer
            if len(buf) > 1024 * 512:
                buf = buf[-1024 * 64:]

            packets, buf = deframe(buf)

            for seq, payload in packets:
                total_pkts += 1
                if last_seq != -1 and seq != (last_seq + 1) % 0xFFFFFFFF:
                    dropped = (seq - last_seq - 1) % 0xFFFFFFFF
                    dropped_pkts += dropped
                last_seq = seq
                if not h264_queue.full():
                    h264_queue.put(payload)

            # Print diagnostics every 100 rx() calls
            if rx_attempts % 100 == 0:
                power = np.mean(np.abs(samples) ** 2)
                print(f"[DIAG] buffers={rx_attempts} | sync_hits={sync_hits} "
                      f"| packets={total_pkts} | dropped={dropped_pkts} "
                      f"| power={power:.1f} | buf_len={len(buf)}")

    except KeyboardInterrupt:
        print(f"\n[*] Done. Received {total_pkts} packets, "
              f"dropped {dropped_pkts} ({100*dropped_pkts/max(total_pkts,1):.1f}%)")


if __name__ == "__main__":
    main()