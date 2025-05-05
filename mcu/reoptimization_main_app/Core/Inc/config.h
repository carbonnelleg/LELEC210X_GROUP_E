#include <stdio.h>
#include "utils.h"

#ifndef CONFIG_H
#define CONFIG_H

// =============================================================================
// Debug and Feature Toggles
// =============================================================================
/*
 * NO_UART          - Deactivate UART prints.
 *                    Default: 0 (UART prints enabled).
 * 
 * NO_DEBUG         - Deactivate debug prints.
 *                    Default: 0 (debug prints enabled).
 *
 * NO_DEBUGPRINT    - Deactivate debug prints.
 *                    Default: 0 (debug prints enabled).
 * 
 * NO_PERF          - Deactivate all performance metrics.
 *                    Default: 0 (performance metrics enabled).
 *
 * NO_OPTIMIZATIONS - Deactivate all optimizations.
 *                    Default: 0 (optimizations active).
 *
 * NO_S2LP_SLEEP    - Deactivate S2LP sleep mode.
 *                    Default: 0 (S2LP sleep mode enabled).
 * 
 * USE_BUTTON       - Enables the use of a button (should not be needed).
 *                    Default: 0 (button support disabled).
 */
#define NO_UART          1
#define NO_DEBUG         0
#define NO_DEBUGPRINT    0
#define NO_DEBUGFAST_P   0
#define NO_PERF          0
#define NO_OPTIMIZATIONS 0
#define NO_S2LP_SLEEP    0
#define USE_BUTTON       0

// =============================================================================
// Optimization Defines
// =============================================================================
/*
 * OPT_CHAIN_ON  - Activates whole chain optimizations (80 -> 41k speedup).
 *                 Default: 1 (enabled).
 *
 * OPT_PACKET_ON - Activates optimizations for packetization.
 *                 (By default, hardware acceleration is used.)
 *                 Default: 1 (enabled).
 * 
 * OPT_S2LP_DYN_POWER_ON - Activates dynamic power optimization for S2LP.
 *                        Default: 1 (enabled).
 * 
 * CAPA_LVL_1  - Capacity level 1.
 *              Default: 0.40. (3.96V -> 1.97mJ, discharges to 3.4V)
 * 
 * CAPA_LVL_2  - Capacity level 2.
 *             Default: 0.75. (4.27V -> 3.85mJ, discharges to 3.8V)
 * 
 */
#define OPT_CHAIN_ON   1
#define OPT_PACKET_ON  1
#define OPT_S2LP_DYN_POWER_ON  1

#define CAPA_LVL_1  0.55
#define CAPA_LVL_2  0.82

// =============================================================================
// Chain Defines
// =============================================================================
/*
 * MEL_VEC_LENGTH - Length parameter for MEL processing.
 *               Default: 20.
 *
 * MEL_NUM_VEC - Number of MEL bins.
 *               Default: 20.
 *
 * SAMPLES_NUM - FFT size parameter.
 *               Default: 512.
 * 
 * SENDER_ID   - ID of the sender.
 *               Default: 0x01.
 *
 * OPT_MEL     - Enable (1) or disable (0) MEL optimization.
 *               Default: 0 (disabled).
 *
 * OPT_PREP    - Enable (1) or disable (0) pre-processing optimization.
 *               Default: 0 (disabled).
 *
 * OPT_AMPL    - Enable (1) or disable (0) amplitude optimization.
 *               Default: 0 (disabled).
 */
#define MEL_VEC_LENGTH   18
#define MEL_NUM_VEC      20
#define SAMPLES_NUM      512

#define SENDER_ID        0x01

#define OPT_MEL      0
#define OPT_PREP     0
#define OPT_AMPL     0

// =============================================================================
// Threshold Defines
// =============================================================================
/*
 * THRESHOLD_MODE       - Mode of the threshold:
 *                          0: Deactivated
 *                          1: Full-mean
 *                          2: Vector-based
 *                          3: Singular
 *                        Default: 0 (deactivated).
 *
 * THRESHOLD_LV1_VALUE  - Threshold level 1 value.
 *                        Default: 5.
 *
 * THRESHOLD_LV2_VALUE  - Threshold level 2 value.
 *                        Default: 10.
 *
 * THRESHOLD_LV3_VALUE  - Threshold level 3 value.
 *                        Default: 20.
 */
#define THRESHOLD_MODE       0
#define THRESHOLD_LV1_VALUE  5
#define THRESHOLD_LV2_VALUE  10
#define THRESHOLD_LV3_VALUE  20

