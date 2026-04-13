#!/usr/bin/env python3
"""
Simple QPSK transmitter — sends a counter string over RF.
Pi → PlutoSDR TX → RF → PlutoSDR RX → Laptop
"""
from gnuradio import gr, digital, blocks
import gnuradio.iio as iio
import numpy as np
import threading
import time
import struct

import Constants


def make_packet(counter: int) -> bytes:
    """
    Frame format:
    [SYNC 4B][COUNTER 4B][LEN 1B][PAYLOAD][CRC 1B]
    """
    payload   = f"PKT:{counter:06d}".encode()
    sync      = b'\xDE\xAD\xBE\xEF'
    length    = bytes([len(payload)])
    crc       = bytes([sum(payload) & 0xFF])
    return sync + struct.pack(">I", counter) + length + payload + crc


class PacketSource(gr.sync_block):
    """Generates a continuous stream of QPSK-ready bytes."""
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="PacketSource",
            in_sig=None,
            out_sig=[np.uint8]
        )
        self._buf     = bytearray()
        self._counter = 0
        self._lock    = threading.Lock()

    def work(self, input_items, output_items):
        out = output_items[0]
        n   = len(out)

        with self._lock:
            # Fill buffer if running low
            while len(self._buf) < n:
                pkt = make_packet(self._counter)
                self._counter += 1
                self._buf.extend(pkt)

            chunk = self._buf[:n]
            self._buf = self._buf[n:]

        out[:] = list(chunk)
        return n


class TxFlowgraph(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "QPSK TX")

        # --- Blocks ---
        self.src       = PacketSource()

        # Pack bytes into bits
        self.pack      = blocks.pack_k_bits_bb(8)

        # QPSK constellation
        constellation  = digital.constellation_qpsk().base()
        self.mod       = digital.generic_mod(
            constellation   = constellation,
            differential    = False,
            samples_per_symbol = Constants.SPS,
            pre_diff_code   = True,
            excess_bw       = 0.35,
            verbose         = False,
            log             = False
        )

        # Scale to PlutoSDR range
        self.scale     = blocks.multiply_const_cc(0.9)

        # PlutoSDR sink
        self.pluto = iio.fmcomms2_sink_fc32(
            uri=Constants.Pluto_Pi_IP,
            ch_en=[True, False, False, False],
            buffer_size=32768,
            cyclic=False,
        )
        self.pluto.set_frequency(Constants.TX_FREQ)
        self.pluto.set_samplerate(Constants.SAMP_RATE)
        self.pluto.set_bandwidth(Constants.SAMP_RATE)
        self.pluto.set_attenuation(0, abs(Constants.TX_GAIN))

        # --- Connect ---
        self.connect(self.src, self.pack, self.mod, self.scale, self.pluto)


def main():
    print(f"[TX] Starting QPSK TX at {Constants.TX_FREQ/1e6:.1f} MHz")
    print(f"[TX] Sample rate: {Constants.SAMP_RATE/1e6:.1f} Msps, SPS: {Constants.SPS}")
    print(f"[TX] TX gain: {Constants.TX_GAIN} dB")

    tb = TxFlowgraph()
    tb.start()

    try:
        counter = 0
        while True:
            time.sleep(1)
            counter += 1
            print(f"[TX] Running... t={counter}s")
    except KeyboardInterrupt:
        pass
    finally:
        tb.stop()
        tb.wait()
        print("[TX] Stopped.")


if __name__ == "__main__":
    main()