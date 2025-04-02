/*
 * feature_sel.h
 *
 *  Created on: Jun 4, 2021
 *      Author: math
 */

#ifndef INC_SPECTROGRAM_H_
#define INC_SPECTROGRAM_H_

#include "arm_math.h"
#include "config.h"

static inline float q15_to_float(q15_t x)
{
	float y;
	arm_q15_to_float(&x, &y, 1);
	return y;
}

static inline q15_t float_to_q15(float x)
{
	q15_t y;
	arm_float_to_q15(&x, &y, 1);
	return y;
}

// Compute the whole mel spectrogram using a FFT*Mel size buffer
Full_spectrogram_compute(uint16_t *buffer, q15_t mel_vectors[MEL_NUM_VEC][MEL_VEC_LENGTH]);

#endif /* INC_SPECTROGRAM_H_ */
