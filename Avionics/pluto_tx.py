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
TX_BUFFER_SAMPLES = 4096
CHUNK_SIZE        = 512
PREAMBLE_LEN      = 64   # must match pluto_rx.py
# ==========================================


def _framer(data: bytes, seq: int) -> bytes:
    sync      = b'\xDE\xAD\xBE\xEF'
    seq_bytes = struct.pack(">I", seq)
    length    = struct.pack(">H", len(data))
    crc       = bytes([sum(data) & 0xFF])
    return sync + seq_bytes + length + data + crc


def _to_qpsk(data: bytes, target_len: int) -> np.ndarray:
    preamble = np.array([1+0j, -1+0j] * (PREAMBLE_LEN // 2), dtype=np.complex64)

    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    if len(bits) % 2:
        bits = np.append(bits, 0)

    i_bits  = bits[0::2].astype(np.float32) * 2 - 1
    q_bits  = bits[1::2].astype(np.float32) * 2 - 1
    symbols = (i_bits + 1j * q_bits).astype(np.complex64)

    combined = np.concatenate([preamble, symbols])

    if len(combined) < target_len:
        # Pad with preamble pattern instead of zeros — helps PLL stay locked
        pad_len  = target_len - len(combined)
        pad      = np.tile([1+0j, -1+0j], pad_len // 2 + 1)[:pad_len]
        combined = np.concatenate([combined, pad.astype(np.complex64)])
    else:
        combined = combined[:target_len]

    return combined * (2**13)   # slightly lower than 2^14 to avoid clipping


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

        self._queue  = queue.Queue(maxsize=30)
        self._seq    = 0
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

def loopback_test():
    """Test TX→demod pipeline without any RF — run on Pi to verify math."""
    import sys
    sys.path.insert(0, '.')

    test_data = b'\xDE\xAD\xBE\xEF' + b'Hello IREC 2026!' * 4
    frame     = _framer(test_data, 42)
    symbols   = _to_qpsk(frame, TX_BUFFER_SAMPLES)

    # Simulate what RX sees — add slight noise and phase rotation
    noise     = (np.random.randn(len(symbols)) + 1j * np.random.randn(len(symbols))) * 10
    rx        = symbols + noise.astype(np.complex64)

    # Try all rotations
    rotations = [1+0j, 0+1j, -1+0j, 0-1j]
    SYNC_WORD = b'\xDE\xAD\xBE\xEF'

    print(f"[TEST] Frame length: {len(frame)} bytes")
    print(f"[TEST] Symbols: {len(symbols)}, TX_BUFFER_SAMPLES: {TX_BUFFER_SAMPLES}")
    print(f"[TEST] Preamble symbols: {PREAMBLE_LEN}")

    for i, rot in enumerate(rotations):
        data_samples = rx[PREAMBLE_LEN:] * rot
        i_bits = (np.real(data_samples) > 0).astype(np.uint8)
        q_bits = (np.imag(data_samples) > 0).astype(np.uint8)
        bits   = np.empty(len(i_bits) * 2, dtype=np.uint8)
        bits[0::2] = i_bits
        bits[1::2] = q_bits
        bits   = bits[:len(bits) - len(bits) % 8]
        result = np.packbits(bits).tobytes()
        found  = SYNC_WORD in result
        idx    = result.find(SYNC_WORD) if found else -1
        print(f"[TEST] Rotation {i} ({rot}): sync={'FOUND at '+str(idx) if found else 'NOT FOUND'}")
        if found:
            print(f"[TEST] ✓ Correct rotation is {i}")
            break

    print("[TEST] Done")

if __name__ == "__main__":
    loopback_test()