#include "uart.h"

void uart_init(volatile uartreg_t* uart) {
    // nop
}

bool uart_is_tx_full(volatile uartreg_t* uart) {
    return uart->TX_FULL;
}

void uart_send_nonblock(volatile uartreg_t* uart, char data) {
    if (uart_is_tx_full(uart)) {
        return;
    }
    uart->TX_DATA = data;
}

void uart_send(volatile uartreg_t* uart, char data) {
    while (uart_is_tx_full(uart)) {}
    uart->TX_DATA = data;
}

bool uart_is_rx_valid(volatile uartreg_t* uart) {
    return uart->RX_VALID;
}

char uart_recv(volatile uartreg_t* uart) {
    while (!uart->RX_VALID) {}
    return uart->RX_DATA & 0xFF;
}

bool uart_recv_nonblock(volatile uartreg_t* uart, char* data) {
    if (!uart->RX_VALID) {
        return false;
    }
    *data = uart->RX_DATA & 0xFF;
    return true;
}