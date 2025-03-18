#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LELEC2102 - Decode SDR with FPGA
# Author: UCLouvain
# GNU Radio version: 3.10.7.0

from packaging.version import Version as StrictVersion
from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import eng_notation
from gnuradio import filter
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import zeromq
from gnuradio.qtgui import Range, RangeWidget
from PyQt5 import QtCore
import fsk
import limesdr_fpga



class eval_limesdr_fpga(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "LELEC2102 - Decode SDR with FPGA", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("LELEC2102 - Decode SDR with FPGA")
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

        self.settings = Qt.QSettings("GNU Radio", "eval_limesdr_fpga")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.n_melvecs = n_melvecs = 20
        self.melvec_length = melvec_length = 20
        self.spectrogram_len = spectrogram_len = n_melvecs*melvec_length*2
        self.payload_len = payload_len = spectrogram_len
        self.hdr_len = hdr_len = 8
        self.data_rate = data_rate = 50e3
        self.crc_len = crc_len = 1
        self.tx_power = tx_power = 0
        self.save_measurements = save_measurements = 1
        self.samp_rate = samp_rate = data_rate*8
        self.rx_gain = rx_gain = 10
        self.print_payload = print_payload = 1
        self.print_metrics = print_metrics = 1
        self.packet_len = packet_len = hdr_len+payload_len+crc_len
        self.noiseQuery = noiseQuery = 0
        self.fdev = fdev = data_rate/2
        self.carrier_freq = carrier_freq = 868e6
        self.K_threshold = K_threshold = 7
        self.Enable_detection = Enable_detection = 0

        ##################################################
        # Blocks
        ##################################################

        self._tx_power_tool_bar = Qt.QToolBar(self)
        self._tx_power_tool_bar.addWidget(Qt.QLabel("TX power used (no impact, just for logging)" + ": "))
        self._tx_power_line_edit = Qt.QLineEdit(str(self.tx_power))
        self._tx_power_tool_bar.addWidget(self._tx_power_line_edit)
        self._tx_power_line_edit.returnPressed.connect(
            lambda: self.set_tx_power(int(str(self._tx_power_line_edit.text()))))
        self.top_layout.addWidget(self._tx_power_tool_bar)
        _save_measurements_check_box = Qt.QCheckBox("'save_measurements'")
        self._save_measurements_choices = {True: 1, False: 0}
        self._save_measurements_choices_inv = dict((v,k) for k,v in self._save_measurements_choices.items())
        self._save_measurements_callback = lambda i: Qt.QMetaObject.invokeMethod(_save_measurements_check_box, "setChecked", Qt.Q_ARG("bool", self._save_measurements_choices_inv[i]))
        self._save_measurements_callback(self.save_measurements)
        _save_measurements_check_box.stateChanged.connect(lambda i: self.set_save_measurements(self._save_measurements_choices[bool(i)]))
        self.top_layout.addWidget(_save_measurements_check_box)
        self._rx_gain_range = Range(0, 73, 1, 10, 200)
        self._rx_gain_win = RangeWidget(self._rx_gain_range, self.set_rx_gain, "'rx_gain'", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._rx_gain_win)
        _print_payload_check_box = Qt.QCheckBox("'print_payload'")
        self._print_payload_choices = {True: 1, False: 0}
        self._print_payload_choices_inv = dict((v,k) for k,v in self._print_payload_choices.items())
        self._print_payload_callback = lambda i: Qt.QMetaObject.invokeMethod(_print_payload_check_box, "setChecked", Qt.Q_ARG("bool", self._print_payload_choices_inv[i]))
        self._print_payload_callback(self.print_payload)
        _print_payload_check_box.stateChanged.connect(lambda i: self.set_print_payload(self._print_payload_choices[bool(i)]))
        self.top_layout.addWidget(_print_payload_check_box)
        _print_metrics_check_box = Qt.QCheckBox("'print_metrics'")
        self._print_metrics_choices = {True: 1, False: 0}
        self._print_metrics_choices_inv = dict((v,k) for k,v in self._print_metrics_choices.items())
        self._print_metrics_callback = lambda i: Qt.QMetaObject.invokeMethod(_print_metrics_check_box, "setChecked", Qt.Q_ARG("bool", self._print_metrics_choices_inv[i]))
        self._print_metrics_callback(self.print_metrics)
        _print_metrics_check_box.stateChanged.connect(lambda i: self.set_print_metrics(self._print_metrics_choices[bool(i)]))
        self.top_layout.addWidget(_print_metrics_check_box)
        _noiseQuery_push_button = Qt.QPushButton('Noise estimation query')
        _noiseQuery_push_button = Qt.QPushButton('Noise estimation query')
        self._noiseQuery_choices = {'Pressed': 1, 'Released': 0}
        _noiseQuery_push_button.pressed.connect(lambda: self.set_noiseQuery(self._noiseQuery_choices['Pressed']))
        _noiseQuery_push_button.released.connect(lambda: self.set_noiseQuery(self._noiseQuery_choices['Released']))
        self.top_layout.addWidget(_noiseQuery_push_button)
        self._K_threshold_range = Range(1, 254, 1, 7, 200)
        self._K_threshold_win = RangeWidget(self._K_threshold_range, self.set_K_threshold, "K factor for threshold", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._K_threshold_win)
        _Enable_detection_check_box = Qt.QCheckBox("'Enable_detection'")
        self._Enable_detection_choices = {True: 1, False: 0}
        self._Enable_detection_choices_inv = dict((v,k) for k,v in self._Enable_detection_choices.items())
        self._Enable_detection_callback = lambda i: Qt.QMetaObject.invokeMethod(_Enable_detection_check_box, "setChecked", Qt.Q_ARG("bool", self._Enable_detection_choices_inv[i]))
        self._Enable_detection_callback(self.Enable_detection)
        _Enable_detection_check_box.stateChanged.connect(lambda i: self.set_Enable_detection(self._Enable_detection_choices[bool(i)]))
        self.top_layout.addWidget(_Enable_detection_check_box)
        self.zeromq_pub_sink_0 = zeromq.pub_sink(gr.sizeof_char, payload_len, 'tcp://127.0.0.1:10000', 100, False, (-1), '', True, True)
        self.limesdr_fpga_source_0 = limesdr_fpga.source_fpga('', 0, '', False)


        self.limesdr_fpga_source_0.set_sample_rate(samp_rate)


        self.limesdr_fpga_source_0.set_center_freq(carrier_freq, 0)

        self.limesdr_fpga_source_0.set_bandwidth(1.5e6, 0)


        self.limesdr_fpga_source_0.set_digital_filter(samp_rate, 0)


        self.limesdr_fpga_source_0.set_gain(rx_gain, 0)


        self.limesdr_fpga_source_0.set_antenna(255, 0)


        self.limesdr_fpga_source_0.calibrate(2.5e6, 0)






        self.limesdr_fpga_source_0.set_dspcfg_preamble(((packet_len+1)*8*int(samp_rate/data_rate)+int(samp_rate/data_rate)), K_threshold, Enable_detection)
        self.fsk_synchronization_0 = fsk.synchronization(data_rate, fdev, samp_rate, hdr_len, packet_len, tx_power)
        self.fsk_packet_parser_0 = fsk.packet_parser(hdr_len, payload_len, crc_len, [0,0,1,1,1,1,1,0,0,0,1,0,1,0,1,0,0,1,0,1,0,1,0,0,1,0,1,1,0,1,1,1])
        self.fsk_onQuery_noise_estimation_0 = fsk.onQuery_noise_estimation(1024,10,noiseQuery)
        self.fsk_logger_0 = fsk.logger(payload_len, print_payload, print_metrics, 'eval_radio', save_measurements)
        self.fsk_flag_detector_0 = fsk.flag_detector(data_rate,  samp_rate, packet_len, Enable_detection)
        self.fsk_demodulation_0 = fsk.demodulation(data_rate, fdev, samp_rate, payload_len, crc_len)
        self.dc_blocker_xx_0 = filter.dc_blocker_cc(1024, True)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.fsk_onQuery_noise_estimation_0, 'noisePow'), (self.fsk_synchronization_0, 'noisePow'))
        self.msg_connect((self.fsk_packet_parser_0, 'payloadMetaData'), (self.fsk_logger_0, 'payloadMetaData'))
        self.msg_connect((self.fsk_synchronization_0, 'syncMetrics'), (self.fsk_logger_0, 'syncMetrics'))
        self.msg_connect((self.fsk_synchronization_0, 'powerMetrics'), (self.fsk_logger_0, 'powerMetrics'))
        self.connect((self.dc_blocker_xx_0, 0), (self.fsk_flag_detector_0, 0))
        self.connect((self.dc_blocker_xx_0, 0), (self.fsk_onQuery_noise_estimation_0, 0))
        self.connect((self.fsk_demodulation_0, 0), (self.fsk_packet_parser_0, 0))
        self.connect((self.fsk_flag_detector_0, 0), (self.fsk_synchronization_0, 0))
        self.connect((self.fsk_packet_parser_0, 1), (self.fsk_logger_0, 0))
        self.connect((self.fsk_packet_parser_0, 0), (self.zeromq_pub_sink_0, 0))
        self.connect((self.fsk_synchronization_0, 0), (self.fsk_demodulation_0, 0))
        self.connect((self.limesdr_fpga_source_0, 0), (self.dc_blocker_xx_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "eval_limesdr_fpga")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_n_melvecs(self):
        return self.n_melvecs

    def set_n_melvecs(self, n_melvecs):
        self.n_melvecs = n_melvecs
        self.set_spectrogram_len(self.n_melvecs*self.melvec_length*2)

    def get_melvec_length(self):
        return self.melvec_length

    def set_melvec_length(self, melvec_length):
        self.melvec_length = melvec_length
        self.set_spectrogram_len(self.n_melvecs*self.melvec_length*2)

    def get_spectrogram_len(self):
        return self.spectrogram_len

    def set_spectrogram_len(self, spectrogram_len):
        self.spectrogram_len = spectrogram_len
        self.set_payload_len(self.spectrogram_len)

    def get_payload_len(self):
        return self.payload_len

    def set_payload_len(self, payload_len):
        self.payload_len = payload_len
        self.set_packet_len(self.hdr_len+self.payload_len+self.crc_len)

    def get_hdr_len(self):
        return self.hdr_len

    def set_hdr_len(self, hdr_len):
        self.hdr_len = hdr_len
        self.set_packet_len(self.hdr_len+self.payload_len+self.crc_len)

    def get_data_rate(self):
        return self.data_rate

    def set_data_rate(self, data_rate):
        self.data_rate = data_rate
        self.set_fdev(self.data_rate/2)
        self.set_samp_rate(self.data_rate*8)
        self.limesdr_fpga_source_0.set_dspcfg_preamble(((self.packet_len+1)*8*int(self.samp_rate/self.data_rate)+int(self.samp_rate/self.data_rate)), self.K_threshold, self.Enable_detection)

    def get_crc_len(self):
        return self.crc_len

    def set_crc_len(self, crc_len):
        self.crc_len = crc_len
        self.set_packet_len(self.hdr_len+self.payload_len+self.crc_len)

    def get_tx_power(self):
        return self.tx_power

    def set_tx_power(self, tx_power):
        self.tx_power = tx_power
        Qt.QMetaObject.invokeMethod(self._tx_power_line_edit, "setText", Qt.Q_ARG("QString", str(self.tx_power)))
        self.fsk_synchronization_0.set_tx_power(self.tx_power)

    def get_save_measurements(self):
        return self.save_measurements

    def set_save_measurements(self, save_measurements):
        self.save_measurements = save_measurements
        self._save_measurements_callback(self.save_measurements)
        self.fsk_logger_0.set_save_measurements(self.save_measurements)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.limesdr_fpga_source_0.set_digital_filter(self.samp_rate, 0)
        self.limesdr_fpga_source_0.set_digital_filter(self.samp_rate, 1)
        self.limesdr_fpga_source_0.set_dspcfg_preamble(((self.packet_len+1)*8*int(self.samp_rate/self.data_rate)+int(self.samp_rate/self.data_rate)), self.K_threshold, self.Enable_detection)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.limesdr_fpga_source_0.set_gain(self.rx_gain, 0)

    def get_print_payload(self):
        return self.print_payload

    def set_print_payload(self, print_payload):
        self.print_payload = print_payload
        self._print_payload_callback(self.print_payload)
        self.fsk_logger_0.set_print_payload(self.print_payload)

    def get_print_metrics(self):
        return self.print_metrics

    def set_print_metrics(self, print_metrics):
        self.print_metrics = print_metrics
        self._print_metrics_callback(self.print_metrics)
        self.fsk_logger_0.set_print_metrics(self.print_metrics)

    def get_packet_len(self):
        return self.packet_len

    def set_packet_len(self, packet_len):
        self.packet_len = packet_len
        self.limesdr_fpga_source_0.set_dspcfg_preamble(((self.packet_len+1)*8*int(self.samp_rate/self.data_rate)+int(self.samp_rate/self.data_rate)), self.K_threshold, self.Enable_detection)

    def get_noiseQuery(self):
        return self.noiseQuery

    def set_noiseQuery(self, noiseQuery):
        self.noiseQuery = noiseQuery
        self.fsk_onQuery_noise_estimation_0.query_estimation(self.noiseQuery)

    def get_fdev(self):
        return self.fdev

    def set_fdev(self, fdev):
        self.fdev = fdev

    def get_carrier_freq(self):
        return self.carrier_freq

    def set_carrier_freq(self, carrier_freq):
        self.carrier_freq = carrier_freq
        self.limesdr_fpga_source_0.set_center_freq(self.carrier_freq, 0)

    def get_K_threshold(self):
        return self.K_threshold

    def set_K_threshold(self, K_threshold):
        self.K_threshold = K_threshold
        self.limesdr_fpga_source_0.set_dspcfg_preamble(((self.packet_len+1)*8*int(self.samp_rate/self.data_rate)+int(self.samp_rate/self.data_rate)), self.K_threshold, self.Enable_detection)

    def get_Enable_detection(self):
        return self.Enable_detection

    def set_Enable_detection(self, Enable_detection):
        self.Enable_detection = Enable_detection
        self._Enable_detection_callback(self.Enable_detection)
        self.fsk_flag_detector_0.set_enable(self.Enable_detection)
        self.limesdr_fpga_source_0.set_dspcfg_preamble(((self.packet_len+1)*8*int(self.samp_rate/self.data_rate)+int(self.samp_rate/self.data_rate)), self.K_threshold, self.Enable_detection)




def main(top_block_cls=eval_limesdr_fpga, options=None):

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

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
