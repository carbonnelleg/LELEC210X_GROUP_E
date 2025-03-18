#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LELEC2102 - Decode Capture
# Author: UCLouvain
# GNU Radio version: 3.10.7.0

from gnuradio import blocks
import pmt
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import zeromq
import fsk




class decode_trace(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "LELEC2102 - Decode Capture", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.payload_len = payload_len = 100
        self.hdr_len = hdr_len = 8
        self.data_rate = data_rate = 50e3
        self.crc_len = crc_len = 1
        self.samp_rate = samp_rate = data_rate*8
        self.packet_len = packet_len = hdr_len+payload_len+crc_len
        self.fdev = fdev = data_rate/4
        self.estimated_noise_power = estimated_noise_power = 1
        self.detect_threshold = detect_threshold = 0.05
        self.carrier_freq = carrier_freq = 868e6

        ##################################################
        # Blocks
        ##################################################

        self.zeromq_pub_sink_0 = zeromq.pub_sink(gr.sizeof_char, payload_len, 'tcp://127.0.0.1:10000', 100, False, (-1), '', True, True)
        self.low_pass_filter_0 = filter.fir_filter_ccf(
            1,
            firdes.low_pass(
                1,
                samp_rate,
                (data_rate+fdev),
                (data_rate*1),
                window.WIN_HAMMING,
                6.76))
        self.fsk_synchronization_0 = fsk.synchronization(data_rate, fdev, samp_rate, hdr_len, packet_len, 0,True)
        self.fsk_preamble_detect_0 = fsk.preamble_detect(data_rate, fdev, samp_rate, packet_len, detect_threshold, 1)
        self.fsk_packet_parser_0 = fsk.packet_parser(hdr_len, payload_len, crc_len, [0,0,1,1,1,1,1,0,0,0,1,0,1,0,1,0,0,1,0,1,0,1,0,0,1,0,1,1,0,1,1,1], True)
        self.fsk_logger_0 = fsk.logger('capture', payload_len)
        self.fsk_demodulation_0 = fsk.demodulation(data_rate, fdev, samp_rate, payload_len, crc_len)
        self.blocks_var_to_msg_0 = blocks.var_to_msg_pair('estimated_noise_power')
        self.blocks_throttle_0 = blocks.throttle(gr.sizeof_gr_complex*1, samp_rate,True)
        self.blocks_file_source_0 = blocks.file_source(gr.sizeof_gr_complex*1, '/mnt/c/Users/gauti/OneDrive - UCL/Documents/UCL - EPL/Master/Master 1 Q2/LELEC210X/LELEC210X_GROUP_E/telecom/gnuradio/gr-fsk/misc/fsk_capture.mat', False, 0, 0)
        self.blocks_file_source_0.set_begin_tag(pmt.PMT_NIL)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.blocks_var_to_msg_0, 'msgout'), (self.fsk_logger_0, 'noisePow'))
        self.msg_connect((self.blocks_var_to_msg_0, 'msgout'), (self.fsk_synchronization_0, 'NoisePow'))
        self.msg_connect((self.fsk_packet_parser_0, 'payloadMetaData'), (self.fsk_logger_0, 'payloadMetaData'))
        self.msg_connect((self.fsk_synchronization_0, 'syncMetrics'), (self.fsk_logger_0, 'syncMetrics'))
        self.connect((self.blocks_file_source_0, 0), (self.blocks_throttle_0, 0))
        self.connect((self.blocks_throttle_0, 0), (self.low_pass_filter_0, 0))
        self.connect((self.fsk_demodulation_0, 0), (self.fsk_packet_parser_0, 0))
        self.connect((self.fsk_packet_parser_0, 0), (self.fsk_logger_0, 'payload'))
        self.connect((self.fsk_packet_parser_0, 0), (self.zeromq_pub_sink_0, 0))
        self.connect((self.fsk_preamble_detect_0, 0), (self.fsk_synchronization_0, 0))
        self.connect((self.fsk_synchronization_0, 0), (self.fsk_demodulation_0, 0))
        self.connect((self.low_pass_filter_0, 0), (self.fsk_preamble_detect_0, 0))


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
        self.set_fdev(self.data_rate/4)
        self.set_samp_rate(self.data_rate*8)
        self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.samp_rate, (self.data_rate+self.fdev), (self.data_rate*1), window.WIN_HAMMING, 6.76))

    def get_crc_len(self):
        return self.crc_len

    def set_crc_len(self, crc_len):
        self.crc_len = crc_len
        self.set_packet_len(self.hdr_len+self.payload_len+self.crc_len)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.blocks_throttle_0.set_sample_rate(self.samp_rate)
        self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.samp_rate, (self.data_rate+self.fdev), (self.data_rate*1), window.WIN_HAMMING, 6.76))

    def get_packet_len(self):
        return self.packet_len

    def set_packet_len(self, packet_len):
        self.packet_len = packet_len

    def get_fdev(self):
        return self.fdev

    def set_fdev(self, fdev):
        self.fdev = fdev
        self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.samp_rate, (self.data_rate+self.fdev), (self.data_rate*1), window.WIN_HAMMING, 6.76))

    def get_estimated_noise_power(self):
        return self.estimated_noise_power

    def set_estimated_noise_power(self, estimated_noise_power):
        self.estimated_noise_power = estimated_noise_power
        self.blocks_var_to_msg_0.variable_changed(self.estimated_noise_power)

    def get_detect_threshold(self):
        return self.detect_threshold

    def set_detect_threshold(self, detect_threshold):
        self.detect_threshold = detect_threshold
        self.fsk_preamble_detect_0.set_threshold(self.detect_threshold)

    def get_carrier_freq(self):
        return self.carrier_freq

    def set_carrier_freq(self, carrier_freq):
        self.carrier_freq = carrier_freq




def main(top_block_cls=decode_trace, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()

    tb.wait()


if __name__ == '__main__':
    main()
