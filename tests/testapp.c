/*
 * Minimal test application for bindle integration tests.
 *
 * Links against libz to ensure at least one non-blacklisted library
 * must be bundled alongside the executable.  Prints the zlib version
 * and exits with status 0 on success.
 */
#include <stdio.h>
#include <zlib.h>

int main(void) {
    printf("hello from bindle! zlib version: %s\n", zlibVersion());
    return 0;
}