/*
 * spectrogram.c
 *
 *  Created on: Jun 4, 2021
 *      Author: math
 */

#include <stdio.h>
#include "spectrogram.h"
#include "spectrogram_tables.h"
#include "config.h"
#include "utils.h"
#include "arm_absmax_q15.h"

#include "mel_filter_bank.h"

#if MEASURE_CYCLES_FULL_SPECTROGRAM == 1
	#define START_CYCLE_COUNT_SIGNAL_PROC_OP()
	#define STOP_CYCLE_COUNT_SIGNAL_PROC_OP(str)
	#define START_CYCLE_COUNT_FFT()
	#define STOP_CYCLE_COUNT_FFT(str)
	#define START_CYCLE_COUNT_MEL()
	#define STOP_CYCLE_COUNT_MEL(str)
#else
	// Timings for the other operations
	#if MEASURE_CYCLES_SIGNAL_PROC_OP == 0
		#define START_CYCLE_COUNT_SIGNAL_PROC_OP()
		#define STOP_CYCLE_COUNT_SIGNAL_PROC_OP(str)
	#else
		#define START_CYCLE_COUNT_SIGNAL_PROC_OP() start_cycle_count()
		#define STOP_CYCLE_COUNT_SIGNAL_PROC_OP(str) stop_cycle_count(str)
	#endif

	// Timings for the fft
	#if MEASURE_CYCLES_FFT == 0
		#define START_CYCLE_COUNT_FFT()
		#define STOP_CYCLE_COUNT_FFT(str)
	#else
		#define START_CYCLE_COUNT_FFT() start_cycle_count()
		#define STOP_CYCLE_COUNT_FFT(str) stop_cycle_count(str)
	#endif

	// Mel transform timings
	#if MEASURE_CYCLES_MEL == 0
		#define START_CYCLE_COUNT_MEL()
		#define STOP_CYCLE_COUNT_MEL(str)
	#else
		#define START_CYCLE_COUNT_MEL() start_cycle_count()
		#define STOP_CYCLE_COUNT_MEL(str) stop_cycle_count(str)
	#endif
#endif // MEASURE_CYCLES_FULL_SPECTROGRAM

#ifdef ALIGN_BUFFER_SIGNALS
// Using ARM CMSIS alignment attribute
ALIGN_32BYTES(q15_t buf    [  SAMPLES_PER_MELVEC  ]); // Windowed samples
ALIGN_32BYTES(q15_t buf_fft[2*SAMPLES_PER_MELVEC  ]); // Double size buffer
ALIGN_32BYTES(q15_t buf_tmp[  SAMPLES_PER_MELVEC/2]); // Intermediate buffer
#else
q15_t buf    [  SAMPLES_PER_MELVEC  ]; // Windowed samples
q15_t buf_fft[2*SAMPLES_PER_MELVEC  ]; // Double size (real|imag) buffer needed for arm_rfft_q15
q15_t buf_tmp[  SAMPLES_PER_MELVEC/2]; // Intermediate buffer for arm_mat_mult_fast_q15
#endif

void mel_filter_apply(q15_t *fft_array, q15_t *mel_array, size_t fft_len, size_t mel_len) {
	// Pre-check all triangles once (cache locality)
    for (size_t i = 0; i < mel_len; i++) {
        if (mel_triangles[i].idx_offset + mel_triangles[i].triangle_len > fft_len) {
            DEBUG_PRINT("Error: Mel triangle %d is too large\n", i);
            return;
        }
    }

	// Process all Mel triangles at once (cache locality optimization)
    for (size_t i = 0; i < mel_len; i++) {
		q15_t* fft_samples = &fft_array[mel_triangles[i].idx_offset];
		q63_t mel_result;
		// Compute the dot product of the FFT samples and the Mel triangle
        arm_dot_prod_q15(fft_samples,  mel_triangles[i].values,  mel_triangles[i].triangle_len, &mel_result);
		// Store the result in the Mel array
		mel_array[i] = clip_q63_to_q15(mel_result);
    }
}

