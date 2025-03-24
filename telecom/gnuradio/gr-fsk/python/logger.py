# -*- coding: utf-8 -*-
"""
Created on Tue Mar 18 09:29:36 2025

@author: carbonnelleg
"""

from distutils.version import LooseVersion

from collections import deque
from gnuradio import gr
import numpy as np
import pmt
import logging

from .utils import get_measurements_logger, timeit

class logger(gr.basic_block):
    """
    docstring for block synchronization
    """

    def __init__(self, payload_len, print_payload, print_metrics, meas_type, save_measurements):
        # Make grc block
        self.payload_len = payload_len
        self.print_payload = print_payload
        self.print_metrics = print_metrics
        self.meas_type = meas_type
        self.save_measurements = save_measurements
        gr.basic_block.__init__(
            self,
            name="Logger",
            in_sig=[(np.uint8, self.payload_len)],
            out_sig=None,
        )

        # Msg attributes
        # Noise
        self.n_est = 0
        self.noise_est_vec = pmt.PMT_NIL
        self.mean_noise_power = 0.0
        self.dc_offset_vec = pmt.PMT_NIL
        self.n_samples_vec = pmt.PMT_NIL
        # Sync
        self.preamble_start = 0
        self.cfo = 0.0
        self.sto = 0
        # Power
        self.snr = 0.0
        self.rxp = 0.0
        self.txp = 0.0
        # Payload Metadata
        self.nb_packet = 0
        self.is_correct = False
        self.nb_error = 0
        self.crc = 0

        # Msg queues
        self.sync_queue = deque()
        self.power_queue = deque()

        self.measurements_logger = get_measurements_logger(self.meas_type)
        
        self.message_port_register_in(pmt.intern("noiseMetrics"))
        self.set_msg_handler(pmt.intern("noiseMetrics"), self.parse_noise_metrics)
        self.message_port_register_in(pmt.intern("syncMetrics"))
        self.set_msg_handler(pmt.intern("syncMetrics"), self.parse_sync_metrics)
        self.message_port_register_in(pmt.intern("powerMetrics"))
        self.set_msg_handler(pmt.intern("powerMetrics"), self.parse_power_metrics)
        self.message_port_register_in(pmt.intern("payloadMetaData"))
        self.set_msg_handler(pmt.intern("payloadMetaData"), self.parse_payload_metadata)

        # Redefine function based on version
        self.gr_version = gr.version()
        if LooseVersion(self.gr_version) < LooseVersion("3.9.0"):
            self.forecast = self.forecast_v38
        else:
            self.forecast = self.forecast_v310
    
    def parse_noise_metrics(self, msg):
        self.n_est = pmt.to_long(pmt.dict_ref(msg, pmt.intern("n_est"), pmt.PMT_NIL))
        self.noise_est_vec = pmt.dict_ref(msg, pmt.intern("noise_est_vec"), pmt.PMT_NIL)
        self.mean_noise_power = pmt.to_double(pmt.dict_ref(msg, pmt.intern("mean_noise_power"), pmt.PMT_NIL))
        self.dc_offset_vec = pmt.dict_ref(msg, pmt.intern("dc_offset_vec"), pmt.PMT_NIL)
        self.n_samples_vec = pmt.dict_ref(msg, pmt.intern("n_samples_vec"), pmt.PMT_NIL)

        logger = logging.getLogger("noise")

        for i in range(self.n_est):
            noise_est = pmt.to_double(pmt.vector_ref(self.noise_est_vec, i))
            noise_est_dB = 10 * np.log10(noise_est)
            dc_offset = pmt.to_double(pmt.vector_ref(self.dc_offset_vec, i))
            n_samples = pmt.to_long(pmt.vector_ref(self.n_samples_vec, i))
            logger.info(
                f"estimated noise power: {noise_est:.2e} ({noise_est_dB:.2f}dB, Noise std : {np.sqrt(noise_est):.2e}, "
                f"DC offset: {dc_offset:.2e}, calc. on {n_samples} samples)"
            )
            if self.save_measurements:
                self.measurements_logger.info(
                    f"noise_est={noise_est}, dc_offset={dc_offset}, n_samples={n_samples}"
                )
        logger.info(
            f"===== > Final estimated noise power: {self.mean_noise_power:.2e} ({10 * np.log10(self.mean_noise_power):.2f}dB, "
            f"Noise std : {np.sqrt(self.mean_noise_power):.2e})"
        )
        if self.save_measurements:
            self.measurements_logger.info(
                f"mean_noise_power={self.mean_noise_power}"
            )

    def parse_sync_metrics(self, msg):
        preamble_start = pmt.to_long(pmt.dict_ref(msg, pmt.intern("preamble_start"), pmt.PMT_NIL))
        cfo = pmt.to_double(pmt.dict_ref(msg, pmt.intern("cfo"), pmt.PMT_NIL))
        sto = pmt.to_long(pmt.dict_ref(msg, pmt.intern("sto"), pmt.PMT_NIL))
        self.sync_queue.append((preamble_start, cfo, sto))
    
    def parse_power_metrics(self, msg):
        snr = pmt.to_double(pmt.dict_ref(msg, pmt.intern("snr"), pmt.PMT_NIL))
        rxp = pmt.to_double(pmt.dict_ref(msg, pmt.intern("rxp"), pmt.PMT_NIL))
        txp = pmt.to_double(pmt.dict_ref(msg, pmt.intern("txp"), pmt.PMT_NIL))
        self.power_queue.append((snr, rxp, txp))

    def parse_payload_metadata(self, msg):
        self.nb_packet = pmt.to_long(pmt.dict_ref(msg, pmt.intern("nb_packet"), pmt.PMT_NIL))
        self.is_correct = bool(pmt.to_long(pmt.dict_ref(msg, pmt.intern("is_correct"), pmt.PMT_NIL)))
        self.nb_error = pmt.to_long(pmt.dict_ref(msg, pmt.intern("nb_error"), pmt.PMT_NIL))
        self.crc = pmt.to_long(pmt.dict_ref(msg, pmt.intern("crc"), pmt.PMT_NIL))
        
        # Retrieve the oldest synchronized values
        if self.sync_queue and self.power_queue:
            self.preamble_start, self.cfo, self.sto = self.sync_queue.popleft()
            self.snr, self.rxp, self.txp = self.power_queue.popleft()
        else:
            return
    
    
    def set_print_payload(self, print_payload):
        self.print_payload = print_payload
    
    def set_print_metrics(self, print_metrics):
        self.print_metrics = print_metrics

    def set_save_measurements(self, save_measurements):
        self.save_measurements = save_measurements

    def forecast_v38(self, noutput_items, ninput_items_required):
        ninput_items_required[0] = 1

    def forecast_v310(self, noutput_items, ninputs):
        """
        forecast is only called from a general block
        this is the default implementation
        """
        ninput_items_required = [0] * ninputs
        for i in range(ninputs):
            ninput_items_required[i] = 1

        return ninput_items_required
    
    @timeit('logger/')
    def general_work(self, input_items, output_items):
        payload = input_items[0][0]
        self.consume_each(len(input_items[0]))

        # Logging received payload
        logger = logging.getLogger("payload")
        if self.is_correct:
            if self.print_payload:
                logger.info(
                    f"packet successfully demodulated: {payload} (CRC: {self.crc})"
                )
            logger.info(
                f"{self.nb_packet} packets received with {self.nb_error} error(s)"
            )
        else:
            if self.print_payload:
                logger.error(
                    f"incorrect CRC, packet dropped: {payload} (CRC: {self.crc})"
                )
            logger.info(
                f"{self.nb_packet} packets received with {self.nb_error} error(s)"
            )

        # Logging synchronization and power metrics
        if self.print_metrics:
            logger = logging.getLogger("sync")
            logger.info(
                f"new preamble detected @ {self.preamble_start} (CFO {self.cfo:.2f} Hz, STO {self.sto})"
            )
            logger = logging.getLogger("power")
            logger.info(
                f"estimated SNR: {self.snr:.2f} dB, Esti. RX power: {self.rxp:.2f} dB,  TX indicative Power: {self.txp} dB)"
            )

        # Saving measurement data if enabled
        if self.save_measurements:
            self.measurements_logger.info(
                f"packet_number={self.nb_packet}, correct={self.is_correct}, payload=[{','.join(map(str, payload))}]"
            )
            self.measurements_logger.info(f"CFO={self.cfo:.4f}, STO={self.sto}")
            self.measurements_logger.info(
                f"SNRdB={self.snr:.4f}, RXPdB={self.rxp:.4f}, TXPdB={self.txp}"
            )

        return 0
    