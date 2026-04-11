import adi
import numpy as np
import struct
import cv2
import subprocess
import threading
import queue

# ==========================================
TX_FREQ           = 915_000_000
TX_BW             = 10_000_000
SAMPLE_RATE       = 10_000_000
RX_GAIN           = 20
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

def demod_with_phase_tracking(samples: np.ndarray) -> bytes:
    """
    Symbol-by-symbol QPSK demod with a phase tracking PLL.
    Handles frequency offsets that spin the constellation.
    """
    # Skip preamble
    data = samples[PREAMBLE_LEN:].copy()
    n    = len(data)

    # PLL parameters — tune these if lock is unstable
    alpha      = 0.1    # phase correction gain
    beta       = 0.001  # frequency correction gain
    phase      = 0.0
    freq       = 0.0

    i_bits = np.zeros(n, dtype=np.uint8)
    q_bits = np.zeros(n, dtype=np.uint8)

    for k in range(n):
        # Apply current phase correction
        corrected = data[k] * np.exp(-1j * phase)

        # Hard decision
        i_bit = 1 if np.real(corrected) > 0 else 0
        q_bit = 1 if np.imag(corrected) > 0 else 0
        i_bits[k] = i_bit
        q_bits[k] = q_bit

        # Ideal symbol location
        i_ideal = 1.0 if i_bit else -1.0
        q_ideal = 1.0 if q_bit else -1.0

        # Phase error = cross product of received vs ideal
        error = (np.real(corrected) * q_ideal -
                 np.imag(corrected) * i_ideal)

        # Update PLL
        freq  += beta * error
        phase += alpha * error + freq

    # Pack bits
    bits = np.empty(n * 2, dtype=np.uint8)
    bits[0::2] = i_bits
    bits[1::2] = q_bits
    bits = bits[:len(bits) - len(bits) % 8]
    return np.packbits(bits).tobytes()

def main():
    print("[*] Connecting to PlutoSDR RX...")
    sdr = adi.Pluto("usb:")
    sdr.sample_rate             = SAMPLE_RATE
    sdr.rx_rf_bandwidth         = TX_BW
    sdr.rx_lo                   = TX_FREQ
    sdr.tx_lo = TX_FREQ
    # Force both sides to use the same reference
    sdr._ctrl.attrs["dcxo_tune_coarse"].value = "0"
    sdr._ctrl.attrs["dcxo_tune_fine"].value = "0"
    sdr.gain_control_mode_chan0 = "manual"
    sdr.rx_hardwaregain_chan0   = RX_GAIN
    sdr.rx_buffer_size          = RX_BUFFER_SAMPLES
    print(f"[*] PlutoSDR RX ready at {TX_FREQ/1e6:.1f} MHz")

    h264_queue = queue.Queue(maxsize=60)
    threading.Thread(target=display_worker, args=(h264_queue,), daemon=True).start()

    # Accumulate samples across buffers — TX sends 8192 samples but RX
    # buffers may not be aligned to TX buffer boundaries
    sample_buf   = np.array([], dtype=np.complex64)

    buf          = bytearray()
    last_seq     = -1
    total_pkts   = 0
    dropped_pkts = 0
    rx_attempts  = 0
    sync_hits    = 0

    print("[*] Receiving — press Ctrl+C to stop\n")

    try:
        while True:
            new_samples = sdr.rx()
            sample_buf = np.concatenate([sample_buf, new_samples.astype(np.complex64)])
            rx_attempts += 1

            while len(sample_buf) >= RX_BUFFER_SAMPLES:
                chunk = sample_buf[:RX_BUFFER_SAMPLES]
                sample_buf = sample_buf[RX_BUFFER_SAMPLES:]

                result = demod_with_phase_tracking(chunk)
                buf.extend(result)
                if SYNC in result:
                    sync_hits += 1

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

            if rx_attempts % 100 == 0:
                power = np.mean(np.abs(new_samples) ** 2)
                print(f"[DIAG] buffers={rx_attempts} | sync_hits={sync_hits} "
                      f"| packets={total_pkts} | dropped={dropped_pkts} "
                      f"| power={power:.1f} | buf_len={len(buf)} "
                      f"| sample_buf={len(sample_buf)}")

    except KeyboardInterrupt:
        print(f"\n[*] Done. Received {total_pkts} pkts, "
              f"dropped {dropped_pkts} ({100*dropped_pkts/max(total_pkts,1):.1f}%)")


def capture_diagnostic():
    """Capture raw IQ when signal detected, save to file for offline analysis."""
    print("[*] Connecting to PlutoSDR RX...")
    sdr = adi.Pluto("usb:7.3.5")
    sdr.sample_rate             = SAMPLE_RATE
    sdr.rx_rf_bandwidth         = TX_BW
    sdr.rx_lo                   = TX_FREQ
    sdr.gain_control_mode_chan0 = "manual"
    sdr.rx_hardwaregain_chan0   = RX_GAIN
    sdr.rx_buffer_size          = RX_BUFFER_SAMPLES
    print(f"[*] Watching for signal at {TX_FREQ/1e6:.1f} MHz — start the Pi TX now")

    NOISE_FLOOR  = 1000    # power below this = no signal
    captured     = []
    capturing    = False
    capture_goal = 50      # save 50 buffers worth of signal

    try:
        while True:
            samples = sdr.rx().astype(np.complex64)
            power   = np.mean(np.abs(samples) ** 2)

            if not capturing and power > NOISE_FLOOR:
                print(f"[!] Signal detected! power={power:.0f} — capturing...")
                capturing = True

            if capturing:
                captured.append(samples.copy())
                print(f"    captured {len(captured)}/{capture_goal} buffers")
                if len(captured) >= capture_goal:
                    break

    except KeyboardInterrupt:
        pass

    if captured:
        all_samples = np.concatenate(captured)
        np.save("captured_iq.npy", all_samples)
        print(f"[*] Saved {len(all_samples)} samples to captured_iq.npy")
        print(f"[*] Run: python analyze_iq.py")
    else:
        print("[!] No signal captured")



if __name__ == "__main__":
    #capture_diagnostic()
    main()