#if CHAIN_OPT_MODE == CHAIN_OPT
// Convert 12-bit DC ADC samples to Q1.15 fixed point signal and remove DC component
void Spectrogram_Format(q15_t *buf)
{
    // STEP 0 & 1: Combine 0.1 (Increase fixed-point scale) + 0.2 (Remove DC) + 1 (Windowing)

    // Original plan:
    //  - Shift left by 3 to go from [0..4095] (12-bit) up into [0..32767] (Q15).
    //  - Then subtract 2^14 = 16384 to recenter around zero.
	// - Multiply by Hamming window.
    // Instead, do both in one pass:
    START_CYCLE_COUNT_SIGNAL_PROC_OP();
    for (int i = 0; i < SAMPLES_PER_MELVEC; i++)
	{
		// shift + DC
		q31_t shifted = ((q31_t)buf[i] << 3) - (1 << 14);

		// multiply by Hamming
		q31_t w = (shifted * hamming_window[i]) >> 15;

		// saturate to Q15
		buf[i] = (q15_t)__SSAT(w, 16);
	}
    STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 0 & 1 - Shift + DC Removal + Windowing");
}

// Compute spectrogram of samples and transform into MEL vectors.
void Spectrogram_Compute(q15_t *samples, q15_t *melvec)
{
    // STEP 2: Real FFT
	START_CYCLE_COUNT_FFT();
    arm_rfft_instance_q15 rfft_inst;
    // 0 => FFT, 1 => IFFT // 1 => bitReverse
    arm_rfft_init_q15(&rfft_inst, SAMPLES_PER_MELVEC, 0, 1);
	STOP_CYCLE_COUNT_FFT("Step 2.1 - RFFT INIT");

    START_CYCLE_COUNT_FFT();
    arm_rfft_q15(&rfft_inst, buf, buf_fft);
    STOP_CYCLE_COUNT_FFT("Step 2.2 - RFFT");

    // STEP 3: Compute magnitude and find max in a single pass
    START_CYCLE_COUNT_SIGNAL_PROC_OP();
    q15_t vmax = 0;

    for (int i = 0; i < SAMPLES_PER_MELVEC / 2; i++)
    {
		// Compute magnitude
		q31_t real = buf_fft[2 * i];
		q31_t imag = buf_fft[2 * i + 1];
		q31_t mag = __QADD(__QADD(__SMUAD(real, real), __SMUAD(imag, imag)), 0); // Q31

		// Find max
		if (mag > vmax)
		{
			vmax = mag;
		}

		// Store magnitude in buf
		buf[i] = (q15_t)__SSAT(mag, 16);
	}
    STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 3 - Magnitude & Find max");

    // STEP 4: Normalize
    START_CYCLE_COUNT_SIGNAL_PROC_OP();
    if (1)
    {
        // Manual reciprocal in Q15:
        //  1.0 in Q15 is 0x7FFF ~ 32767
        //  We'll do: (32767 << 15) / vmax = Q15 reciprocal
        //  Then multiply each sample by this reciprocal >> 15
        q31_t reciprocal = (((q31_t)0x7FFF) << 15) / (q31_t)vmax; 
        q15_t invVmax = (q15_t)__SSAT(reciprocal, 16); // saturate to Q15

        for (int i = 0; i < SAMPLES_PER_MELVEC / 2; i++)
        {
            q31_t tmp = ((q31_t)buf[i] * (q31_t)invVmax) >> 15; 
            buf[i] = (q15_t)__SSAT(tmp, 16);
        }
    }
    STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 4 - Normalize magnitude spectrum");

    // STEP 5: Mel transform
    START_CYCLE_COUNT_MEL();
#if MEL_MODE == MEL_MODE_FILTERBANK
    // e.g., mel_filter_apply(buf, melvec, SAMPLES_PER_MELVEC/2, MELVEC_LENGTH);
    mel_filter_apply(buf, melvec, SAMPLES_PER_MELVEC, MELVEC_LENGTH);
    STOP_CYCLE_COUNT_MEL("Step 5 - Mel filter bank");
#else
    arm_matrix_instance_q15 hz2mel_inst, fftmag_inst, melvec_inst;
    arm_mat_init_q15(&hz2mel_inst, MELVEC_LENGTH, SAMPLES_PER_MELVEC/2, hz2mel_mat);
    arm_mat_init_q15(&fftmag_inst, SAMPLES_PER_MELVEC/2, 1, buf);
    arm_mat_init_q15(&melvec_inst, MELVEC_LENGTH, 1, melvec);

    arm_mat_mult_fast_q15(&hz2mel_inst, &fftmag_inst, &melvec_inst, buf_tmp);
    STOP_CYCLE_COUNT_MEL("Step 5 - Mel matrix");
#endif
}

