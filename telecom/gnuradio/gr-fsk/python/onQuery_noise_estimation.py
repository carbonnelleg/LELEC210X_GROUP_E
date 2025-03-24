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

class onQuery_noise_estimation(gr.basic_block):
    """
    docstring for block onQuery_noise_estimation
    """

    def query_estimation(self, query):
        if query == 1:
            self.est_counter = 1
            self.mean_noise_est = 0.0
            self.do_a_query = 1

    def __init__(self, n_samples, n_est):
        # Make grc block
        self.n_samples = n_samples
        self.n_est = n_est
        gr.basic_block.__init__(
            self, name="Noise Estimation", in_sig=[np.complex64], out_sig=None
        )

        # Define noise estimation variables
        self.mean_noise_est = 0.0
        self.est_counter = 1
        self.noise_est = 0.0
        self.do_a_query = 0

        # Define msg ports variables
        self.message_port_register_out(pmt.intern("noisePow"))
        self.est_vec = pmt.make_vector(n_est, pmt.from_double(0.0))
        self.dc_offset_vec = pmt.make_vector(n_est, pmt.from_double(0.0))
        self.n_samples_vec = pmt.make_vector(n_est, pmt.from_long(0))

        # Redefine function based on version
        self.gr_version = gr.version()
        if LooseVersion(self.gr_version) < LooseVersion("3.9.0"):
            self.forecast = self.forecast_v38
        else:
            self.forecast = self.forecast_v310

    def forecast_v38(self, noutput_items, ninput_items_required):
        ninput_items_required[0] = self.n_samples

    def forecast_v310(self, noutput_items, ninputs):
        """
        forecast is only called from a general block
        this is the default implementation
        """
        ninput_items_required = [self.n_samples] * ninputs

        return ninput_items_required

    def general_work(self, input_items, output_items):
        if self.do_a_query == 0:
            self.consume_each(len(input_items[0]))
        else:
            y = input_items[0]
            dc_offset = np.abs(np.mean(y))
            self.noise_est = np.var(y)
            pmt.vector_set(self.est_vec, self.est_counter-1, pmt.from_double(self.noise_est))
            pmt.vector_set(self.dc_offset_vec, self.est_counter-1, pmt.from_double(dc_offset))
            pmt.vector_set(self.n_samples_vec, self.est_counter-1, pmt.from_long(len(y)))
            self.consume_each(len(y))
            self.mean_noise_est += self.noise_est

            if self.est_counter == self.n_est:
                mean_noisP = self.mean_noise_est / self.est_counter
                msg = pmt.make_dict()
                msg = pmt.dict_add(msg, pmt.intern("n_est"), pmt.from_long(self.n_est))
                msg = pmt.dict_add(msg, pmt.intern("noise_est_vec"), self.est_vec)
                msg = pmt.dict_add(msg, pmt.intern("mean_noise_power"), pmt.from_double(mean_noisP))
                msg = pmt.dict_add(msg, pmt.intern("dc_offset_vec"), self.dc_offset_vec)
                msg = pmt.dict_add(msg, pmt.intern("n_samples_vec"), self.n_samples_vec)
                self.message_port_pub(pmt.intern("noisePow"), msg)

                self.est_counter = 1
                self.mean_noise_est = 0.0
                self.do_a_query = 0

            else:
                self.est_counter += 1

        return 0
