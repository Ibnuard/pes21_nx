/* Admit an actual local canary through the current runtime packet parser. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t exhibition_home_team_id = 1, exhibition_away_team_id = 2;
static uint32_t competition_frontend_scoreboard(uint32_t h, uint32_t a) {
    (void)h; (void)a; return 11;
}
static void scene_runtime_note(const char *a, const char *b) { (void)a; (void)b; }
#define PESNX_SCOREBOARD_HOST_TEST
#include "../source/scoreboard_runtime.inc"

static unsigned char *read_owned(const char *path, size_t *bytes) {
    FILE *file = fopen(path, "rb");
    assert(file && !fseek(file, 0, SEEK_END));
    long length = ftell(file);
    assert(length > 0 && length <= 2000000 && !fseek(file, 0, SEEK_SET));
    unsigned char *data = malloc((size_t)length);
    assert(data && fread(data, 1, (size_t)length, file) == (size_t)length);
    fclose(file); *bytes = (size_t)length; return data;
}

int main(int argc, char **argv) {
    assert(argc == 3);
    size_t original_bytes, packet_bytes;
    unsigned char *mobile = read_owned(argv[1], &original_bytes);
    unsigned char *packet = read_owned(argv[2], &packet_bytes);
    size_t base = 0;
    while (base + 108 <= original_bytes && memcmp(mobile + base, "TXP2", 4)) ++base;
    assert(base + 108 <= original_bytes);
    unsigned char *original = mobile + base;
    original_bytes -= base;
    uint32_t size = 0;
    assert(scoreboard_payload(packet, packet_bytes, original, original_bytes, &size) == packet + 32);
    assert(size == packet_bytes - 32);
    assert(!scoreboard_payload(packet, packet_bytes - 1, original, original_bytes, &size));
    packet[packet_bytes - 1] ^= 1;
    assert(!scoreboard_payload(packet, packet_bytes, original, original_bytes, &size));
    packet[packet_bytes - 1] ^= 1;
    original[30] ^= 1;
    assert(!scoreboard_payload(packet, packet_bytes, original, original_bytes, &size));
    original[30] ^= 1;
    assert(scoreboard_payload(packet, packet_bytes, original, original_bytes, &size) == packet + 32);
    printf("current scoreboard_payload admits c11: %u target bytes; corrupt packet/source rejected\n", size);
    free(mobile); free(packet);
    return 0;
}
