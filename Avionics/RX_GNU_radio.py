#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# IREC 2026 Avionics — RX Flowgraph
# Laptop PlutoSDR (192.168.4.1) @ 915 MHz → UDP 127.0.0.1:10001 → ffplay
#
# Run receiver:  python3 RX_GNU_radio.py
# Run player:    ffplay -fflags nobuffer -flags low_delay -framedrop \
#                       -i udp://127.0.0.1:10001

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from gnuradio import analog, blocks, digital, gr, network, filter as grfilter
from gnuradio.filter import firdes
from gnuradio.fft import window
from gnuradio import iio
import sys, signal, threading

class RX_GNU_radio(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "IREC RX", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables — must match TX exactly
        ##################################################
        self.samp_rate  = 1_500_000
        self.sps        = 2          # must match TX samples_per_symbol
        self.nfilts     = 32
        self.excess_bw  = 0.35

        # QPSK constellation — identical to TX
        self.qpsk = digital.constellation_rect(
            [0.707+0.707j, -0.707+0.707j, -0.707-0.707j, 0.707-0.707j],
            [0, 1, 2, 3], 4, 2, 2, 1, 1).base()

        # Access code — must match TX header_format exactly
        self.access_code = '11011011001100001111011100000011'

        # RRC filter taps — nfilts, nfilts, 1/sps, excess_bw, 11*sps*nfilts
        self.rrc_taps = firdes.root_raised_cosine(
            self.nfilts, self.nfilts,
            1.0 / float(self.sps),
            self.excess_bw,
            11 * self.sps * self.nfilts)

        ##################################################
        # Blocks
        ##################################################

        # 1. PlutoSDR source — samp_rate only, no *2
        self.pluto_source = iio.fmcomms2_source_fc32(
            'ip:192.168.4.1',
            [True, True], 32768)
        self.pluto_source.set_len_tag_key('packet_len')
        self.pluto_source.set_frequency(915_000_000)
        self.pluto_source.set_samplerate(self.samp_rate)   # was samp_rate*2, now fixed
        self.pluto_source.set_gain_mode(0, 'manual')
        self.pluto_source.set_gain(0, 30)                  # bumped from 15
        self.pluto_source.set_quadrature(True)
        self.pluto_source.set_rfdc(True)
        self.pluto_source.set_bbdc(True)
        self.pluto_source.set_filter_params('Auto', '', 0, 0)

        # 2. AGC — normalize amplitude before clock sync
        self.agc = analog.agc_cc(1e-4, 1.0, 1.0)

        # 3. Low pass filter — reject out-of-band noise
        self.lpf = grfilter.fir_filter_ccf(
            1,
            firdes.low_pass(
                1, self.samp_rate,
                600_000,   # cutoff: slightly above signal bandwidth
                100_000,   # transition width
                window.WIN_HAMMING))

        # 4. FLL — coarse frequency correction (handles Pluto crystal offset)
        self.fll = digital.fll_band_edge_cc(
            self.sps,
            self.excess_bw,
            44,     # filter size
            0.01)   # loop bandwidth — wide enough for ±25ppm at 915MHz (~23kHz)

        # 5. Polyphase clock sync — sps=2 to match TX
        self.clock_sync = digital.pfb_clock_sync_ccf(
            self.sps,
            6.28 / 100.0,
            self.rrc_taps,
            self.nfilts,
            self.nfilts // 2,
            1.5,
            1)      # output sps = 1 (one sample per symbol out)

        # 6. CMA equalizer
        self.eq_algo = digital.adaptive_algorithm_cma(self.qpsk, 1e-3, 4).base()
        self.equalizer = digital.linear_equalizer(
            15, 1, self.eq_algo, True, [], 'corr_est')

        # 7. Costas loop — fine phase correction
        self.costas = digital.costas_loop_cc(6.28 / 50.0, 4, False)

        # 8. Constellation decoder — QPSK symbols (0-3)
        self.decoder = digital.constellation_decoder_cb(self.qpsk)

        # 9. Differential decoder — must match TX differential=True
        self.diff_decoder = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)

        # 10. Map symbols 0-3 → dibits
        self.mapper = digital.map_bb([0, 1, 2, 3])

        # 11. Unpack 2-bit dibits to individual bits for correlator
        self.unpack = blocks.unpack_k_bits_bb(2)

        # 12. Correlate access code — finds packet boundaries
        #     threshold=2 allows up to 2 bit errors in the access code
        self.correlator = digital.correlate_access_code_bb_ts(
            self.access_code, 2, 'packet_len')  # tag name matches TX

        # 13. Repack bits → bytes, using 'packet_len' tag
        self.repack = blocks.repack_bits_bb(
            1, 8, 'packet_len', False, gr.GR_MSB_FIRST)

        # 14. CRC32 check — strips CRC, drops bad packets
        self.crc_check = digital.crc32_bb(True, "packet_len", True)

        # 15. UDP sink → ffplay
        self.udp_sink = network.udp_sink(
            gr.sizeof_char, 1,
            '127.0.0.1', 10001,
            0, 1316, False)

        ##################################################
        # Connections
        ##################################################
        self.connect((self.pluto_source, 0), (self.agc,         0))
        self.connect((self.agc,          0), (self.lpf,         0))
        self.connect((self.lpf,          0), (self.fll,         0))
        self.connect((self.fll,          0), (self.clock_sync,  0))
        self.connect((self.clock_sync,   0), (self.equalizer,   0))
        self.connect((self.equalizer,    0), (self.costas,      0))
        self.connect((self.costas,       0), (self.decoder,     0))
        self.connect((self.decoder,      0), (self.diff_decoder,0))
        self.connect((self.diff_decoder, 0), (self.mapper,      0))
        self.connect((self.mapper,       0), (self.unpack,      0))
        self.connect((self.unpack,       0), (self.correlator,  0))
        self.connect((self.correlator,   0), (self.repack,      0))
        self.connect((self.repack,       0), (self.crc_check,   0))
        self.connect((self.crc_check,    0), (self.udp_sink,    0))


def main():
    tb = RX_GNU_radio()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT,  sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()
    print("[RX] Flowgraph running.")
    print("[RX] In another terminal run:")
    print("[RX]   ffplay -fflags nobuffer -flags low_delay -framedrop -i udp://127.0.0.1:10001")
    print("[RX] Press Enter to quit.")
    try:
        input()
    except EOFError:
        signal.pause()
    tb.stop()
    tb.wait()

if __name__ == '__main__':
    main()