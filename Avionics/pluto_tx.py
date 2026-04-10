import adi
import numpy as np
import threading
import queue
import struct


# ==========================================
# RF CONFIGURATION
# ==========================================
TX_FREQ           = 915_000_000
TX_BW             = 5_000_000
SAMPLE_RATE       = 5_000_000
TX_GAIN           = -50
TX_BUFFER_SAMPLES = 8192
CHUNK_SIZE        = 1024
# ==========================================


def _framer(data: bytes, seq: int) -> bytes:
    sync      = b'\xDE\xAD\xBE\xEF'
    seq_bytes = struct.pack(">I", seq)
    length    = struct.pack(">H", len(data))
    crc       = bytes([sum(data) & 0xFF])
    return sync + seq_bytes + length + data + crc


def _to_qpsk(data: bytes, target_len: int) -> np.ndarray:
    """Bytes → QPSK IQ samples padded to target_len, with BPSK preamble for sync."""
    # BPSK preamble: 64 alternating +1/-1 helps RX find symbol boundaries
    preamble = np.array([1+0j, -1+0j] * 32, dtype=np.complex64)

    bits  = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    if len(bits) % 2:
        bits = np.append(bits, 0)

    i_bits  = bits[0::2].astype(np.float32) * 2 - 1
    q_bits  = bits[1::2].astype(np.float32) * 2 - 1
    symbols = (i_bits + 1j * q_bits).astype(np.complex64)

    # Combine preamble + data symbols
    combined = np.concatenate([preamble, symbols])

    # Pad or truncate to fixed length
    if len(combined) < target_len:
        combined = np.concatenate([combined,
                   np.zeros(target_len - len(combined), dtype=np.complex64)])
    else:
        combined = combined[:target_len]

    return combined * (2**14)


class PlutoTX:
    def __init__(self):
        print("[PlutoTX] Connecting to PlutoSDR...")
        self._sdr = adi.Pluto("usb:")
        self._sdr.sample_rate           = SAMPLE_RATE
        self._sdr.tx_rf_bandwidth       = TX_BW
        self._sdr.tx_lo                 = TX_FREQ
        self._sdr.tx_hardwaregain_chan0  = TX_GAIN
        self._sdr.tx_cyclic_buffer      = False
        self._sdr.tx_buffer_size        = TX_BUFFER_SAMPLES
        print(f"[PlutoTX] Ready at {TX_FREQ/1e6:.1f} MHz, gain={TX_GAIN} dB")

        self._queue = queue.Queue(maxsize=30)
        self._seq   = 0
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def send(self, data: bytes):
        """Called by LiveVideo.py for each H264 chunk."""
        for i in range(0, len(data), CHUNK_SIZE):
            chunk = data[i:i + CHUNK_SIZE]
            if not self._queue.full():
                self._queue.put(chunk)

    def _worker(self):
        while True:
            try:
                chunk   = self._queue.get(timeout=0.5)
                frame   = _framer(chunk, self._seq)
                self._seq = (self._seq + 1) % 0xFFFFFFFF
                symbols = _to_qpsk(frame, TX_BUFFER_SAMPLES)
                self._sdr.tx(symbols)
            except queue.Empty:
                # Keep transmitting zeros to hold buffer
                self._sdr.tx(np.zeros(TX_BUFFER_SAMPLES, dtype=np.complex64))
            except Exception as e:
                print(f"[PlutoTX ERROR] {e}")

    def stop(self):
        try:
            self._sdr.tx_destroy_buffer()
        except:
            pass