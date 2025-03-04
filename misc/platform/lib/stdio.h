#pragma once

#include <stdint.h>
#include <stdbool.h>

#include "soc.h"

void stdio_init();
void stdio_putc(char c);
void stdio_puts(const char* s);
char stdio_getc();
bool stdio_gets(char* s, uint32_t size);