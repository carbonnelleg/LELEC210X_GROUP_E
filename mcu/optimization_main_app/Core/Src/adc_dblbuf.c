#include <adc_dblbuf.h>
#include "config.h"
#include "main.h"
#include "spectrogram.h"
#include "arm_math.h"
#include "utils.h"
#include "s2lp.h"
#include "packet.h"

// Timings for printing the feature vectors
#if MEASURE_CYCLES_PRINT_FV == 0
	#define START_CYCLE_COUNT_PRINT_FV()
	#define STOP_CYCLE_COUNT_PRINT_FV(str)
#else
	#define START_CYCLE_COUNT_PRINT_FV() start_cycle_count()
	#define STOP_CYCLE_COUNT_PRINT_FV(str) stop_cycle_count(str)
#endif

// Timings for printing the packets
#if MEASURE_CYCLES_PRINT_PACKET == 0
	#define START_CYCLE_COUNT_PRINT_PACKET()
	#define STOP_CYCLE_COUNT_PRINT_PACKET(str)
#else
	#define START_CYCLE_COUNT_PRINT_PACKET() start_cycle_count()
	#define STOP_CYCLE_COUNT_PRINT_PACKET(str) stop_cycle_count(str)
#endif

// Timings for sending the packet
#if MEASURE_CYCLES_ENCODE_PACKET == 0
	#define START_CYCLE_COUNT_ENCODE_PACKET()
	#define STOP_CYCLE_COUNT_ENCODE_PACKET(str)
#else
	#define START_CYCLE_COUNT_ENCODE_PACKET() start_cycle_count()
	#define STOP_CYCLE_COUNT_ENCODE_PACKET(str) stop_cycle_count(str)
#endif

// Timings for sending the packet
#if MEASURE_CYCLES_SEND_PACKET == 0
	#define START_CYCLE_COUNT_SEND_PACKET()
	#define STOP_CYCLE_COUNT_SEND_PACKET(str)
#else
	#define START_CYCLE_COUNT_SEND_PACKET() start_cycle_count()
	#define STOP_CYCLE_COUNT_SEND_PACKET(str) stop_cycle_count(str)
#endif

// Timings for the whole spectrogram computation
#if MEASURE_CYCLES_FULL_SPECTROGRAM == 0
	#define START_CYCLE_COUNT_SPECTROGRAM()
	#define STOP_CYCLE_COUNT_SPECTROGRAM(str)
#else
	#define START_CYCLE_COUNT_SPECTROGRAM() start_cycle_count()
	#define STOP_CYCLE_COUNT_SPECTROGRAM(str) stop_cycle_count(str)
#endif

static volatile uint16_t ADCDoubleBuf[2*ADC_BUF_SIZE]; /* ADC group regular conversion data (array of data) */
static volatile uint16_t* ADCData[2] = {&ADCDoubleBuf[0], &ADCDoubleBuf[ADC_BUF_SIZE]};
static volatile uint8_t ADCDataRdy[2] = {0, 0};

static volatile uint8_t cur_melvec = 0;
static q15_t mel_vectors[N_MELVECS][MELVEC_LENGTH];

static uint32_t packet_cnt = 0;

static volatile int32_t rem_n_bufs = 0;

// Function to start the ADC acquisition
int StartADCAcq(int32_t n_bufs) {
	rem_n_bufs = n_bufs;
	cur_melvec = 0;
	if (rem_n_bufs != 0) {
		return HAL_ADC_Start_DMA(&hadc1, (uint32_t *)ADCDoubleBuf, 2*ADC_BUF_SIZE);
	} else {
		return HAL_OK;
	}
}

// Function to check if the ADC acquisition is finished
int IsADCFinished(void) {
	return (rem_n_bufs == 0);
}

// Function to stop the ADC acquisition
static void StopADCAcq() {
	HAL_ADC_Stop_DMA(&hadc1);
}

// Function to print the spectrogram (feature vectors) separated by commas
static void print_spectrogram(void) {
#if (DEBUGP == 1 & PRINT_FV_SPECTROGRAM == 1)
	START_CYCLE_COUNT_PRINT_FV();
	DEBUG_PRINT("Acquisition complete, sending the following FVs\r\n");
	for(unsigned int j=0; j < N_MELVECS; j++) {
		DEBUG_PRINT("FV #%u:\t", j+1);
		for(unsigned int i=0; i < MELVEC_LENGTH; i++) {
			DEBUG_PRINT("%.2f, ", q15_to_float(mel_vectors[j][i]));
		}
		DEBUG_PRINT("\r\n");
	}
	STOP_CYCLE_COUNT_PRINT_FV("Print Feature Vec");
#endif
}

// Function to print the encoded packet in hexadecimal format
static void print_encoded_packet(uint8_t *packet) {
#if (DEBUGP == 1 & PRINT_ENCODED_PACKET == 1)
	START_CYCLE_COUNT_PRINT_PACKET();
	char hex_encoded_packet[2*PACKET_LENGTH+1];
	hex_encode(hex_encoded_packet, packet, PACKET_LENGTH);
	DEBUG_PRINT("DF:HEX:%s\r\n", hex_encoded_packet);
	STOP_CYCLE_COUNT_PRINT_PACKET("Print Encoded Packet");
#endif
}

