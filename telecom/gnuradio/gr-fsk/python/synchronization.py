#!/usr/bin/env python
#
# Copyright 2021 UCLouvain.
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

from distutils.version import LooseVersion

import numpy as np
import pmt
from gnuradio import gr
from scipy.signal import savgol_filter

from .utils import timeit


@timeit
def old_cfo_estimation(y, B, R, Fdev, N_Moose=2):
    """
    Estimates the CFO based on the received signal.
    Estimates CFO using Moose algorithm, on first samples of preamble.

    :param y: The received signal, (N * R,).
    :param B: Bitrate [bits/sec]
    :param R: oversample factor (typically = 8)
    :param Fdev: Frequency deviation [Hz] ( = Bitrate/4)
    :param N_Moose: N parameter in Moose algorithm (max should be total bits per preamble / 2)
        default to 2 (low accuracy and low chance of ambiguity)
    :return: The estimated CFO.
    """
    # extract 2 blocks of size N*R at the start of y

    # apply the Moose algorithm on these two blocks to estimate the CFO
    N_t = N_Moose * R
    T = 1 / B # 1/Bitrate
    
    alpha_est = np.vdot(y[:N_t], y[N_t:2*N_t])
    
    cfo_est = np.angle(alpha_est) * R / (2 * np.pi * N_t * T)

    return cfo_est


@timeit
def cfo_estimation(y, B, R, Fdev, N_Moose=2):
    """
    Estimates the CFO based on the received signal.
    Estimates CFO using Moose algorithm, on first samples of preamble.

    :param y: The received signal, (N * R,).
    :param B: Bitrate [bits/sec]
    :param R: oversample factor (typically = 8)
    :param Fdev: Frequency deviation [Hz] ( = Bitrate/4)
    :param N_Moose: N parameter in Moose algorithm (not used in this function)
    :return: The estimated CFO.
    """
    # extract 2 blocks of size N*R at the start of y

    # apply the Moose algorithm on these two blocks to estimate the CFO
    N_Moose_list = [2, 4, 8, 16] # max should be total bits per preamble / 2
    T = 1 / B # 1/Bitrate

    first_est = True
    cfo_est_off = 0.

    for N_Moose in N_Moose_list:
        N_t = N_Moose * R
        alpha_est = np.vdot(y[:N_t], y[N_t:2*N_t])
        new_cfo_est = np.angle(alpha_est) * R / (2 * np.pi * N_t * T)

        if first_est:
            first_est = not first_est
        elif abs(cfo_est - new_cfo_est) > 1/(2*N_Moose*T): # Ambiguity detected
            cfo_est_off += np.sign(cfo_est) * 1 / (N_Moose*T)
        cfo_est = new_cfo_est
    
    return cfo_est + cfo_est_off


@timeit
def old_sto_estimation(y, B, R, Fdev):
    """
    Estimate symbol timing (fractional) based on phase shifts
    """
    phase_function = np.unwrap(np.angle(y))
    phase_derivative_sign = phase_function[1:] - phase_function[:-1]
    sign_derivative = np.abs(phase_derivative_sign[1:] - phase_derivative_sign[:-1])

    sum_der_saved = -np.inf
    save_i = 0

    for i in range(0, R):
        sum_der = np.sum(sign_derivative[i::R])

        if sum_der > sum_der_saved:
            sum_der_saved = sum_der
            save_i = i

    return np.mod(save_i + 1, R)


@timeit
def sto_estimation(y, B, R, Fdev):
    """
    Estimate symbol timing (fractional) based on phase shifts
    """
    phase_function = np.unwrap(np.angle(y))
    phase_derivative_1 = savgol_filter(phase_function, window_length=5, polyorder=3, deriv=1)
    phase_derivative_2 = np.abs(savgol_filter(phase_function, window_length=5, polyorder=3, deriv=2))
    
    sum_der_saved = -np.inf
    save_i = 0
    for i in range(0, R):
        sum_der = np.sum(phase_derivative_2[i::R])  # Sum every R samples

        if sum_der > sum_der_saved:
            sum_der_saved = sum_der
            save_i = i

    return np.mod(save_i + 1, R)


