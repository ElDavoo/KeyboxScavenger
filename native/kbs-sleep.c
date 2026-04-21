#define _GNU_SOURCE

#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int parse_seconds(const char *input, uint64_t *out_seconds) {
  char *end = NULL;
  unsigned long long parsed = 0ULL;

  if (input == NULL || *input == '\0') {
    return -1;
  }

  errno = 0;
  parsed = strtoull(input, &end, 10);
  if (errno != 0 || end == input || *end != '\0') {
    return -1;
  }

  *out_seconds = (uint64_t)parsed;
  return 0;
}

int main(int argc, char **argv) {
  struct timespec req;
  struct timespec rem;
  uint64_t seconds = 0;

  if (argc != 2) {
    fprintf(stderr, "usage: %s <seconds>\n", argv[0]);
    return 2;
  }

  if (parse_seconds(argv[1], &seconds) != 0) {
    fprintf(stderr, "invalid seconds: %s\n", argv[1]);
    return 2;
  }

  req.tv_sec = (time_t)seconds;
  req.tv_nsec = 0;

  for (;;) {
    if (clock_nanosleep(CLOCK_BOOTTIME, 0, &req, &rem) == 0) {
      return 0;
    }

    if (errno != EINTR) {
      perror("clock_nanosleep");
      return 1;
    }

    req = rem;
  }
}
