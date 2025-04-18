/*
 * utils.c
 */
#include "config.h"
#include "stm32l4xx_hal.h"
#include "stm32l4xx_hal_uart.h"
#include "main.h"
#include "utils.h"

#if (NO_PERF == 0)

volatile uint8_t counting_cycles = 0;

void start_cycle_count() {
	uint32_t prim = __get_PRIMASK();
	__disable_irq();
	if (counting_cycles) {
		DEBUG_PRINT("Tried re-entrant cycle counting.\r\n");
		Error_Handler();
	} else {
		counting_cycles = 1;
	}
	if (!prim) {
		__enable_irq();
	}
	DWT->CTRL |= 1 ; // enable the counter
	DWT->CYCCNT = 0; // reset the counter
}
void stop_cycle_count(char *s) {
	uint32_t res = DWT->CYCCNT;
	counting_cycles = 0;
	printf("[PERF] ");
	printf(s);
	printf(" %lu cycles.\r\n", res);
}

#else

void start_cycle_count() {}
void stop_cycle_count(char *s) {}

#endif // PERF_COUNT


// Encode the binary buffer buf of length len in the null-terminated string s
// (which must have length at least 2*len+1).
void hex_encode(char* s, const uint8_t* buf, size_t len) {
    s[2*len] = '\0';
    for (size_t i=0; i<len; i++) {
        s[i*2] = "0123456789abcdef"[buf[i] >> 4];
        s[i*2+1] = "0123456789abcdef"[buf[i] & 0xF];
    }
}

extern UART_HandleTypeDef hlpuart1; // Declared in main.c

void fast_debug_print(const char* data, size_t size) {
	// Send the data to the UART
	HAL_UART_Transmit(&hlpuart1, (uint8_t*)data, size, HAL_MAX_DELAY);
}	