class synchronization(gr.basic_block):
    """
    docstring for block synchronization
    """

    def __init__(self, drate, fdev, fsamp, hdr_len, packet_len, tx_power, N_Moose, old_sync):
        self.drate = drate
        self.fdev = fdev
        self.fsamp = fsamp
        self.osr = int(fsamp / drate)
        self.hdr_len = hdr_len
        self.packet_len = packet_len  # in bytes
        self.estimated_noise_power = 1e-5
        self.tx_power = tx_power
        self.N_Moose = N_Moose
        self.old_sync = bool(old_sync)

        if old_sync:
            self.cfo_estimation = old_cfo_estimation
            self.sto_estimation = old_sto_estimation
        else:
            self.cfo_estimation = cfo_estimation
            self.sto_estimation = sto_estimation

        # Remaining number of samples in the current packet
        self.rem_samples = 0
        self.sto = 0
        self.cfo = 0.0
        self.t0 = 0.0
        self.power_est = None

        gr.basic_block.__init__(
            self, name="Synchronization", in_sig=[np.complex64], out_sig=[np.complex64]
        )

        self.message_port_register_in(pmt.intern("noisePow"))
        self.set_msg_handler(pmt.intern("noisePow"), self.handle_msg)
        
        self.message_port_register_out(pmt.intern("syncMetrics"))
        self.message_port_register_out(pmt.intern("powerMetrics"))

        self.gr_version = gr.version()

        # Redefine function based on version
        if LooseVersion(self.gr_version) < LooseVersion("3.9.0"):
            self.forecast = self.forecast_v38
        else:
            self.forecast = self.forecast_v310

    def forecast_v38(self, noutput_items, ninput_items_required):
        """
        input items are samples (with oversampling factor)
        output items are samples (with oversampling factor)
        """
        if self.rem_samples == 0:  # looking for a new packet
            ninput_items_required[0] = min(
                8000, 8 * self.osr * (self.packet_len + 1) + self.osr
            )  # enough samples to find a header inside
        else:  # processing a previously found packet
            ninput_items_required[0] = (
                noutput_items  # pass remaining samples in packet to next block
            )

    def forecast_v310(self, noutput_items, ninputs):
        """
        forecast is only called from a general block
        this is the default implementation
        """
        ninput_items_required = [0] * ninputs
        for i in range(ninputs):
            if self.rem_samples == 0:  # looking for a new packet
                ninput_items_required[i] = min(
                    8000, 8 * self.osr * (self.packet_len + 1) + self.osr
                )  # enough samples to find a header inside
            else:  # processing a previously found packet
                ninput_items_required[i] = (
                    noutput_items  # pass remaining samples in packet to next block
                )

        return ninput_items_required

    def handle_msg(self, msg):
        self.estimated_noise_power = pmt.to_double(pmt.dict_ref(msg, pmt.intern("mean_noise_power"), pmt.PMT_NIL))

    def set_tx_power(self, tx_power):
        self.tx_power = tx_power

    @timeit('synchronization/')
    def general_work(self, input_items, output_items):
        if self.rem_samples == 0:  # new packet to process, compute the CFO and STO
            y = input_items[0][: self.hdr_len * 8 * self.osr]
            self.cfo = self.cfo_estimation(y, self.drate, self.osr, self.fdev, self.N_Moose)

            # Correct CFO in preamble
            t = np.arange(len(y)) / (self.drate * self.osr)
            y_cfo = np.exp(-1j * 2 * np.pi * self.cfo * t) * y
            self.t0 = t[-1]

            self.sto = self.sto_estimation(y_cfo, self.drate, self.osr, self.fdev)

            self.power_est = None
            self.rem_samples = (self.packet_len + 1) * 8 * self.osr

            sync_metrics = pmt.make_dict()
            sync_metrics = pmt.dict_add(sync_metrics, pmt.intern("preamble_start"), pmt.from_long(self.nitems_read(0) + self.sto))
            sync_metrics = pmt.dict_add(sync_metrics, pmt.intern("cfo"), pmt.from_double(self.cfo))
            sync_metrics = pmt.dict_add(sync_metrics, pmt.intern("sto"), pmt.from_long(self.sto))
            self.message_port_pub(pmt.intern("syncMetrics"), sync_metrics)

            self.consume_each(self.sto)  # drop *sto* samples to align the buffer
            return 0  # ... but we do not transmit data to the demodulation stage
        else:
            win_size = min(len(output_items[0]), self.rem_samples)
            y = input_items[0][:win_size]

            if self.power_est is None and win_size >= 256:
                self.power_est = np.var(y)
                SNR_est = (self.power_est - self.estimated_noise_power) / self.estimated_noise_power
                power_metrics = pmt.make_dict()
                power_metrics = pmt.dict_add(power_metrics, pmt.intern("snr"), pmt.from_double(10 * np.log10(SNR_est)))
                power_metrics = pmt.dict_add(power_metrics, pmt.intern("rxp"), pmt.from_double(10 * np.log10(self.power_est)))
                power_metrics = pmt.dict_add(power_metrics, pmt.intern("txp"), pmt.from_double(self.tx_power))
                self.message_port_pub(pmt.intern("powerMetrics"), power_metrics)

            # Correct CFO before transferring samples to demodulation stage
            t = self.t0 + np.arange(1, len(y) + 1) / (self.drate * self.osr)
            y_corr = np.exp(-1j * 2 * np.pi * self.cfo * t) * y
            self.t0 = t[
                -1
            ]  # we keep the CFO correction continuous across buffer chunks

            output_items[0][:win_size] = y_corr

            self.rem_samples -= win_size
            if (
                self.rem_samples == 0
            ):  # Thow away the extra OSR samples from the preamble detection stage
                self.consume_each(win_size + self.osr - self.sto)
            else:
                self.consume_each(win_size)

            return win_size
