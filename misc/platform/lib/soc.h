#pragma once

#include <stdint.h>

#include "driver/uart.h"

// TODO: move address definition to linker script
typedef struct {
    volatile uartreg_t* uart0;
} soc_t;
volatile soc_t _soc = {
    (volatile uartreg_t*)0x01000000
};

/// @brief get uart module for stdout
/// @return  uart module pointer
volatile uartreg_t* get_stdout_uart() {
    return _soc.uart0;
}
