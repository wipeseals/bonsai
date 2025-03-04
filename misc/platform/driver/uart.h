#pragma once

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

// TODO: inline (for performance)
void uart_init(volatile uartreg_t* uart);
bool uart_is_tx_full(volatile uartreg_t* uart);
void uart_send_nonblock(volatile uartreg_t* uart, char data);
void uart_send(volatile uartreg_t* uart, char data);
bool uart_is_rx_valid(volatile uartreg_t* uart);
char uart_recv(volatile uartreg_t* uart);
bool uart_recv_nonblock(volatile uartreg_t* uart, char* data);
