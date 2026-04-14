#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
from gnuradio import network
import configparser
import sip
import threading



class RX_GNU_radio(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Not titled yet")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "RX_GNU_radio")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self._variable_config_0_config = configparser.ConfigParser()
        self._variable_config_0_config.read('default')
        try: variable_config_0 = self._variable_config_0_config.getfloat('main', 'key')
        except: variable_config_0 = 0
        self.variable_config_0 = variable_config_0
        self.constellation_obj = constellation_obj = digital.constellation_rect([1+1j, -1+1j, -1-1j, 1-1j], [0, 1, 2, 3],
        4, 2, 2, 1, 1).base()
        self.SampleRate = SampleRate = 1_000_000
        self.Loop_Band_width = Loop_Band_width = .01
        self.Freq_shift = Freq_shift = 0
        self.Bit_Slip = Bit_Slip = 0

        ##################################################
        # Blocks
        ##################################################

        self._Loop_Band_width_range = qtgui.Range(0, .1, .001, .01, 200)
        self._Loop_Band_width_win = qtgui.RangeWidget(self._Loop_Band_width_range, self.set_Loop_Band_width, "Loop_Band_width", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._Loop_Band_width_win)
        self._Freq_shift_range = qtgui.Range(-20000, 20000, 50, 0, 200)
        self._Freq_shift_win = qtgui.RangeWidget(self._Freq_shift_range, self.set_Freq_shift, "Freq_shift", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._Freq_shift_win)
        self._Bit_Slip_range = qtgui.Range(0, 7, 1, 0, 200)
        self._Bit_Slip_win = qtgui.RangeWidget(self._Bit_Slip_range, self.set_Bit_Slip, "Bit_Slip", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._Bit_Slip_win)
        self.qtgui_time_sink_x_0 = qtgui.time_sink_c(
            1024, #size
            SampleRate, #samp_rate
            "", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_0.set_update_time(0.10)
        self.qtgui_time_sink_x_0.set_y_axis(-1, 1)

        self.qtgui_time_sink_x_0.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_0.enable_tags(True)
        self.qtgui_time_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_0.enable_autoscale(False)
        self.qtgui_time_sink_x_0.enable_grid(False)
        self.qtgui_time_sink_x_0.enable_axis_labels(True)
        self.qtgui_time_sink_x_0.enable_control_panel(False)
        self.qtgui_time_sink_x_0.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(2):
            if len(labels[i]) == 0:
                if (i % 2 == 0):
                    self.qtgui_time_sink_x_0.set_line_label(i, "Re{{Data {0}}}".format(i/2))
                else:
                    self.qtgui_time_sink_x_0.set_line_label(i, "Im{{Data {0}}}".format(i/2))
            else:
                self.qtgui_time_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_time_sink_x_0_win)
        self.qtgui_const_sink_x_0 = qtgui.const_sink_c(
            1024, #size
            "", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_const_sink_x_0.set_update_time(0.10)
        self.qtgui_const_sink_x_0.set_y_axis((-1), 1)
        self.qtgui_const_sink_x_0.set_x_axis((-1), 1)
        self.qtgui_const_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_0.enable_autoscale(False)
        self.qtgui_const_sink_x_0.enable_grid(False)
        self.qtgui_const_sink_x_0.enable_axis_labels(True)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_const_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_const_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_const_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_const_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_const_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_const_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_const_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_const_sink_x_0_win = sip.wrapinstance(self.qtgui_const_sink_x_0.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_const_sink_x_0_win)
        self.network_udp_sink_0 = network.udp_sink(gr.sizeof_char, 1, '127.0.0.1', 10001, 0, 1472, False)
        self.low_pass_filter_0 = filter.fir_filter_ccf(
            1,
            firdes.low_pass(
                1,
                SampleRate,
                500000,
                100000,
                window.WIN_HAMMING,
                6.76))
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32('ip:192.168.4.1' if 'ip:192.168.4.1' else iio.get_pluto_uri(), [True, True], 32768)
        self.iio_pluto_source_0.set_len_tag_key('packet_len')
        self.iio_pluto_source_0.set_frequency((915000000 + Freq_shift))
        self.iio_pluto_source_0.set_samplerate(SampleRate)
        self.iio_pluto_source_0.set_gain_mode(0, 'manual')
        self.iio_pluto_source_0.set_gain(0, 10)
        self.iio_pluto_source_0.set_quadrature(True)
        self.iio_pluto_source_0.set_rfdc(True)
        self.iio_pluto_source_0.set_bbdc(True)
        self.iio_pluto_source_0.set_filter_params('Auto', '', 0, 0)
        self.digital_pfb_clock_sync_xxx_0 = digital.pfb_clock_sync_ccf(4, Loop_Band_width, firdes.root_raised_cosine(32, 32, 1.0, 0.35, 11*32), 32, 0, 1.5, 1)
        self.digital_diff_decoder_bb_0 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.digital_costas_loop_cc_0 = digital.costas_loop_cc(Loop_Band_width, 4, False)
        self.digital_constellation_decoder_cb_0 = digital.constellation_decoder_cb(constellation_obj)
        self.blocks_skiphead_0 = blocks.skiphead(gr.sizeof_char*1, Bit_Slip)
        self.blocks_repack_bits_bb_0 = blocks.repack_bits_bb(1, 8, "", False, gr.GR_MSB_FIRST)
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_char*1, '/home/jacob/Code/IREC_2026/Avionics/rocket_flight_raw.ts', False)
        self.blocks_file_sink_0.set_unbuffered(False)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_repack_bits_bb_0, 0), (self.blocks_file_sink_0, 0))
        self.connect((self.blocks_repack_bits_bb_0, 0), (self.network_udp_sink_0, 0))
        self.connect((self.blocks_skiphead_0, 0), (self.blocks_repack_bits_bb_0, 0))
        self.connect((self.digital_constellation_decoder_cb_0, 0), (self.digital_diff_decoder_bb_0, 0))
        self.connect((self.digital_costas_loop_cc_0, 0), (self.digital_constellation_decoder_cb_0, 0))
        self.connect((self.digital_costas_loop_cc_0, 0), (self.qtgui_const_sink_x_0, 0))
        self.connect((self.digital_diff_decoder_bb_0, 0), (self.blocks_skiphead_0, 0))
        self.connect((self.digital_pfb_clock_sync_xxx_0, 0), (self.digital_costas_loop_cc_0, 0))
        self.connect((self.digital_pfb_clock_sync_xxx_0, 0), (self.qtgui_time_sink_x_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.low_pass_filter_0, 0))
        self.connect((self.low_pass_filter_0, 0), (self.digital_pfb_clock_sync_xxx_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "RX_GNU_radio")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_variable_config_0(self):
        return self.variable_config_0

    def set_variable_config_0(self, variable_config_0):
        self.variable_config_0 = variable_config_0

    def get_constellation_obj(self):
        return self.constellation_obj

    def set_constellation_obj(self, constellation_obj):
        self.constellation_obj = constellation_obj
        self.digital_constellation_decoder_cb_0.set_constellation(self.constellation_obj)

    def get_SampleRate(self):
        return self.SampleRate

    def set_SampleRate(self, SampleRate):
        self.SampleRate = SampleRate
        self.iio_pluto_source_0.set_samplerate(self.SampleRate)
        self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.SampleRate, 500000, 100000, window.WIN_HAMMING, 6.76))
        self.qtgui_time_sink_x_0.set_samp_rate(self.SampleRate)

    def get_Loop_Band_width(self):
        return self.Loop_Band_width

    def set_Loop_Band_width(self, Loop_Band_width):
        self.Loop_Band_width = Loop_Band_width
        self.digital_costas_loop_cc_0.set_loop_bandwidth(self.Loop_Band_width)
        self.digital_pfb_clock_sync_xxx_0.set_loop_bandwidth(self.Loop_Band_width)

    def get_Freq_shift(self):
        return self.Freq_shift

    def set_Freq_shift(self, Freq_shift):
        self.Freq_shift = Freq_shift
        self.iio_pluto_source_0.set_frequency((915000000 + self.Freq_shift))

    def get_Bit_Slip(self):
        return self.Bit_Slip

    def set_Bit_Slip(self, Bit_Slip):
        self.Bit_Slip = Bit_Slip




def main(top_block_cls=RX_GNU_radio, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