#elif CHAIN_OPT_MODE == CHAIN_NO_OPT
// Convert 12-bit DC ADC samples to Q1.15 fixed point signal and remove DC component
void Spectrogram_Format(q15_t *buf)
{
	// STEP 0.1 : Increase fixed-point scale
	//            --> Pointwise shift
	//            Complexity: O(N)
	//            Number of cycles: <TODO>

	// The output of the ADC is stored in an unsigned 12-bit format, so buf[i] is in [0 , 2**12 - 1]
	// In order to better use the scale of the signed 16-bit format (1 bit of sign and 15 integer bits), we can multiply by 2**(15-12) = 2**3
	// That way, the value of buf[i] is in [0 , 2**15 - 1]

	// /!\ When multiplying/dividing by a power 2, always prefer shifting left/right instead, ARM instructions to do so are more efficient.
	// Here we should shift left by 3.

	START_CYCLE_COUNT_SIGNAL_PROC_OP();
	arm_shift_q15(buf, 3, buf, SAMPLES_PER_MELVEC);
	STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 0.1 - Increase fixed-point scale");

	// STEP 0.2 : Remove DC Component
	//            --> Pointwise substract
	//            Complexity: O(N)
	//            Number of cycles: <TODO>

	// Since we use a signed representation, we should now center the value around zero, we can do this by substracting 2**14.
	// Now the value of buf[i] is in [-2**14 , 2**14 - 1]

	START_CYCLE_COUNT_SIGNAL_PROC_OP();
	for(uint16_t i=0; i < SAMPLES_PER_MELVEC; i++) { // Remove DC component
		buf[i] -= (1 << 14);
	}
	STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 0.2 - Remove DC Component");
}

