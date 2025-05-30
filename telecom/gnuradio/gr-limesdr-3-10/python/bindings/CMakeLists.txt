# Copyright 2020 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

########################################################################
# Check if there is C++ code at all
########################################################################
if(NOT limesdr_fpga_sources)
    MESSAGE(STATUS "No C++ sources... skipping python bindings")
    return()
endif(NOT limesdr_fpga_sources)

########################################################################
# Check for pygccxml
########################################################################
GR_PYTHON_CHECK_MODULE_RAW(
    "pygccxml"
    "import pygccxml"
    PYGCCXML_FOUND
    )

include(GrPybind)

########################################################################
# Python Bindings
########################################################################

list(APPEND limesdr_fpga_python_files
    sink_fpga_python.cc
    source_fpga_python.cc
    python_bindings.cc)



GR_PYBIND_MAKE_OOT(limesdr_fpga
   ../..
   gr::limesdr_fpga
   "${limesdr_fpga_python_files}")

install(TARGETS limesdr_fpga_python DESTINATION ${GR_PYTHON_DIR}/limesdr_fpga COMPONENT pythonapi)
