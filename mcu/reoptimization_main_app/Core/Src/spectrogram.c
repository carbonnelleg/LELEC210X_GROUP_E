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

#if CHAIN_OPTIMIZE_MEL_OPT == 0
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
#elif CHAIN_OPTIMIZE_MEL_OPT == 1
void mel_filter_apply(q15_t *fft_array, q15_t *mel_array, size_t fft_len, size_t mel_len) {
	// Process 4 triangles at once through loop unrolling, and register variables
	for (size_t i = 0; i < mel_len; i += 4) {
		// Load the Mel triangle values
		const q15_t* mel_values_0 = mel_triangles[i].values;
        const q15_t* mel_values_1 = mel_triangles[i+1].values;
        const q15_t* mel_values_2 = mel_triangles[i+2].values;
        const q15_t* mel_values_3 = mel_triangles[i+3].values;

		// Load the FFT samples
		q15_t* fft_samples_0 = &fft_array[mel_triangles[i].idx_offset];
		q15_t* fft_samples_1 = &fft_array[mel_triangles[i+1].idx_offset];
		q15_t* fft_samples_2 = &fft_array[mel_triangles[i+2].idx_offset];
		q15_t* fft_samples_3 = &fft_array[mel_triangles[i+3].idx_offset];

		// Compute the dot product of the FFT samples and the Mel triangle
		q63_t mel_result_0, mel_result_1, mel_result_2, mel_result_3;
		arm_dot_prod_q15(fft_samples_0, mel_values_0, mel_triangles[i].triangle_len, &mel_result_0);
		arm_dot_prod_q15(fft_samples_1, mel_values_1, mel_triangles[i+1].triangle_len, &mel_result_1);
		arm_dot_prod_q15(fft_samples_2, mel_values_2, mel_triangles[i+2].triangle_len, &mel_result_2);
		arm_dot_prod_q15(fft_samples_3, mel_values_3, mel_triangles[i+3].triangle_len, &mel_result_3);

		// Store the result in the Mel array
		mel_array[i]   = clip_q63_to_q15(mel_result_0);
		mel_array[i+1] = clip_q63_to_q15(mel_result_1);
		mel_array[i+2] = clip_q63_to_q15(mel_result_2);
		mel_array[i+3] = clip_q63_to_q15(mel_result_3);
	}

	// Handle remaining triangles
	for (size_t i = mel_len & ~3; i < mel_len; i++) {
		const q15_t* mel_values = mel_triangles[i].values;
		q15_t* fft_samples = &fft_array[mel_triangles[i].idx_offset];
		q63_t mel_result;
		arm_dot_prod_q15(fft_samples, mel_values, mel_triangles[i].triangle_len, &mel_result);
		mel_array[i] = clip_q63_to_q15(mel_result);
	}
}
#endif

// Prepare the signal for the spectrogram computation
#if CHAIN_SIGNAL_PREP_OPT_LEVEL == 0
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
#elif CHAIN_SIGNAL_PREP_OPT_LEVEL == 1
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
			buf[i] = ((q31_t)buf[i] << 3) - (1 << 14);

			// multiply by Hamming
			buf[i] = (q15_t)(((q31_t)buf[i] * (q31_t)hamming_window[i]) >> 15);
		}
		STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 0 & 1 - Shift + DC Removal + Windowing");
	}
#elif CHAIN_SIGNAL_PREP_OPT_LEVEL == 2
void Spectrogram_Format(q15_t *buf)
{
    START_CYCLE_COUNT_SIGNAL_PROC_OP();
    
    // Pre-compute constants
    const q31_t dc_offset = (1 << 14);
    int i = 0;
    
    // Process 4 samples at once (loop unrolling)
    for (; i <= SAMPLES_PER_MELVEC - 4; i += 4)
    {
        // Load 4 samples to registers
        register q31_t s0 = (q31_t)buf[i];
        register q31_t s1 = (q31_t)buf[i+1];
        register q31_t s2 = (q31_t)buf[i+2];
        register q31_t s3 = (q31_t)buf[i+3];
        
        // Shift + DC remove
        s0 = (s0 << 3) - dc_offset;
        s1 = (s1 << 3) - dc_offset;
        s2 = (s2 << 3) - dc_offset;
        s3 = (s3 << 3) - dc_offset;
        
        // Multiply by Hamming
        buf[i]   = (q15_t)__SSAT((s0 * (q31_t)hamming_window[i]) >> 15, 16);
        buf[i+1] = (q15_t)__SSAT((s1 * (q31_t)hamming_window[i+1]) >> 15, 16);
        buf[i+2] = (q15_t)__SSAT((s2 * (q31_t)hamming_window[i+2]) >> 15, 16);
        buf[i+3] = (q15_t)__SSAT((s3 * (q31_t)hamming_window[i+3]) >> 15, 16);
    }
    
    // Handle remaining samples
    for (; i < SAMPLES_PER_MELVEC; i++) // Unremovable Warning here
    {
        q31_t sample = (q31_t)buf[i];
        sample = (sample << 3) - dc_offset;
        buf[i] = (q15_t)__SSAT((sample * (q31_t)hamming_window[i]) >> 15, 16);
    }
    
    STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 0 & 1 - Shift + DC Removal + Windowing");
}
#endif

