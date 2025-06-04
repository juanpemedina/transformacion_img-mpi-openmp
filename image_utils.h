#ifndef IMAGE_UTILS_H
#define IMAGE_UTILS_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <omp.h>

struct Image {
    int width;
    int height;
    int size;
    unsigned char *data;
    char name[256];
};

static inline struct Image load_image(const char *filepath) {
    FILE *f = fopen(filepath, "rb");
    if (!f) {
        perror("Error abriendo imagen");
        exit(1);
    }

    unsigned char header[54];
    fread(header, sizeof(unsigned char), 54, f);

    int width = *(int*)&header[18];
    int height = *(int*)&header[22];
    int size = *(int*)&header[34];

    unsigned char *data = (unsigned char *)malloc(size);
    fread(data, sizeof(unsigned char), size, f);
    fclose(f);

    struct Image img = { width, height, size, data };
    return img;
}

static inline struct Image duplicate_image(const struct Image *img) {
    struct Image copy;
    copy.width = img->width;
    copy.height = img->height;
    copy.size = img->size;
    copy.data = (unsigned char *)malloc(img->size);
    memcpy(copy.data, img->data, img->size);
    return copy;
}

static inline void save_image(const char *filepath, struct Image *img, unsigned char *header) {
    FILE *f = fopen(filepath, "wb");
    if (!f) {
        perror("Error guardando imagen");
        exit(1);
    }
    fwrite(header, sizeof(unsigned char), 54, f);
    fwrite(img->data, sizeof(unsigned char), img->size, f);
    fclose(f);
}

static inline void to_grayscale(struct Image *img) {
    int widthWithPadding = (img->width * 3 + 3) & -4;
    #pragma omp parallel for collapse(2)
    for (int y = 0; y < img->height; y++) {
        for (int x = 0; x < img->width; x++) {
            int idx = y * widthWithPadding + x * 3;
            unsigned char b = img->data[idx];
            unsigned char g = img->data[idx + 1];
            unsigned char r = img->data[idx + 2];
            unsigned char gray = (unsigned char)(r * 0.21 + g * 0.72 + b * 0.07);
            img->data[idx] = img->data[idx + 1] = img->data[idx + 2] = gray;
        }
    }
}

static inline void flip_horizontal(struct Image *img) {
    int widthWithPadding = (img->width * 3 + 3) & -4;
    #pragma omp parallel for collapse(2)
    for (int y = 0; y < img->height; y++) {
        for (int x = 0; x < img->width / 2; x++) {
            int left = y * widthWithPadding + x * 3;
            int right = y * widthWithPadding + (img->width - x - 1) * 3;
            for (int i = 0; i < 3; i++) {
                unsigned char tmp = img->data[left + i];
                img->data[left + i] = img->data[right + i];
                img->data[right + i] = tmp;
            }
        }
    }
}

static inline void flip_vertical(struct Image *img) {
    int widthWithPadding = (img->width * 3 + 3) & -4;
    unsigned char *tempRow = (unsigned char *)malloc(widthWithPadding);
    #pragma omp parallel for
    for (int y = 0; y < img->height / 2; y++) {
        int top = y * widthWithPadding;
        int bottom = (img->height - y - 1) * widthWithPadding;
        memcpy(tempRow, &img->data[top], widthWithPadding);
        memcpy(&img->data[top], &img->data[bottom], widthWithPadding);
        memcpy(&img->data[bottom], tempRow, widthWithPadding);
    }
    free(tempRow);
}

static inline void blur(struct Image *img, int kernelSize) {
    int widthWithPadding = (img->width * 3 + 3) & -4;
    int radius = kernelSize / 2;
    unsigned char *tempData = (unsigned char *)malloc(img->size);
    unsigned char *output = (unsigned char *)malloc(img->size);

    #pragma omp parallel for collapse(2)
    for (int y = 0; y < img->height; y++) {
        for (int x = 0; x < img->width; x++) {
            int sum[3] = {0, 0, 0};
            int count = 0;
            for (int k = -radius; k <= radius; k++) {
                int nx = x + k;
                if (nx < 0 || nx >= img->width) continue;
                int idx = y * widthWithPadding + nx * 3;
                for (int c = 0; c < 3; c++) sum[c] += img->data[idx + c];
                count++;
            }
            int idx_out = y * widthWithPadding + x * 3;
            for (int c = 0; c < 3; c++) tempData[idx_out + c] = (unsigned char)(sum[c] / count);
        }
    }

    #pragma omp parallel for collapse(2)
    for (int y = 0; y < img->height; y++) {
        for (int x = 0; x < img->width; x++) {
            int sum[3] = {0, 0, 0};
            int count = 0;
            for (int k = -radius; k <= radius; k++) {
                int ny = y + k;
                if (ny < 0 || ny >= img->height) continue;
                int idx = ny * widthWithPadding + x * 3;
                for (int c = 0; c < 3; c++) sum[c] += tempData[idx + c];
                count++;
            }
            int idx_out = y * widthWithPadding + x * 3;
            for (int c = 0; c < 3; c++) output[idx_out + c] = (unsigned char)(sum[c] / count);
        }
    }

    memcpy(img->data, output, img->size);
    free(tempData);
    free(output);
}

static inline void free_image(struct Image *img) {
    free(img->data);
}

#endif
