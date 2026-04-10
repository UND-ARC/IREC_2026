import adi
import numpy as np
import socket
import struct

#TX_FREQ     = 1_200_000_000
#TX_BW       = 10_000_000
TX_FREQ = 915_000_000   # 915 MHz TODO for testing
TX_BW   = 5_000_000     # drop to 5 MHz — safer for 915 antennas TODO for testing
SAMPLE_RATE = 5_000_000
RX_GAIN     = 40            # dB
CHUNK_SIZE  = 1024
FFPLAY_IP   = "127.0.0.1"
FFPLAY_PORT = 10003
RX_BUFFER_SAMPLES = 8192

SYNC = b'\xDE\xAD\xBE\xEF'


def demod_qpsk(samples: np.ndarray) -> bytes:
    """Demodulate QPSK IQ samples back to bytes."""
    samples = samples / (2**14)
    i = (np.real(samples) > 0).astype(np.uint8)
    q = (np.imag(samples) > 0).astype(np.uint8)
    bits = np.empty(len(i) * 2, dtype=np.uint8)
    bits[0::2] = i
    bits[1::2] = q
    # Trim to byte boundary
    bits = bits[:len(bits) - len(bits) % 8]
    return np.packbits(bits).tobytes()


def deframe(buf: bytearray):
    """Extract packets from buffer, return (packets, remaining_buffer)."""
    packets = []
    while len(buf) >= 11:  # min frame size
        idx = buf.find(SYNC)
        if idx == -1:
            buf = buf[-4:]  # keep last 4 bytes in case sync is split
            break
        if idx > 0:
            buf = buf[idx:]  # discard garbage before sync
        if len(buf) < 11:
            break
        seq = struct.unpack(">I", buf[4:8])[0]
        length = struct.unpack(">H", buf[8:10])[0]
        end = 10 + length + 1  # +1 for CRC
        if len(buf) < end:
            break  # wait for more data
        payload = buf[10:10 + length]
        crc_got = buf[10 + length]
        crc_exp = sum(payload) & 0xFF
        if crc_got == crc_exp:
            packets.append((seq, bytes(payload)))
        buf = buf[end:]
    return packets, buf


def main():
    print("[*] Connecting to PlutoSDR RX...")
    sdr = adi.Pluto("usb:")
    sdr.sample_rate           = SAMPLE_RATE
    sdr.rx_rf_bandwidth       = TX_BW
    sdr.rx_lo                 = TX_FREQ
    sdr.gain_control_mode_chan0 = "manual"
    sdr.rx_hardwaregain_chan0 = RX_GAIN
    sdr.rx_buffer_size        = RX_BUFFER_SAMPLES
    print(f"[*] PlutoSDR RX ready at {TX_FREQ/1e9:.3f} GHz")

    # Send recovered video to ffplay via UDP
    out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    buf = bytearray()
    last_seq = -1

    print(f"[*] Streaming recovered video to UDP {FFPLAY_PORT}")
    print(f"    Run: ffplay -i udp://127.0.0.1:{FFPLAY_PORT} -fflags nobuffer")

    while True:
        try:
            samples = sdr.rx()
            raw = demod_qpsk(samples)
            buf.extend(raw)
            packets, buf = deframe(buf)
            for seq, payload in packets:
                if seq != last_seq + 1 and last_seq != -1:
                    print(f"[!] Dropped {seq - last_seq - 1} packets (seq {last_seq}→{seq})")
                last_seq = seq
                out_sock.sendto(payload, (FFPLAY_IP, FFPLAY_PORT))
        except Exception as e:
            print(f"[RX ERROR] {e}")


if __name__ == "__main__":
    main()