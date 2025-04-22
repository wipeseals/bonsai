#include <stddef.h>

#include "stdio.h"
#include "driver/uart.h"

volatile uartreg_t *uart = NULL;

void stdio_init() {
    uart = get_stdout_uart();
}

void stdio_putc(char c) {
    uart_send(uart, c);
}

void stdio_puts(const char* s) {
    // null文字まで出力
    while (*s != '\0') {
        stdio_putc(*s++);
    }
}

char stdio_getc() {
    return uart_recv(uart);
}

bool stdio_gets(char* s, uint32_t size) {
    // buffer size内で改行が入力されるまで読み込む
    uint32_t i;
    for (i = 0; i < size - 1; i++) {
        s[i] = stdio_getc();
        if (s[i] == '\n') {
            s[i] = '\0';
            return true;
        }
    }
    // overflow
    s[i] = '\0';
    return false;
}
