#include <stdint.h>
#include <stdbool.h>

/*
 * Simple UART TX/RX module
 *
 * Register Map(32bit register):
 * | addr       | name     | RW | default    | description |
 * | ---------- | -------- | -- | ---------- | ----------- |
 * | 0x00000000 | RX_VALID | RO | 0x00000000 | bit[0] = RX data valid |
 * | 0x00000004 | RX_DATA  | RO | 0x00000000 | RX data |
 * | 0x00000008 | TX_FULL  | RO | 0x00000000 | bit[0] = TX full |
 * | 0x0000000C | TX_DATA  | RW | 0x00000000 | TX data |
 */
typedef struct {
    volatile uint32_t RX_VALID;
    volatile uint32_t RX_DATA;
    volatile uint32_t TX_FULL;
    volatile uint32_t TX_DATA;
} uartreg_t;
volatile uartreg_t* uart0 = (volatile uartreg_t*)0x01000000; // TODO: move address definition to linker script

int main(void) {
    const char* hello = "Hello, World!\n";
    while (true) {
        while (uart0->TX_FULL) {}
        uart0->TX_DATA = *hello++;
        if (*hello == '\0') {
            break;
        }
    }
    return 0;
}