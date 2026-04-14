#!/usr/bin/env python3
"""
Simple QPSK receiver — decodes counter string from RF.
"""
from gnuradio import gr, digital, blocks
import gnuradio.iio as iio
import numpy as np
import struct
import time
import threading
import queue

import Constants

SYNC = b'\xDE\xAD\xBE\xEF'


class ByteSink(gr.sync_block):
    """Captures decoded bytes into a queue for processing."""
    def __init__(self, byte_queue: queue.Queue):
        gr.sync_block.__init__(
            self,
            name="ByteSink",
            in_sig=[np.uint8],
            out_sig=None
        )
        self._q   = byte_queue
        self._buf = bytearray()

    def work(self, input_items, output_items):
        data = input_items[0]
        self._buf.extend(data.tobytes())

        # Push complete packets to queue
        while True:
            idx = self._buf.find(SYNC)
            if idx == -1:
                self._buf = self._buf[-4:]
                break
            if idx > 0:
                self._buf = self._buf[idx:]
            if len(self._buf) < 10:
                break

            # Parse header
            counter = struct.unpack(">I", self._buf[4:8])[0]
            length  = self._buf[8]
            end     = 9 + length + 1

            if len(self._buf) < end:
                break

            payload  = self._buf[9:9 + length]
            crc_got  = self._buf[9 + length]
            crc_exp  = sum(payload) & 0xFF

            if crc_got == crc_exp:
                self._q.put((counter, bytes(payload)))

            self._buf = self._buf[end:]

        return len(data)


class RxFlowgraph(gr.top_block):
    def __init__(self, byte_queue: queue.Queue):
        gr.top_block.__init__(self, "QPSK RX")

        # --- Blocks ---
        self.pluto = iio.fmcomms2_source_fc32(
            Constants.Pluto_Ground_IP,
            [True, False, False, False],
            32768,
        )
        self.pluto.set_frequency(Constants.RX_FREQ)
        self.pluto.set_samplerate(Constants.SAMP_RATE)
        #self.pluto.set_bandwidth(Constants.SAMP_RATE)
        self.pluto.set_gain_mode(0, "manual")
        self.pluto.set_gain(0, Constants.RX_GAIN)
        self.pluto.set_quadrature(True)
        self.pluto.set_rfdc(True)
        self.pluto.set_bbdc(True)

        # QPSK demod — GNU Radio handles all sync automatically
        constellation = digital.constellation_qpsk().base()
        self.demod    = digital.generic_demod(
            constellation      = constellation,
            differential       = False,
            samples_per_symbol = Constants.SPS,
            pre_diff_code      = True,
            freq_bw            = 6.28/100,
            timing_bw          = 6.28/100,
            verbose            = False,
            log                = False
        )

        # generic_demod outputs 1 bit per byte — pack into bytes
        self.repack = blocks.repack_bits_bb(
            1,  # input bits per byte (from demod)
            8,  # output bits per byte
            "",  # tag key
            False,  # align
            gr.GR_MSB_FIRST
        )

        # Our custom sink
        self.sink = ByteSink(byte_queue)

        # --- Connect ---
        self.connect(self.pluto, self.demod, self.repack, self.sink)


def main():
    print(f"[RX] Starting QPSK RX at {Constants.RX_FREQ/1e6:.1f} MHz")

    byte_queue = queue.Queue()
    tb         = RxFlowgraph(byte_queue)
    tb.start()

    last_counter = -1
    total        = 0
    dropped      = 0

    print("[RX] Listening — press Ctrl+C to stop\n")

    try:
        while True:
            try:
                counter, payload = byte_queue.get(timeout=2.0)
                total += 1

                if last_counter != -1:
                    gap = counter - last_counter - 1
                    if gap > 0:
                        dropped += gap
                        print(f"[RX] GAP: {gap} packets dropped "
                              f"(seq {last_counter}→{counter})")

                last_counter = counter
                loss_pct = 100 * dropped / max(total + dropped, 1)
                print(f"[RX] {payload.decode(errors='replace')} "
                      f"| total={total} dropped={dropped} "
                      f"loss={loss_pct:.1f}%")

            except queue.Empty:
                print("[RX] No packets received (timeout)")

    except KeyboardInterrupt:
        pass
    finally:
        tb.stop()
        tb.wait()
        print(f"\n[RX] Done. Received={total} Dropped={dropped}")


if __name__ == "__main__":
    main()