// Function to encode the packet
static void encode_packet(uint8_t *packet, uint32_t* packet_cnt) {
	// BE encoding of each mel coef
	for (size_t i=0; i<N_MELVECS; i++) {
		for (size_t j=0; j<MELVEC_LENGTH; j++) {
			(packet+PACKET_HEADER_LENGTH)[(i*MELVEC_LENGTH+j)*2]   = mel_vectors[i][j] >> 8;
			(packet+PACKET_HEADER_LENGTH)[(i*MELVEC_LENGTH+j)*2+1] = mel_vectors[i][j] & 0xFF;
		}
	}
	// Write header and tag into the packet.
	make_packet(packet, PAYLOAD_LENGTH, 0, *packet_cnt);
	*packet_cnt += 1;
	if (*packet_cnt == 0) {
		// Should not happen as packet_cnt is 32-bit and we send at most 1 packet per second.
		DEBUG_PRINT("Packet counter overflow.\r\n");
		Error_Handler();
	}
}

// Function to create and send the packet
static void send_spectrogram() {
	uint8_t packet[PACKET_LENGTH];

	START_CYCLE_COUNT_ENCODE_PACKET();
	encode_packet(packet, &packet_cnt);
	STOP_CYCLE_COUNT_ENCODE_PACKET("Encode Packet");

	START_CYCLE_COUNT_SEND_PACKET();
	S2LP_Send(packet, PACKET_LENGTH);
	STOP_CYCLE_COUNT_SEND_PACKET("Send Packet");

	print_encoded_packet(packet);
}

#if THRESHOLD_MODE == THRESHOLD_HARD_FULL
	#define CORRECTED_THRESHOLD_VALUE THRESHOLD_VALUE*N_MELVECS*MELVEC_LENGTH
#elif THRESHOLD_MODE == THRESHOLD_HARD_PER_MELVEC
	#define CORRECTED_THRESHOLD_VALUE THRESHOLD_VALUE*MELVEC_LENGTH
#elif THRESHOLD_MODE == THRESHOLD_LOOSE
	#define CORRECTED_THRESHOLD_VALUE THRESHOLD_VALUE
#endif

// Function to threshold the mel vectors
char threshold_mel_vectors() {
	q15_t corrected_threshold = CORRECTED_THRESHOLD_VALUE;
	#if THRESHOLD_MODE == THRESHOLD_HARD_FULL
		q15_t accumulator = 0;
		for (size_t i=0; i < N_MELVECS; i++) {
			for (size_t j=0; j < MELVEC_LENGTH; j++) {
				accumulator += abs(mel_vectors[i][j]);
				if (accumulator > corrected_threshold) {
					return 1;
				}
			}
		}
	#elif THRESHOLD_MODE == THRESHOLD_HARD_PER_MELVEC
		for (size_t i=0; i < N_MELVECS; i++) {
			q15_t accumulator = 0;
			for (size_t j=0; j < MELVEC_LENGTH; j++) {
				accumulator += abs(mel_vectors[i][j]);
				if (accumulator > corrected_threshold) {
					return 1;
				}
			}
		}
	#elif THRESHOLD_MODE == THRESHOLD_LOOSE
		for (size_t i=0; i < N_MELVECS; i++) {
			for (size_t j=0; j < MELVEC_LENGTH; j++) {
				if (abs(mel_vectors[i][j]) > corrected_threshold) {
					return 1;
				}
			}
		}
	#endif
	return 0;
}

// Callback function for the ADC, it is called when one of the two buffers is full
static void ADC_Callback(int buf_cplt) {
    if (rem_n_bufs != -1) {
        rem_n_bufs--;
    }

    // Check if ADC buffer is ready
    if (ADCDataRdy[1-buf_cplt]) {
        DEBUG_PRINT("Error: ADC Data buffer full\r\n");
        Error_Handler();
    }

    // Process the current buffer
    ADCDataRdy[buf_cplt] = 1;
    START_CYCLE_COUNT_SPECTROGRAM();
    Spectrogram_Format((q15_t *)ADCData[buf_cplt]);
    Spectrogram_Compute((q15_t *)ADCData[buf_cplt], mel_vectors[cur_melvec]);
    STOP_CYCLE_COUNT_SPECTROGRAM("Full Spectrogram");
    cur_melvec++;
    ADCDataRdy[buf_cplt] = 0;

    // Check if we have collected all mel vectors
    if (rem_n_bufs == 0) {
		#if USE_THRESHOLD == 1
			// If the threshold is reached, print and send the spectrogram
			if (threshold_mel_vectors()) {
				print_spectrogram();
				send_spectrogram();
			}
		#else
			print_spectrogram();
			send_spectrogram();
		#endif

        #if ACQ_MODE == ACQ_STOP_START
            StopADCAcq();
        #elif ACQ_MODE == ACQ_OVERLAP
            // Reset counters and restart acquisition
            cur_melvec = 0;
            rem_n_bufs = N_MELVECS; // Reset to collect next set of vectors
            // ADC continues running
        #endif
    }
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
	ADC_Callback(1);
}

void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc)
{
	ADC_Callback(0);
}
