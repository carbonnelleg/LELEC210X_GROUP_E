#include <adc_dblbuf.h>
#include "config.h"
#include "main.h"
#include "spectrogram.h"
#include "arm_math.h"
#include "utils.h"
#include "s2lp.h"
#include "packet.h"

static uint16_t ADCDoubleBuf[2 * ADC_BUF_SIZE];             // DMA buffer
static uint16_t ADCWorkingBuf[ADC_BUF_SIZE];                // For processing
static q15_t    MELWorkingBuf[MEL_NUM_VEC][MEL_VEC_LENGTH]; // For processing
static volatile uint8_t buffer_ready = 0;                   // Flag set when new data is ready
static uint8_t current_proc_buf = 0;				        // Current buffer being processed
static uint32_t packet_cnt = 0;                             // Packet counter

// Function to stop the ADC acquisition
void StopADCAcq() {
	HAL_ADC_Stop_DMA(&hadc1);
}

// Function to start the ADC acquisition
int StartADCAcq() {
	// Reset the buffer ready flag
	buffer_ready = 0;
	// Reset the current processing buffer index
	current_proc_buf = 0;
	// Reset the packet counter
	packet_cnt = 0;

	// Start the ADC in DMA mode
	HAL_ADC_Start_DMA(&hadc1, (uint32_t*)ADCDoubleBuf, 2 * ADC_BUF_SIZE);
	HAL_ADC_Start_IT(&hadc1);
	return HAL_OK;
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
			(packet+PACKET_HEADER_LENGTH)[(i*MEL_VEC_LENGTH+j)*2]   = MELWorkingBuf[i][j] >> 8;
			(packet+PACKET_HEADER_LENGTH)[(i*MEL_VEC_LENGTH+j)*2+1] = MELWorkingBuf[i][j] & 0xFF;
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
        const q15_t *mel_ptr = MELWorkingBuf[i];
        
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
	#if (NO_S2LP_SLEEP == 0)
		S2LP_WakeUp();
	#endif
	S2LP_Send(packet, PACKET_LENGTH);
	// Wait for the transmission to finish
	#if (NO_S2LP_SLEEP == 0)
		S2LP_Standby();
	#endif

	// Print the encoded packet
	print_encoded_packet(packet);
}

// Function to threshold the mel vectors
char threshold_MELWorkingBuf() {

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
				q15_t val0 = MELWorkingBuf[i][j];
				q15_t val1 = MELWorkingBuf[i][j+1];
				q15_t val2 = MELWorkingBuf[i][j+2];
				q15_t val3 = MELWorkingBuf[i][j+3];
				
				// Calculate absolute values using branchless operations
				// This avoids branch prediction failures
				total_sum += ((val0 ^ (val0 >> 15)) - (val0 >> 15)) +
							((val1 ^ (val1 >> 15)) - (val1 >> 15)) +
							((val2 ^ (val2 >> 15)) - (val2 >> 15)) +
							((val3 ^ (val3 >> 15)) - (val3 >> 15));
			}
			
			// Handle remaining elements
			for (; j < MEL_VEC_LENGTH; j++) {
				q15_t val = MELWorkingBuf[i][j];
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
				q15_t val0 = MELWorkingBuf[i][j];
				q15_t val1 = MELWorkingBuf[i][j+1];
				q15_t val2 = MELWorkingBuf[i][j+2];
				q15_t val3 = MELWorkingBuf[i][j+3];

				sum +=  ((val0 ^ (val0 >> 15)) - (val0 >> 15)) +
						((val1 ^ (val1 >> 15)) - (val1 >> 15)) +
						((val2 ^ (val2 >> 15)) - (val2 >> 15)) +
						((val3 ^ (val3 >> 15)) - (val3 >> 15));
			}

			// Handle remaining elements
			for (; j < MEL_VEC_LENGTH; j++) {
				q15_t val = MELWorkingBuf[i][j];
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
				q15_t val0 = MELWorkingBuf[i][j];
				q15_t val1 = MELWorkingBuf[i][j+1];
				q15_t val2 = MELWorkingBuf[i][j+2];
				q15_t val3 = MELWorkingBuf[i][j+3];

				// Calculate the absolute value, and check if its greater than the corrected threshold
				max_found |= ((val0 ^ (val0 >> 15)) - (val0 >> 15)) > corrected_threshold;
				max_found |= ((val1 ^ (val1 >> 15)) - (val1 >> 15)) > corrected_threshold;
				max_found |= ((val2 ^ (val2 >> 15)) - (val2 >> 15)) > corrected_threshold;
				max_found |= ((val3 ^ (val3 >> 15)) - (val3 >> 15)) > corrected_threshold;
			}
			// Handle remaining elements
			for (; j < MEL_VEC_LENGTH; j++) {
				q15_t val = MELWorkingBuf[i][j];
				max_found |= (val ^ (val >> 15)) - (val >> 15) > corrected_threshold; // Branchless absolute value
			}
			// Threshold check
			if (max_found) {
				return 1;
			}
		}
    #endif
	
    return 1; // Default to 1 (threshold reached)
}

// Function to process the ADC data
void ProcessADCData() {
	// Check if the buffer is ready
	if (buffer_ready) {
		// Reset the buffer ready flag
		buffer_ready = 0;

		// Process the current buffer
		Full_spectrogram_compute((q15_t*) ADCWorkingBuf, MELWorkingBuf);

		if (!threshold_MELWorkingBuf()) {
			// If the threshold is not reached, skip sending the packet
			DEBUG_PRINT("Threshold not reached, skipping\r\n");
			return;
		}

		// Send the spectrogram
		send_spectrogram();
	}
}

void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef* hadc) {
    if (buffer_ready) return; // Prevent overwrite if still processing

    memcpy(ADCWorkingBuf, &ADCDoubleBuf[0], ADC_BUF_SIZE * sizeof(uint16_t));
    buffer_ready = 1;
    current_proc_buf = 0;
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc) {
    if (buffer_ready) return;

    memcpy(ADCWorkingBuf, &ADCDoubleBuf[ADC_BUF_SIZE], ADC_BUF_SIZE * sizeof(uint16_t));
    buffer_ready = 1;
    current_proc_buf = 1;
}