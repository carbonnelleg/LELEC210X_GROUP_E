/*
 * utils.h
 */

#ifndef INC_UTILS_H_
#define INC_UTILS_H_

void start_cycle_count();
void stop_cycle_count(char *s);

void hex_encode(char* s, const unsigned char* buf, size_t len);

void fast_debug_print(const char* data, size_t size);

#endif /* INC_UTILS_H_ */
