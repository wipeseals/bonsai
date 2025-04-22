#include <stdint.h>
#include <stdbool.h>

#include "lib/stdio.h"

int main(void) {
    const char* hello = "Hello, World!\n";
    stdio_init();
    stdio_puts(hello);
    return 0;
}