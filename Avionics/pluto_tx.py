import adi
import numpy as np
import socket
import threading
import queue
import struct
import time

# ==========================================
# RF CONFIGURATION
# ==========================================
TX_FREQ      = 915_000_000
TX_BW        = 5_000_000
SAMPLE_RATE  = 5_000_000
TX_GAIN      = -50
CHUNK_SIZE   = 1024
UDP_PORT     = 10002

# Fixed buffer size in samples — must stay constant after first tx() call
# 1024 bytes → ~4096 QPSK symbols, round up to next power of 2
TX_BUFFER_SAMPLES = 8192
# ==========================================

def make_qpsk_symbols(data: bytes, target_len: int) -> np.ndarray:
    """Pack bytes into QPSK IQ samples, padded to exactly target_len samples."""
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    if len(bits) % 2:
        bits = np.append(bits, 0)

    i_bits = bits[0::2].astype(np.float32) * 2 - 1
    q_bits = bits[1::2].astype(np.float32) * 2 - 1
    symbols = (i_bits + 1j * q_bits).astype(np.complex64)

    # Pad or truncate to fixed target length
    if len(symbols) < target_len:
        padding = np.zeros(target_len - len(symbols), dtype=np.complex64)
        symbols = np.concatenate([symbols, padding])
    else:
        symbols = symbols[:target_len]

    symbols *= 2**14
    return symbols


def framer(data: bytes, seq: int) -> bytes:
    sync      = b'\xDE\xAD\xBE\xEF'
    seq_bytes = struct.pack(">I", seq)
    length    = struct.pack(">H", len(data))
    crc       = bytes([sum(data) & 0xFF])
    return sync + seq_bytes + length + data + crc


def tx_worker(sdr, pkt_queue: queue.Queue):
    seq = 0
    first = True
    while True:
        try:
            chunk = pkt_queue.get(timeout=1.0)
            frame   = framer(chunk, seq)
            seq     = (seq + 1) % 0xFFFFFFFF
            symbols = make_qpsk_symbols(frame, TX_BUFFER_SAMPLES)

            if first:
                sdr.tx_buffer_size = TX_BUFFER_SAMPLES
                first = False

            sdr.tx(symbols)

        except queue.Empty:
            # Send zeros to keep buffer happy during gaps
            sdr.tx(np.zeros(TX_BUFFER_SAMPLES, dtype=np.complex64))
        except Exception as e:
            print(f"[TX ERROR] {e}")


def main():
    print("[*] Connecting to PlutoSDR TX...")
    sdr = adi.Pluto("usb:")
    sdr.sample_rate           = SAMPLE_RATE
    sdr.tx_rf_bandwidth       = TX_BW
    sdr.tx_lo                 = TX_FREQ
    sdr.tx_hardwaregain_chan0 = TX_GAIN
    sdr.tx_cyclic_buffer      = False
    sdr.tx_buffer_size        = TX_BUFFER_SAMPLES
    print(f"[*] PlutoSDR TX ready at {TX_FREQ/1e6:.1f} MHz, gain={TX_GAIN} dB")

    pkt_queue = queue.Queue(maxsize=30)
    t = threading.Thread(target=tx_worker, args=(sdr, pkt_queue), daemon=True)
    t.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", UDP_PORT))
    print(f"[*] Listening for video on UDP {UDP_PORT}...")

    while True:
        data, _ = sock.recvfrom(CHUNK_SIZE + 64)
        print(f"[UDP RX] {len(data)} bytes")
        if not pkt_queue.full():
            pkt_queue.put(data)


if __name__ == "__main__":
    main()