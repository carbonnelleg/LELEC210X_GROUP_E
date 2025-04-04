#include <adc_dblbuf.h>
#include "config.h"
#include "main.h"
#include "spectrogram.h"
#include "arm_math.h"
#include "utils.h"
#include "s2lp.h"
#include "packet.h"

static volatile uint16_t ADCDoubleBuf[2*ADC_BUF_SIZE]; /* ADC group regular conversion data (array of data) */
static volatile uint16_t* ADCData[2] = {&ADCDoubleBuf[0], &ADCDoubleBuf[ADC_BUF_SIZE]};
static volatile uint8_t ADCDataRdy[2] = {0, 0};
static volatile uint16_t ADCProcessBuf[ADC_BUF_SIZE]; 

static q15_t mel_vectors[MEL_NUM_VEC][MEL_VEC_LENGTH];

static uint32_t packet_cnt = 0;

// Function to start the ADC acquisition
int StartADCAcq() {
	int ret = HAL_ADC_Start_DMA(&hadc1, (uint32_t *)ADCDoubleBuf, 2*ADC_BUF_SIZE);

	// Put the MCU to sleep until the ADC buffer is full
	HAL_PWR_EnterSLEEPMode(PWR_MAINREGULATOR_ON, PWR_SLEEPENTRY_WFI);

	return ret;
}

// Function to stop the ADC acquisition
static void StopADCAcq() {
	HAL_ADC_Stop_DMA(&hadc1);
}

// Function to print the encoded packet in hexadecimal format
static void print_encoded_packet(uint8_t *packet) {
	#if (NO_DEBUGPRINT == 0)
		char hex_encoded_packet[2*PACKET_LENGTH+1];
		hex_encode(hex_encoded_packet, packet, PACKET_LENGTH);
		DEBUG_PRINT("DF:HEX:%s\r\n", hex_encoded_packet);
	#endif
}

#if OPT_PACKET_ON == 0
// Function to encode the packet
static void encode_packet(uint8_t *packet, uint32_t* packet_cnt) {
	// BE encoding of each mel coef
	for (size_t i=0; i<MEL_NUM_VEC; i++) {
		for (size_t j=0; j<MEL_VEC_LENGTH; j++) {
			(packet+PACKET_HEADER_LENGTH)[(i*MEL_VEC_LENGTH+j)*2]   = mel_vectors[i][j] >> 8;
			(packet+PACKET_HEADER_LENGTH)[(i*MEL_VEC_LENGTH+j)*2+1] = mel_vectors[i][j] & 0xFF;
		}
	}
	// Write header and tag into the packet.
	make_packet(packet, PAYLOAD_LENGTH, SENDER_ID, *packet_cnt);
	*packet_cnt += 1;
	if (*packet_cnt == 0) {
		// Should not happen as packet_cnt is 32-bit and we send at most 1 packet per second.
		DEBUG_PRINT("Packet counter overflow.\r\n");
		Error_Handler();
	}
}
#elif OPT_PACKET_ON == 1
// Function to encode the packet
static void encode_packet(uint8_t *packet, uint32_t* packet_cnt) {
	// Use pointer arithmetic for better performance
    uint8_t *ptr = packet + PACKET_HEADER_LENGTH;
    
	// BE encoding of each mel coef
    for (size_t i=0; i<MEL_NUM_VEC; i++) {
        const q15_t *mel_ptr = mel_vectors[i];
        
        // Unfold the loop, and hint for SIMD instructions
        for (size_t j=0; j<MEL_VEC_LENGTH-1; j+=2) {
            // Load two q15_t values
            uint32_t pair = (mel_ptr[j] << 16) | (mel_ptr[j+1] & 0xFFFF);
            
            // Extract bytes with bitwise operations
            *ptr++ = (pair >> 24) & 0xFF;        // First value high byte
            *ptr++ = (pair >> 16) & 0xFF;        // First value low byte
            *ptr++ = (pair >> 8) & 0xFF;         // Second value high byte
            *ptr++ = pair & 0xFF;                // Second value low byte
        }
        
        // Handle odd element if MEL_VEC_LENGTH is odd
        if (MEL_VEC_LENGTH & 0b1) {
            size_t j = MEL_VEC_LENGTH - 1;
            *ptr++ = mel_ptr[j] >> 8;
            *ptr++ = mel_ptr[j] & 0xFF;
        }
    }
	// Write header and tag into the packet.
	make_packet(packet, PAYLOAD_LENGTH, SENDER_ID, *packet_cnt);

	*packet_cnt += 1;
	if (*packet_cnt == 0) {
		// Should not happen as packet_cnt is 32-bit and we send at most 1 packet per second.
		DEBUG_PRINT("Packet counter overflow.\r\n");
		Error_Handler();
	}
}
#endif

// Function to create and send the packet
static void send_spectrogram() {
	uint8_t packet[PACKET_LENGTH];

	// Encode the packet
	encode_packet(packet, &packet_cnt);

	// Wakup, send, and standby of the S2LP
	S2LP_WakeUp();
	S2LP_Send(packet, PACKET_LENGTH);
	S2LP_Standby();

	// Print the encoded packet
	print_encoded_packet(packet);
}

