#ifndef INC_ADC_DBLBUF_H_
#define INC_ADC_DBLBUF_H_

#include "main.h"
#include "config.h"
#include "arm_math.h"

// ADC parameters
#define ADC_BUF_SIZE SAMPLES_NUM*MEL_NUM_VEC

int StartADCAcq(void);
void StopADCAcq(void);
void ProcessADCData(void);
uint8_t analogRead_CapaLvl(void); // Implemented in main (BAD PRACTICE)

extern ADC_HandleTypeDef hadc1;

#endif /* INC_ADC_DBLBUF_H_ */
