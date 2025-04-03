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

// Step 1 : Pre-process the signal before computing the spectrogram
// This function takes in a buffer of MEL_NUM_VEC * SAMPLES_NUM, and outputs the mel vectors in mel_vectors.
void step1_123_batch_pre_process(q15_t *buffer)
{
	// 1.1 & 1.2 : Batch shift left by 3 to go from [0..4095] (12-bit) up into [0..32767] (Q15) and Batch remove DC component
	for (int i = 0; i < SAMPLES_NUM*MEL_NUM_VEC; i++){ // TODO : Unroll this loop
		buffer[i] = (q15_t)buffer[i]<<3 - (1<<14);
	}

	// 1.3 : Parallel windowing of the signal
	for (int i = 0; i < MEL_NUM_VEC; i++){ // TODO : Unroll this loop
		arm_mult_q15(&buffer[i*SAMPLES_NUM], hamming_window, &buf[i*SAMPLES_NUM], SAMPLES_NUM);
	}
}

// Step 3 : Compute the complex magnitude of the FFT
void step3_approximate_magnitude(q15_t *fft_buffer, q15_t *output_buffer)
{
	for (int i = 0; i < SAMPLES_NUM/2; i++)
	{
		// Approximate the magnitude using the maximum value
		// Get real and imaginary parts
		q15_t real = fft_buffer[2*i];
		q15_t imag = fft_buffer[2*i+1];

		// Get the absolute value of the real and imaginary parts
		#if MAG_APPROX == MAG_APPROX_ABS_MAX || MAG_APPROX == MAG_APPROX_ABS_SUM
			real = real > 0 ? real : -real; // abs(real)
			imag = imag > 0 ? imag : -imag; // abs(imag)
		#endif

		// Get the maximum values
		#if   MAG_APPROX == MAG_APPROX_PURE_MAX || MAG_APPROX == MAG_APPROX_ABS_MAX
			output_buffer[i] = real > imag ? real : imag; // max(real, imag)
		#elif MAG_APPROX == MAG_APPROX_PURE_SUM || MAG_APPROX == MAG_APPROX_ABS_SUM
			output_buffer[i] = real + imag;  // real + imag
		#endif

		// Get the absolute value (so its always positive)
		#if MAG_APPROX == MAG_APPROX_PURE_MAX || MAG_APPROX == MAG_APPROX_PURE_SUM
			output_buffer[i] = output_buffer[i] > 0 ? output_buffer[i] : -output_buffer[i]; // abs(output_buffer[i])
		#endif
	}
}

// Step 2 & 3 : Compute the full spectrogram and take the absolute value
// This function takes in a buffer of MEL_NUM_VEC * SAMPLES_NUM, and outputs the mel vectors in mel_vectors.
// The function computes the FFT of each vector in the buffer, and then computes the complex magnitude of each FFT.
void step23_batch_fft(q15_t *buffer)
{
	q15_t fft_buffer[SAMPLES_NUM];
	// 2.1 : Compute each FFT of size SAMPLES_NUM
	for (int i = 0; i < MEL_NUM_VEC; i++){ // TODO : Unroll this loop
		// Compute the FFT of each vector in the buffer
		arm_rfft_instance_q15 rfft_inst;
		arm_rfft_init_q15(&rfft_inst, SAMPLES_NUM, 0, 1);
		arm_rfft_q15(&rfft_inst, &buffer[i*SAMPLES_NUM], fft_buffer);

		// 2.2 : Compute the complex magnitude of each FFT
		step3_approximate_magnitude(fft_buffer, &buffer[i*SAMPLES_NUM]);
	}
}

// Step 4 : Compute the mel vectors of each FFT (parallel processing)
// This function takes in a buffer of MEL_NUM_VEC * SAMPLES_NUM, and outputs the mel vectors in mel_vectors.
void step4_mel_filter_apply(q15_t *buffer, q15_t mel_vectors[MEL_NUM_VEC][MEL_VEC_LENGTH])
{
	// 4.1 : Compute the mel vectors of each FFT (parallel processing)
	for (int i = 0; i < MEL_NUM_VEC; i++){ // TODO : Unroll this loop
		mel_filter_apply(&buffer[i*SAMPLES_NUM], &mel_vectors[i][0], SAMPLES_NUM, MEL_VEC_LENGTH);
	}
}

void Full_spectrogram_compute(uint16_t *buffer, q15_t mel_vectors[MEL_NUM_VEC][MEL_VEC_LENGTH])
{
	// 4 Steps
	//    1. Format the signal (expand to 16-bit, remove DC, windowing)
	//    2. Compute the FFT
	//    3. Compute the complex magnitude
	//    4. Compute the mel vectors

	// This function takes in a buffer of MEL_NUM_VEC * SAMPLES_NUM, and outputs the mel vectors in mel_vectors.

	// 1   : Format the signal (expand to 16-bit, remove DC, windowing)
	step1_123_batch_pre_process(buffer);

	// 2 & 3 : Compute each FFT of size SAMPLES_NUM and take the absolute value
	step23_batch_fft(buffer);

	// 4   : Compute the mel vectors of each FFT (parallel processing)
	step4_mel_filter_apply(buffer, mel_vectors);
}