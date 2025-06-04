#ifndef METRICS_H
#define METRICS_H

#include <stdio.h>

static inline void write_metrics(const char *filename, const char *img_name, int bytes_read, int bytes_written) {
    FILE *f = fopen(filename, "a");
    if (!f) { perror("metrics.txt"); return; }

    fprintf(f, "Imagen: %s\n", img_name);
    fprintf(f, "Bytes leídos: %d\n", bytes_read);
    fprintf(f, "Bytes escritos: %d\n", bytes_written);
    fprintf(f, "---------------------------\n");
    fclose(f);
}

static inline double calculate_mips(int total_instructions, double total_time_sec) {
    return (total_instructions / 1e6) / total_time_sec;
}

#endif
