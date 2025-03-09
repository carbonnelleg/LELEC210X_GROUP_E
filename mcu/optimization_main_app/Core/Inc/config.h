/*
* config.h
* Configuration file for the MCU application
*/

#ifndef INC_CONFIG_H_
#define INC_CONFIG_H_

#include <stdio.h>

/*==============================================================================
*                          DO NOT MODIFY SECTION
*============================================================================*/

// Runtime parameters - DO NOT CHANGE
#define MAIN_APP 0
#define EVAL_RADIO 1

#define RUN_CONFIG MAIN_APP

/*==============================================================================
*                          CONFIGURABLE SECTION
*============================================================================*/

/*------------------------------------------------------------------------------
* Debug Configuration Master
*----------------------------------------------------------------------------*/

// General define for setting the MCU in no debug mode
#define NO_DEBUG 0

// Deactivate the need to use the button to trigger the system
#define NO_BUTTON 0

/*------------------------------------------------------------------------------
* System Configuration
*----------------------------------------------------------------------------*/

// General UART enable/disable (disable for low-power operation)
#define ENABLE_UART 1

// Acquisition Mode
// Set to 1 for continuous mode (start/stop on button press)
// Set to 0 for single packet mode (send one packet per button press)
#define CONTINUOUS_ACQ 1

// Acquisition Overlap mode (BUG: Line vertical at position 3 during overlap)
#define ACQ_STOP_START 0  // Stop the acquisition before starting a new one
#define ACQ_OVERLAP 1     // Overlap the acquisition (start a new one before stopping the previous one)
#define ACQ_MODE ACQ_OVERLAP  // Select either ACQ_STOP_START or ACQ_OVERLAP

/*------------------------------------------------------------------------------
* Radio & Crypto Configuration
*----------------------------------------------------------------------------*/
// Enable/disable radio communication
#define ENABLE_RADIO 1

// Cryptography Implementation Selection
#define USE_SOFTWARE_CRYPTO 0  // Performance: 521391 cycles per packet
#define USE_HARDWARE_CRYPTO 1  // Performance: 17244 cycles per packet
#define USE_CRYPTO USE_HARDWARE_CRYPTO  // Select either USE_SOFTWARE_CRYPTO or USE_HARDWARE_CRYPTO

/*------------------------------------------------------------------------------
* Signal Processing Configuration
*----------------------------------------------------------------------------*/
// Spectrogram Parameters
#define SAMPLES_PER_MELVEC 512
#define MELVEC_LENGTH 20
#define N_MELVECS 20

// Optimize chain computations
#define CHAIN_NO_OPT 0
#define CHAIN_OPT 1
#define CHAIN_OPT_MODE CHAIN_OPT  // Select either CHAIN_NO_OPT or CHAIN_OPT

// Mel Processing Mode
#define MEL_MODE_MATRIX 0     // Performance: 20900 cycles per vector
#define MEL_MODE_FILTERBANK 1 // Performance: 4246 cycles per vector
#define MEL_MODE MEL_MODE_FILTERBANK  // Select either MEL_MODE_FILTERBANK or MEL_MODE_MATRIX

// Thresholding Configuration
#define THRESHOLD_HARD_FULL 0
#define THRESHOLD_HARD_PER_MELVEC 1
#define THRESHOLD_LOOSE 2
#define USE_THRESHOLD 1 // Enable/disable thresholding
#define THRESHOLD_VALUE 0x1 // Threshold value for the Mel vectors
#define THRESHOLD_MODE THRESHOLD_HARD_FULL // Select either THRESHOLD_HARD_FULL, THRESHOLD_HARD_PER_MELVEC, or THRESHOLD_LOOSE

/*------------------------------------------------------------------------------
* Debug Configuration
*----------------------------------------------------------------------------*/
// Enable/disable performance measurements
#define PERF_COUNT 1

// Selective performance measurements (set to 0 to disable)
#define MEASURE_CYCLES_FULL_SPECTROGRAM 0 // (Turns off all other signal processing measurements)

#define MEASURE_CYCLES_SIGNAL_PROC_OP 1
#define MEASURE_CYCLES_FFT 1
#define MEASURE_CYCLES_MEL 1

#define MEASURE_CYCLES_THRESHOLD 1
#define MEASURE_CYCLES_ENCODE_PACKET 1
#define MEASURE_CYCLES_SEND_PACKET 0

#define MEASURE_CYCLES_PRINT_FV 0
#define MEASURE_CYCLES_PRINT_PACKET 0

// Enable/disable debug printing
#define DEBUGP 1

// Enable/disable printing for elements of the system
#define PRINT_FV_SPECTROGRAM 0
#define PRINT_ENCODED_PACKET 1

/*==============================================================================
*                          DO NOT MODIFY SECTION
*============================================================================*/

// Debug print macro
#if (DEBUGP == 1)
#define DEBUG_PRINT(...) do{ printf(__VA_ARGS__ ); } while( 0 )
#else
#define DEBUG_PRINT(...) do{ } while ( 0 )
#endif

// Re-define the DEBUGP, PERF_COUNT, and ENABLE_UART macros if NO_DEBUG is set
#if NO_DEBUG == 1
#undef DEBUGP
#undef PERF_COUNT
#undef ENABLE_UART
#define DEBUGP 0
#define PERF_COUNT 0
#define ENABLE_UART 0
#endif

#endif /* INC_CONFIG_H_ */
