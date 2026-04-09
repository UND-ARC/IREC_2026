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
TX_FREQ     = 1_200_000_000   # 1.2 GHz
TX_BW       = 10_000_000      # 10 MHz bandwidth
SAMPLE_RATE = 10_000_000      # 10 Msps
TX_GAIN     = -20             # dBm — keep LOW for bench testing, max -0 for flight
CHUNK_SIZE  = 1024            # bytes per RF burst
UDP_PORT    = 10002           # local UDP port to receive H264 from camera script

# ==========================================

def make_qpsk_symbols(data: bytes) -> np.ndarray:
    """Pack bytes into QPSK IQ samples."""
    # Pad to even number of bits
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    if len(bits) % 2:
        bits = np.append(bits, 0)

    # Map bit pairs to QPSK constellation
    # 00 -> 1+1j, 01 -> -1+1j, 10 -> 1-1j, 11 -> -1-1j
    i_bits = bits[0::2].astype(np.float32) * 2 - 1
    q_bits = bits[1::2].astype(np.float32) * 2 - 1

    symbols = (i_bits + 1j * q_bits).astype(np.complex64)

    # Scale to PlutoSDR's expected range
    symbols *= 2**14

    return symbols


def framer(data: bytes, seq: int) -> bytes:
    """
    Simple packet framing:
    [SYNC 4B][SEQ 4B][LEN 2B][PAYLOAD][CRC 1B]
    """
    sync = b'\xDE\xAD\xBE\xEF'
    length = struct.pack(">H", len(data))
    seq_bytes = struct.pack(">I", seq)
    crc = sum(data) & 0xFF
    return sync + seq_bytes + length + data + bytes([crc])


def tx_worker(sdr, pkt_queue: queue.Queue):
    """Pulls packets from queue and transmits."""
    seq = 0
    while True:
        try:
            chunk = pkt_queue.get(timeout=1.0)
            frame = framer(chunk, seq)
            seq = (seq + 1) % 0xFFFFFFFF
            symbols = make_qpsk_symbols(frame)
            sdr.tx(symbols)
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[TX ERROR] {e}")


def main():
    print("[*] Connecting to PlutoSDR...")
    sdr = adi.Pluto("usb:")
    sdr.sample_rate              = SAMPLE_RATE
    sdr.tx_rf_bandwidth          = TX_BW
    sdr.tx_lo                    = TX_FREQ
    sdr.tx_hardwaregain_chan0    = TX_GAIN
    sdr.tx_cyclic_buffer         = False
    sdr.tx_buffer_size           = 1024 * 16
    print(f"[*] PlutoSDR TX ready at {TX_FREQ/1e9:.3f} GHz, gain={TX_GAIN} dBm")

    pkt_queue = queue.Queue(maxsize=30)

    # Start TX thread
    t = threading.Thread(target=tx_worker, args=(sdr, pkt_queue), daemon=True)
    t.start()

    # Listen for H264 chunks over local UDP from camera script
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", UDP_PORT))
    print(f"[*] Listening for video on UDP {UDP_PORT}...")

    while True:
        data, _ = sock.recvfrom(CHUNK_SIZE + 64)
        if not pkt_queue.full():
            pkt_queue.put(data)
        else:
            pass  # drop packet — RF can't keep up, normal at high bitrates


if __name__ == "__main__":
    main()