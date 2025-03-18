from distutils.version import LooseVersion

from gnuradio import gr
import numpy as np
import pmt
import logging

from .utils import get_measurements_logger

class logger(gr.basic_block):
    """
    docstring for block synchronization
    """

    def __init__(self, payload_len, print_payload, print_metrics, meas_type, save_measurements):
        self.payload_len = payload_len
        self.print_payload = print_payload
        self.print_metrics = print_metrics
        self.meas_type = meas_type
        self.save_measurements = save_measurements

        # Msg attributes
        self.preamble_start = 0
        self.cfo = 0.0
        self.sto = 0
        self.snr = 0.0
        self.rxp = 0.0
        self.txp = 0.0
        self.nb_packet = 0
        self.is_correct = False
        self.nb_error = 0
        self.crc = 0
        
        gr.basic_block.__init__(
            self,
            name="Logger",
            in_sig=[(np.uint8, self.payload_len)],
            out_sig=None,
        )

        self.logger = logging.getLogger(__name__)
        self.measurements_logger = get_measurements_logger(self.meas_type)
        
        self.message_port_register_in(pmt.intern("syncMetrics"))
        self.set_msg_handler(pmt.intern("syncMetrics"), self.parse_sync_metrics)
        self.message_port_register_in(pmt.intern("powerMetrics"))
        self.set_msg_handler(pmt.intern("powerMetrics"), self.parse_power_metrics)
        self.message_port_register_in(pmt.intern("payloadMetaData"))
        self.set_msg_handler(pmt.intern("payloadMetaData"), self.parse_payload_metadata)

        self.gr_version = gr.version()

        # Redefine function based on version
        if LooseVersion(self.gr_version) < LooseVersion("3.9.0"):
            self.forecast = self.forecast_v38
        else:
            self.forecast = self.forecast_v310
    
    def parse_sync_metrics(self, msg):
        self.preamble_start = pmt.to_long(pmt.dict_ref(msg, pmt.intern("preamble_start"), pmt.PMT_NIL))
        self.cfo = pmt.to_double(pmt.dict_ref(msg, pmt.intern("cfo"), pmt.PMT_NIL))
        self.sto = pmt.to_long(pmt.dict_ref(msg, pmt.intern("sto"), pmt.PMT_NIL))
    
    def parse_power_metrics(self, msg):
        self.snr = pmt.to_double(pmt.dict_ref(msg, pmt.intern("snr"), pmt.PMT_NIL))
        self.rxp = pmt.to_double(pmt.dict_ref(msg, pmt.intern("rxp"), pmt.PMT_NIL))
        self.txp = pmt.to_double(pmt.dict_ref(msg, pmt.intern("txp"), pmt.PMT_NIL))

    def parse_payload_metadata(self, msg):
        self.nb_packet = pmt.to_long(pmt.dict_ref(msg, pmt.intern("nb_packet"), pmt.PMT_NIL))
        self.is_correct = bool(pmt.to_long(pmt.dict_ref(msg, pmt.intern("is_correct"), pmt.PMT_NIL)))
        self.nb_error = pmt.to_long(pmt.dict_ref(msg, pmt.intern("nb_error"), pmt.PMT_NIL))
        self.crc = pmt.to_long(pmt.dict_ref(msg, pmt.intern("crc"), pmt.PMT_NIL))
    
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
    
    def general_work(self, input_items, output_items):
        payload = input_items[0][0]
        self.consume_each(1)

        # Logging received payload
        if self.is_correct:
            if self.print_payload:
                self.logger.info(
                    f"packet successfully demodulated: {payload} (CRC: {self.crc})"
                )
            self.logger.info(
                f"{self.nb_packet} packets received with {self.nb_error} error(s)"
            )
        else:
            if self.print_payload:
                self.logger.error(
                    f"incorrect CRC, packet dropped: {payload} (CRC: {self.crc})"
                )
            self.logger.info(
                f"{self.nb_packet} packets received with {self.nb_error} error(s)"
            )

        # Logging synchronization and power metrics
        if self.print_metrics:
            self.logger.info(
                f"new preamble detected @ {self.preamble_start} (CFO {self.cfo:.2f} Hz, STO {self.sto})"
            )
            self.logger.info(
                f"estimated SNR: {self.snr:.2f} dB, Esti. RX power: {self.rxp:.2e},  TX indicative Power: {self.txp} dB)"
            )

        # Saving measurement data if enabled
        if self.save_measurements:
            self.measurements_logger.info(
                f"packet_number={self.nb_packet}, correct={self.is_correct}, payload=[{','.join(map(str, payload))}]"
            )
            self.measurements_logger.info(f"CFO={self.cfo}, STO={self.sto}")
            self.measurements_logger.info(
                f"SNRdB={self.snr:.2f}, RXPdB={self.rxp:.2e}, TXPdB={self.txp}"
            )

        return 0
    