// TODO : redo the values
// Function to threshold the mel vectors
char threshold_mel_vectors() {

	// Correct the threshold to compensate for the mean (instead of a division)
	#if THRESHOLD_MODE == 1
		q15_t corrected_threshold =  THRESHOLD_LV1_VALUE;
	#elif THRESHOLD_MODE == 2
		q15_t corrected_threshold =  THRESHOLD_LV2_VALUE;
	#elif THRESHOLD_MODE == 3
		q15_t corrected_threshold =  THRESHOLD_LV3_VALUE;
	#endif
 
    // Check the threshold
    #if THRESHOLD_MODE == 1 // Threshold on the sum of all mel vectors
		q31_t total_sum = 0;
		// Unrolled loop for better performance for each mel vector	
		for (size_t i = 0; i < MEL_NUM_VEC; i++) {
			// Unrolled inner loop - process 4 elements at once
			size_t j = 0;
			for (; j <= MEL_VEC_LENGTH - 4; j += 4) {
				// Load 4 values at once for better pipelining
				q15_t val0 = mel_vectors[i][j];
				q15_t val1 = mel_vectors[i][j+1];
				q15_t val2 = mel_vectors[i][j+2];
				q15_t val3 = mel_vectors[i][j+3];
				
				// Calculate absolute values using branchless operations
				// This avoids branch prediction failures
				total_sum += ((val0 ^ (val0 >> 15)) - (val0 >> 15)) +
							((val1 ^ (val1 >> 15)) - (val1 >> 15)) +
							((val2 ^ (val2 >> 15)) - (val2 >> 15)) +
							((val3 ^ (val3 >> 15)) - (val3 >> 15));
			}
			
			// Handle remaining elements
			for (; j < MEL_VEC_LENGTH; j++) {
				q15_t val = mel_vectors[i][j];
				total_sum += (val ^ (val >> 15)) - (val >> 15); // Branchless absolute value
			}
			
			// Early threshold check every 2 vectors
			if ((i & 0x1) == 0x1 && total_sum > corrected_threshold) {
				return 1;
			}
		}
		// Final threshold check
		if (total_sum > corrected_threshold) {
			return 1;
		}
    #elif THRESHOLD_MODE == 2 // Threshold on the mean of each mel vector
	// Unrolled loop for better performance for each mel vector	
	for (size_t i=0; i < MEL_NUM_VEC; i++) {
			q31_t sum = 0;
			size_t j = 0;
			for (; j < MEL_VEC_LENGTH - 4; j += 4) {
				q15_t val0 = mel_vectors[i][j];
				q15_t val1 = mel_vectors[i][j+1];
				q15_t val2 = mel_vectors[i][j+2];
				q15_t val3 = mel_vectors[i][j+3];

				sum +=  ((val0 ^ (val0 >> 15)) - (val0 >> 15)) +
						((val1 ^ (val1 >> 15)) - (val1 >> 15)) +
						((val2 ^ (val2 >> 15)) - (val2 >> 15)) +
						((val3 ^ (val3 >> 15)) - (val3 >> 15));
			}

			// Handle remaining elements
			for (; j < MEL_VEC_LENGTH; j++) {
				q15_t val = mel_vectors[i][j];
				sum += (val ^ (val >> 15)) - (val >> 15); // Branchless absolute value
			}

			// Threshold check
			if (sum > corrected_threshold) {
				return 1;
			}
		}		
    #elif THRESHOLD_MODE == 3 // Threshold on the maximum absolute value of each mel vector
		// Unrolled loop for better performance for each mel vector
		for (size_t i=0; i < MEL_NUM_VEC; i++) {
			q15_t max_found = 0;
			size_t j = 0;
			for (; j < MEL_VEC_LENGTH - 4; j += 4) {
				q15_t val0 = mel_vectors[i][j];
				q15_t val1 = mel_vectors[i][j+1];
				q15_t val2 = mel_vectors[i][j+2];
				q15_t val3 = mel_vectors[i][j+3];

				// Calculate the absolute value, and check if its greater than the corrected threshold
				max_found |= ((val0 ^ (val0 >> 15)) - (val0 >> 15)) > corrected_threshold;
				max_found |= ((val1 ^ (val1 >> 15)) - (val1 >> 15)) > corrected_threshold;
				max_found |= ((val2 ^ (val2 >> 15)) - (val2 >> 15)) > corrected_threshold;
				max_found |= ((val3 ^ (val3 >> 15)) - (val3 >> 15)) > corrected_threshold;
			}
			// Handle remaining elements
			for (; j < MEL_VEC_LENGTH; j++) {
				q15_t val = mel_vectors[i][j];
				max_found |= (val ^ (val >> 15)) - (val >> 15) > corrected_threshold; // Branchless absolute value
			}
			// Threshold check
			if (max_found) {
				return 1;
			}
		}
    #endif
	
    return 0;
}

// Callback function for the ADC, it is called when one of the two buffers is full
static void ADC_Callback(int buf_cplt) {
    // Check if ADC buffer is ready
    if (ADCDataRdy[1-buf_cplt]) {
        DEBUG_PRINT("Error: ADC Data buffer full\r\n");
        Error_Handler();
    }

    // Process the current buffer
    ADCDataRdy[buf_cplt] = 1;
    // Process a copy of the buffer, not the original
	memcpy((void*)ADCProcessBuf, (void*)ADCData[buf_cplt], ADC_BUF_SIZE * sizeof(uint16_t));
	Full_spectrogram_compute((q15_t*) ADCProcessBuf, mel_vectors);
    ADCDataRdy[buf_cplt] = 0;

    // Check if we have collected all mel vectors
	#if THRESHOLD_MODE > 0
		// If the threshold is reached, print and send the spectrogram
		if (threshold_mel_vectors()) 
			return;
	#endif

	// If we have collected all mel vectors, print and send the spectrogram
	send_spectrogram();
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
	ADC_Callback(1);
}

void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc)
{
	ADC_Callback(0);
}