// Compute spectrogram of samples and transform into MEL vectors.
void Spectrogram_Compute(q15_t *samples, q15_t *melvec)
{
	// STEP 1  : Windowing of input samples
	//           --> Pointwise product
	//           Complexity: O(N)
	//           Number of cycles: <TODO>
	START_CYCLE_COUNT_SIGNAL_PROC_OP();
	arm_mult_q15(samples, hamming_window, buf, SAMPLES_PER_MELVEC);
	STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 1 - Windowing (Hamming)");

	// STEP 2  : Discrete Fourier Transform
	//           --> In-place Fast Fourier Transform (FFT) on a real signal
	//           --> For our spectrogram, we only keep only positive frequencies (symmetry) in the next operations.
	//           Complexity: O(Nlog(N))
	//           Number of cycles: <TODO>

	START_CYCLE_COUNT_FFT();

	// Since the FFT is a recursive algorithm, the values are rescaled in the function to ensure that overflow cannot happen.
	arm_rfft_instance_q15 rfft_inst;
	arm_rfft_init_q15(&rfft_inst, SAMPLES_PER_MELVEC, 0, 1);
	arm_rfft_q15(&rfft_inst, buf, buf_fft);

	STOP_CYCLE_COUNT_FFT("Step 2 - FFT");

	// STEP 3  : Compute the complex magnitude of the FFT
	//           Because the FFT can output a great proportion of very small values,
	//           we should rescale all values by their maximum to avoid loss of precision when computing the complex magnitude
	//           In this implementation, we use integer division and multiplication to rescale values, which are very costly.

	// STEP 3.1: Find the extremum value (maximum of absolute values)
	//           Complexity: O(N)
	//           Number of cycles: <TODO>

	q15_t vmax;
	uint32_t pIndex=0;

	START_CYCLE_COUNT_SIGNAL_PROC_OP();
	arm_absmax_q15(buf_fft, SAMPLES_PER_MELVEC, &vmax, &pIndex);
	STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 3.1 - Find the extremum value");

	// STEP 3.2: Normalize the vector - Dynamic range increase
	//           Complexity: O(N)
	//           Number of cycles: <TODO>

	START_CYCLE_COUNT_SIGNAL_PROC_OP();
	for (int i=0; i < SAMPLES_PER_MELVEC; i++) // We don't use the second half of the symmetric spectrum
	{
		buf[i] = (q15_t) (((q31_t) buf_fft[i] << 15) /((q31_t)vmax));
	}
	STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 3.2 - Normalize the vector");

	// STEP 3.3: Compute the complex magnitude
	//           --> The output buffer is now two times smaller because (real|imag) --> (mag)
	//           Complexity: O(N)
	//           Number of cycles: <TODO>

	START_CYCLE_COUNT_SIGNAL_PROC_OP();
	arm_cmplx_mag_q15(buf, buf, SAMPLES_PER_MELVEC/2);
	STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 3.3 - Compute the complex magnitude");

	// STEP 3.4: Denormalize the vector
	//           Complexity: O(N)
	//           Number of cycles: <TODO>

	START_CYCLE_COUNT_SIGNAL_PROC_OP();
	for (int i=0; i < SAMPLES_PER_MELVEC/2; i++)
	{
		buf[i] = (q15_t) ((((q31_t) buf[i]) * ((q31_t) vmax) ) >> 15 );
	}
	STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 3.4 - Denormalize the vector");

	// STEP 4:   Apply MEL transform
	//           --> Fast Matrix Multiplication
	//           Complexity: O(Nmel*N)
	//           Number of cycles: <TODO>

	// /!\ The difference between the function arm_mat_mult_q15() and the fast variant is that the fast variant use a 32-bit rather than a 64-bit accumulator.
	// The result of each 1.15 x 1.15 multiplication is truncated to 2.30 format. These intermediate results are accumulated in a 32-bit register in 2.30 format.
	// Finally, the accumulator is saturated and converted to a 1.15 result. The fast version has the same overflow behavior as the standard version but provides
	// less precision since it discards the low 16 bits of each multiplication result.

	// /!\ In order to avoid overflows completely the input signals should be scaled down. Scale down one of the input matrices by log2(numColsA) bits to avoid overflows,
	// as a total of numColsA additions are computed internally for each output element. Because our hz2mel_mat matrix contains lots of zeros in its rows, this is not necessary.
	
	START_CYCLE_COUNT_MEL();
	#if MEL_MODE == MEL_MODE_FILTERBANK
		mel_filter_apply(buf, melvec, SAMPLES_PER_MELVEC, MELVEC_LENGTH);
		STOP_CYCLE_COUNT_MEL("Step 4 - Mel filter bank");
	#elif MEL_MODE == MEL_MODE_MATRIX
		arm_matrix_instance_q15 hz2mel_inst, fftmag_inst, melvec_inst;

		arm_mat_init_q15(&hz2mel_inst, MELVEC_LENGTH, SAMPLES_PER_MELVEC/2, hz2mel_mat);
		arm_mat_init_q15(&fftmag_inst, SAMPLES_PER_MELVEC/2, 1, buf);
		arm_mat_init_q15(&melvec_inst, MELVEC_LENGTH, 1, melvec);

		arm_mat_mult_fast_q15(&hz2mel_inst, &fftmag_inst, &melvec_inst, buf_tmp);
		STOP_CYCLE_COUNT_MEL("Step 4 - Mel matrix");
	#endif
	
}

#endif // CHAIN_OPT_MODE