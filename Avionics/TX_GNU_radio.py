#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# IREC 2026 Avionics — TX Flowgraph
# Pi → PlutoSDR (192.168.3.1) @ 915 MHz
# Receives MPEG-TS from LiveVideo.py via UDP port 9000

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from gnuradio import blocks, digital, gr, network
from gnuradio.filter import firdes
from gnuradio.fft import window
from gnuradio import iio
import sys, signal, threading

class TX_GNU_radio(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "IREC TX", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables — must match RX exactly
        ##################################################
        self.samp_rate  = 1_500_000
        self.sps        = 2          # samples per symbol
        self.excess_bw  = 0.35
        self.pkt_len    = 1316       # match UDP packet size from LiveVideo.py

        # QPSK constellation — must match RX
        self.qpsk = digital.constellation_rect(
            [0.707+0.707j, -0.707+0.707j, -0.707-0.707j, 0.707-0.707j],
            [0, 1, 2, 3], 4, 2, 2, 1, 1).base()

        # Access code — must match RX correlate block exactly
        self.access_code = '11011011001100001111011100000011'

        ##################################################
        # Blocks
        ##################################################

        # 1. Receive MPEG-TS UDP from LiveVideo.py
        self.udp_source = network.udp_source(
            gr.sizeof_char, 1,
            9000,    # port
            0,       # header type: none
            self.pkt_len,
            True,    # notify missed frames
            False,   # IPv6
            False)   # src zeros if no data — keep False

        # 2. Tag stream into packets matching pkt_len
        self.stream_tagger = blocks.stream_to_tagged_stream(
            gr.sizeof_char, 1, self.pkt_len, "packet_len")

        # 3. CRC32 append
        self.crc_append = digital.crc32_bb(False, "packet_len", True)

        # 4. Protocol formatter — inserts access code header
        self.header_format = digital.header_format_default(
            self.access_code, 0, 1)
        self.formatter = digital.protocol_formatter_bb(
            self.header_format, "packet_len")

        # 5. Mux header + payload
        self.mux = blocks.tagged_stream_mux(
            gr.sizeof_char * 1, "packet_len", 0)

        # 6. QPSK modulator with differential encoding
        self.modulator = digital.generic_mod(
            constellation=self.qpsk,
            differential=True,
            samples_per_symbol=self.sps,
            pre_diff_code=True,
            excess_bw=self.excess_bw,
            verbose=False,
            log=False,
            truncate=False)

        # 7. PlutoSDR sink
        self.pluto_sink = iio.fmcomms2_sink_fc32(
            '192.168.3.1',
            [True, True], 32768, False)
        self.pluto_sink.set_len_tag_key('')
        self.pluto_sink.set_bandwidth(20_000_000)
        self.pluto_sink.set_frequency(915_000_000)
        self.pluto_sink.set_samplerate(self.samp_rate)
        self.pluto_sink.set_attenuation(0, 30)
        self.pluto_sink.set_filter_params('Auto', '', 0, 0)

        ##################################################
        # Connections
        ##################################################
        self.connect((self.udp_source,    0), (self.stream_tagger, 0))
        self.connect((self.stream_tagger, 0), (self.crc_append,    0))
        self.connect((self.crc_append,    0), (self.formatter,     0))
        self.connect((self.crc_append,    0), (self.mux,           1))
        self.connect((self.formatter,     0), (self.mux,           0))
        self.connect((self.mux,           0), (self.modulator,     0))
        self.connect((self.modulator,     0), (self.pluto_sink,    0))


def main():
    tb = TX_GNU_radio()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT,  sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()
    print("[TX] Flowgraph running. Press Enter to quit.")
    try:
        input()
    except EOFError:
        pass
    tb.stop()
    tb.wait()

if __name__ == '__main__':
    main()