// =============================================================================
// Approximate Amplitude Defines
// =============================================================================
/*
 * AMPL_APPROX         - Approximation mode for amplitude (tied to OPT_AMPL).
 *                       Default: 0.
 *
 * AMPL_ABS_INPUTS     - Use absolute value processing on inputs.
 *                       Default: 0 (disabled).
 *
 * AMPL_MAX_SUM_INPUTS - Use the maximum or sum of the inputs.
 *                       0: Maximum
 *                       1: Sum
 *                       Default: 1.
 *
 * AMPL_ABS_OUTPUTS    - Use absolute value processing on outputs.
 *                       Default: 0 (disabled).
 */
#define AMPL_APPROX         1
#define AMPL_ABS_INPUTS     1
#define AMPL_MAX_SUM_INPUTS 0
#define AMPL_ABS_OUTPUTS    0

// =============================================================================
// Performance Measurement Defines
// =============================================================================
/*
 * Top Level Performance Metrics:
 * PERF_CHAIN  - Overall chain performance measurement.
 *               Default: 1 (enabled).
 *
 * PERF_PACKET - Overall packet performance measurement.
 *               Default: 1 (enabled).
 *
 * PERF_SEND   - Performance measurement for the S2LP send operation.
 *               Default: 1 (enabled).
 *
 * Detailed Chain Performance Stages:
 * PERF_CHAIN_PREP  - Pre-FFT stage.
 *                    Default: 1 (enabled).
 *
 * PERF_CHAIN_FFT   - FFT stage.
 *                    Default: 1 (enabled).
 *
 * PERF_CHAIN_AMPL  - Amplitude stage.
 *                    Default: 1 (enabled).
 *
 * PERF_CHAIN_MEL   - MEL stage.
 *                    Default: 1 (enabled).
 *
 * Detailed Packet Performance Stages:
 * PERF_PACKET_ENCODE - Encoding stages (2 stages).
 *                     Default: 1 (enabled).
 *
 * PERF_PACKET_AES    - MAC stage.
 *                     Default: 1 (enabled).
 */
#define PERF_CHAIN          1
#define PERF_PACKET         1
#define PERF_SEND           1

#define PERF_CHAIN_PREP     1
#define PERF_CHAIN_FFT      1
#define PERF_CHAIN_AMPL     1
#define PERF_CHAIN_MEL      1

#define PERF_PACKET_ENCODE  1
#define PERF_PACKET_AES     1


// =============================================================================
// Implementation redefines and checks
// =============================================================================

// Deactivate UART and debug prints with the NO_UART flag
#if NO_UART == 1
    #undef NO_DEBUG
    #undef NO_DEBUGPRINT
    #undef NO_DEBUGFAST_P
    #define NO_DEBUG      1
    #define NO_DEBUGPRINT 1
    #define NO_DEBUGFAST_P 1
#endif

// Deactivate all prints and performance metrics with the NO_DEBUG flag
#if NO_DEBUG == 1
    #undef NO_DEBUGPRINT
    #undef NO_DEBUGFAST_P
    #undef NO_PERF
    #define NO_DEBUGPRINT 1
    #define NO_DEBUGFAST_P 1
    #define NO_PERF       1
#endif

// Debug print macro
#if (NO_DEBUGPRINT == 0)
    #define DEBUG_PRINT(...) do{ printf(__VA_ARGS__ ); } while( 0 )
#else
    #define DEBUG_PRINT(...) do{ } while ( 0 )
#endif

// Fast Debug print macro
#if (NO_DEBUGFAST_P == 0)
    #define DEBUG_PRINT_FAST(data, size) do { fast_debug_print(data, size); } while(0)
#else
    #define DEBUG_PRINT_FAST(data, size) do { } while(0)
#endif

// Deactivate performance metrics with the NO_PERF flag
#if NO_PERF == 1
    #undef PERF_CHAIN
    #undef PERF_PACKET
    #undef PERF_SEND
    #undef PERF_CHAIN_PREP
    #undef PERF_CHAIN_FFT
    #undef PERF_CHAIN_AMPL
    #undef PERF_CHAIN_MEL
    #undef PERF_PACKET_ENCODE
    #undef PERF_PACKET_AES
    #define PERF_CHAIN          0
    #define PERF_PACKET         0
    #define PERF_SEND           0
    #define PERF_CHAIN_PREP     0
    #define PERF_CHAIN_FFT      0
    #define PERF_CHAIN_AMPL     0
    #define PERF_CHAIN_MEL      0
    #define PERF_PACKET_ENCODE  0
    #define PERF_PACKET_AES     0
#endif

// Deactivate optimizations with the NO_OPTIMIZATIONS flag
#if NO_OPTIMIZATIONS == 1
    #undef OPT_CHAIN_ON
    #undef OPT_PACKET_ON
    #undef OPT_MEL
    #undef OPT_PREP
    #undef OPT_AMPL
    #define OPT_CHAIN_ON   0
    #define OPT_PACKET_ON  0
    #define OPT_MEL        0
    #define OPT_PREP       0
    #define OPT_AMPL       0
#endif

#endif // CONFIG_H
