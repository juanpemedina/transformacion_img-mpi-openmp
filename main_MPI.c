#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <omp.h>
#include <mpi.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include "image_utils.h"
#include "metrics.h"

#define NUM_IMAGES 100
#define KERNEL_VALUE 55
#define TAG_WORK 1
#define TAG_STOP 2

void create_folder_OS(const char *path) {
    struct stat statusBuffer = {0};
    if (stat(path, &statusBuffer) == -1) {
#ifdef _WIN32
        if (mkdir(path)) perror("Error creando directorio");
#else
        if (mkdir(path, 0700)) perror("Error creando directorio");
#endif
    }
}

void process_image(int img_number, int rank) {
    char folder[] = "./imagenes_bmp/";
    char filename[512];
    sprintf(filename, "%simagen_%03d.bmp", folder, img_number);  // ¡CORRECTO!

    if (access(filename, F_OK) != 0) {
        char hostname[128];
        gethostname(hostname, sizeof(hostname));
        fprintf(stderr, "Rango %d no puede abrir %s -> %s\n", rank, filename, hostname);
        return;
    }

    char hostname[128];
    gethostname(hostname, sizeof(hostname));
    printf("Proceso %d -> Imagen %03d -> %s\n", rank, img_number, hostname);

    struct Image img = load_image(filename);
    int bytes_leidos = img.size;
    int bytes_escritos = 0;

    FILE *f = fopen(filename, "rb");
    unsigned char header[54];
    fread(header, sizeof(unsigned char), 54, f);
    fclose(f);

    char sub_folder[256];
    sprintf(sub_folder, "imagen_transform/img_%03d", img_number);
    create_folder_OS(sub_folder);

    #pragma omp parallel for schedule(dynamic, 1) reduction(+:bytes_escritos)
    for (int t = 0; t < 6; t++) {
        struct Image temp = duplicate_image(&img);
        char name[256];

        switch (t) {
            case 0:
                to_grayscale(&temp);
                sprintf(name, "%s/imagen_%03d_gray.bmp", sub_folder, img_number);
                break;
            case 1:
                to_grayscale(&temp);
                flip_horizontal(&temp);
                sprintf(name, "%s/imagen_%03d_gray_hmirror.bmp", sub_folder, img_number);
                break;
            case 2:
                to_grayscale(&temp);
                flip_vertical(&temp);
                sprintf(name, "%s/imagen_%03d_gray_vmirror.bmp", sub_folder, img_number);
                break;
            case 3:
                flip_horizontal(&temp);
                sprintf(name, "%s/imagen_%03d_col_hmirror.bmp", sub_folder, img_number);
                break;
            case 4:
                flip_vertical(&temp);
                sprintf(name, "%s/imagen_%03d_col_vmirror.bmp", sub_folder, img_number);
                break;
            case 5:
                blur(&temp, KERNEL_VALUE);
                sprintf(name, "%s/imagen_%03d_blur_%d.bmp", sub_folder, img_number, KERNEL_VALUE);
                break;
        }

        save_image(name, &temp, header);
        bytes_escritos += temp.size;
        free_image(&temp);
    }

    free_image(&img);

    char nombre_img[64];
    sprintf(nombre_img, "imagen_%03d.bmp", img_number);
    #pragma omp critical
    write_metrics("metrics_rank.txt", nombre_img, bytes_leidos, bytes_escritos);

    printf("[MPI %d] Terminó imagen %03d con %d bytes escritos\n", rank, img_number, bytes_escritos);
}

int main(int argc, char *argv[]) {
    MPI_Init(&argc, &argv);

    int rank, nprocs;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nprocs);

    omp_set_num_threads(omp_get_max_threads());

    double start_time = MPI_Wtime();

    if (rank == 0) create_folder_OS("imagen_transform");
    MPI_Barrier(MPI_COMM_WORLD); // Sincronizar antes de comenzar

    if (rank == 0) {
        // Maestro
        int next_img = 1;
        int active_workers = nprocs - 1;

        while (active_workers > 0) {
            MPI_Status status;
            int request;
            MPI_Recv(&request, 1, MPI_INT, MPI_ANY_SOURCE, TAG_WORK, MPI_COMM_WORLD, &status);

            if (next_img <= NUM_IMAGES) {
                MPI_Send(&next_img, 1, MPI_INT, status.MPI_SOURCE, TAG_WORK, MPI_COMM_WORLD);
                next_img++;
            } else {
                int stop = -1;
                MPI_Send(&stop, 1, MPI_INT, status.MPI_SOURCE, TAG_STOP, MPI_COMM_WORLD);
                active_workers--;
            }
        }
    } else {
        // Trabajadores
        while (1) {
            int dummy = 0;
            MPI_Send(&dummy, 1, MPI_INT, 0, TAG_WORK, MPI_COMM_WORLD);

            int img_number;
            MPI_Status status;
            MPI_Recv(&img_number, 1, MPI_INT, 0, MPI_ANY_TAG, MPI_COMM_WORLD, &status);

            if (status.MPI_TAG == TAG_STOP) break;

            process_image(img_number, rank);
        }
    }

    MPI_Barrier(MPI_COMM_WORLD);
    if (rank == 0) {
        double end_time = MPI_Wtime();
        printf("Tiempo total (distribución dinámica): %.2f segundos\n", end_time - start_time);
    }

    MPI_Finalize();
    return 0;
}
