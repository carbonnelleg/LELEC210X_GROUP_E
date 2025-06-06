/* -*- c++ -*- */
/*
 * Copyright 2023 Lime Microsystems info@limemicro.com
 *
 * GNU Radio is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 *
 * GNU Radio is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with GNU Radio; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifndef LOGGING_H
#define LOGGING_H

#include <lime/Logger.h>

#include <gnuradio/logger.h>

// Redirect LimeSuite logging into GNU Radio's logging.
void set_limesuite_logger(void);

// Suppress any LimeSuite logging output.
void suppress_limesuite_logging(void);

#endif