// Compute spectrogram of samples and transform into MEL vectors.
void Spectrogram_Compute(q15_t *samples, q15_t *melvec)
{
	#if CHAIN_SIGNAL_PREP_OPT_LEVEL == 0
		// STEP 1  : Windowing of input samples
		//           --> Pointwise product
		//           Complexity: O(N)
		//           Number of cycles: <TODO>
		START_CYCLE_COUNT_SIGNAL_PROC_OP();
		arm_mult_q15(samples, hamming_window, buf, SAMPLES_PER_MELVEC);
		STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 1 - Windowing (Hamming)");
	#endif

	// STEP 2  : Discrete Fourier Transform
	//           --> In-place Fast Fourier Transform (FFT) on a real signal
	//           --> For our spectrogram, we only keep only positive frequencies (symmetry) in the next operations.
	//           Complexity: O(Nlog(N))
	//           Number of cycles: <TODO>

	#if CHAIN_SIGNAL_PREP_OPT_LEVEL == 0
		#define FFT_BUFFER_TO_COMUTE buf
	#else
		#define FFT_BUFFER_TO_COMUTE samples
	#endif

	START_CYCLE_COUNT_FFT();

	// Since the FFT is a recursive algorithm, the values are rescaled in the function to ensure that overflow cannot happen.
	arm_rfft_instance_q15 rfft_inst;
	arm_rfft_init_q15(&rfft_inst, SAMPLES_PER_MELVEC, 0, 1);
	arm_rfft_q15(&rfft_inst, FFT_BUFFER_TO_COMUTE, buf_fft);

	STOP_CYCLE_COUNT_FFT("Step 2 - FFT");


	#if CHAIN_OPTIMIZE_MAGNITUDE == 0
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

	#elif CHAIN_OPTIMIZE_MAGNITUDE == 1
		// STEP 3: Compute the complex magnitude of the FFT using a approximation using the maximum value
		// This is sped up using SIMD instructions to compute the complex magnitude of the FFT

		START_CYCLE_COUNT_SIGNAL_PROC_OP();
		for (int i = 0; i < SAMPLES_PER_MELVEC/2; i++)
		{
			// Approximate the magnitude using the maximum value
			// Get real and imaginary parts
			q15_t real = buf_fft[2*i];
			q15_t imag = buf_fft[2*i+1];

			// Get the absolute value of the real and imaginary parts
			#if MAG_APPROX == MAG_APPROX_ABS_MAX || MAG_APPROX == MAG_APPROX_ABS_SUM
				real = real > 0 ? real : -real; // abs(real)
				imag = imag > 0 ? imag : -imag; // abs(imag)
			#endif

			// Get the maximum values
			#if   MAG_APPROX == MAG_APPROX_PURE_MAX || MAG_APPROX == MAG_APPROX_ABS_MAX
				// Get the maximum values
				buf[i] = real > imag ? real : imag; // max(real, imag)
			#elif MAG_APPROX == MAG_APPROX_PURE_SUM || MAG_APPROX == MAG_APPROX_ABS_SUM
				// Get the absolute sum
				buf[i] = real + imag;  // real + imag
			#endif

			// Get the absolute value (so its always positive)
			#if MAG_APPROX == MAG_APPROX_PURE_MAX || MAG_APPROX == MAG_APPROX_PURE_SUM
				buf[i] = buf[i] > 0 ? buf[i] : -buf[i]; // abs(buf[i])
			#endif
		}
		STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 3 - Compute the approximate complex magnitude");

	#elif CHAIN_OPTIMIZE_MAGNITUDE == 2
		// STEP 3: Compute the complex magnitude using optimized unrolled implementation
		START_CYCLE_COUNT_SIGNAL_PROC_OP();
		
		int i = 0;
		
		// Process 4 complex samples at once (unroll by 4)
		for (; i <= SAMPLES_PER_MELVEC/2 - 4; i += 4)
		{
			// Load 4 complex samples (8 values - 4 real + 4 imaginary)
			q15_t real0 = buf_fft[2*i];
			q15_t imag0 = buf_fft[2*i+1];
			q15_t real1 = buf_fft[2*(i+1)];
			q15_t imag1 = buf_fft[2*(i+1)+1];
			q15_t real2 = buf_fft[2*(i+2)];
			q15_t imag2 = buf_fft[2*(i+2)+1];
			q15_t real3 = buf_fft[2*(i+3)];
			q15_t imag3 = buf_fft[2*(i+3)+1];
			
			#if MAG_APPROX == MAG_APPROX_ABS_MAX || MAG_APPROX == MAG_APPROX_ABS_SUM
				// Fast absolute value using branchless operations
				int32_t real0_sign = real0 >> 15;  // Get sign bit (all 1s if negative, all 0s if positive)
				int32_t imag0_sign = imag0 >> 15;
				int32_t real1_sign = real1 >> 15;
				int32_t imag1_sign = imag1 >> 15;
				int32_t real2_sign = real2 >> 15;
				int32_t imag2_sign = imag2 >> 15;
				int32_t real3_sign = real3 >> 15;
				int32_t imag3_sign = imag3 >> 15;
				
				// XOR with sign and subtract sign (branchless absolute value)
				real0 = (real0 ^ real0_sign) - real0_sign;
				imag0 = (imag0 ^ imag0_sign) - imag0_sign;
				real1 = (real1 ^ real1_sign) - real1_sign;
				imag1 = (imag1 ^ imag1_sign) - imag1_sign;
				real2 = (real2 ^ real2_sign) - real2_sign;
				imag2 = (imag2 ^ imag2_sign) - imag2_sign;
				real3 = (real3 ^ real3_sign) - real3_sign;
				imag3 = (imag3 ^ imag3_sign) - imag3_sign;
			#endif
			
			#if MAG_APPROX == MAG_APPROX_PURE_MAX || MAG_APPROX == MAG_APPROX_ABS_MAX
				// Calculate max for all 4 pairs using branchless operations
				buf[i]   = real0 > imag0 ? real0 : imag0;
				buf[i+1] = real1 > imag1 ? real1 : imag1;
				buf[i+2] = real2 > imag2 ? real2 : imag2;
				buf[i+3] = real3 > imag3 ? real3 : imag3;
			#elif MAG_APPROX == MAG_APPROX_PURE_SUM || MAG_APPROX == MAG_APPROX_ABS_SUM
				// Calculate sum for all 4 pairs
				buf[i]   = real0 + imag0;
				buf[i+1] = real1 + imag1;
				buf[i+2] = real2 + imag2;
				buf[i+3] = real3 + imag3;
			#endif
			
			#if MAG_APPROX == MAG_APPROX_PURE_MAX || MAG_APPROX == MAG_APPROX_PURE_SUM
				// Final absolute value using branchless operations
				int32_t sign0 = buf[i] >> 15;
				int32_t sign1 = buf[i+1] >> 15;
				int32_t sign2 = buf[i+2] >> 15;
				int32_t sign3 = buf[i+3] >> 15;
				
				buf[i]   = (buf[i]   ^ sign0) - sign0;
				buf[i+1] = (buf[i+1] ^ sign1) - sign1;
				buf[i+2] = (buf[i+2] ^ sign2) - sign2;
				buf[i+3] = (buf[i+3] ^ sign3) - sign3;
			#endif
		}
		
		// Handle remaining samples
		for (; i < SAMPLES_PER_MELVEC/2; i++)
		{
			q15_t real = buf_fft[2*i];
			q15_t imag = buf_fft[2*i+1];
			
			#if MAG_APPROX == MAG_APPROX_ABS_MAX || MAG_APPROX == MAG_APPROX_ABS_SUM
				// Branchless absolute value
				int32_t real_sign = real >> 15;
				int32_t imag_sign = imag >> 15;
				real = (real ^ real_sign) - real_sign;
				imag = (imag ^ imag_sign) - imag_sign;
			#endif
			
			#if MAG_APPROX == MAG_APPROX_PURE_MAX || MAG_APPROX == MAG_APPROX_ABS_MAX
				buf[i] = real > imag ? real : imag;
			#elif MAG_APPROX == MAG_APPROX_PURE_SUM || MAG_APPROX == MAG_APPROX_ABS_SUM
				buf[i] = real + imag;
			#endif
			
			#if MAG_APPROX == MAG_APPROX_PURE_MAX || MAG_APPROX == MAG_APPROX_PURE_SUM
				int32_t sign = buf[i] >> 15;
				buf[i] = (buf[i] ^ sign) - sign;
			#endif
		}
		
		STOP_CYCLE_COUNT_SIGNAL_PROC_OP("Step 3 - Unrolled magnitude calculation");
	#endif

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