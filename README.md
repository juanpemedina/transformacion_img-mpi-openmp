#README - Sistema Distribuido de Procesamiento de Imágenes con MPI y OpenMP
### Objetivo

Implementar un sistema distribuido con **3 computadoras en red** que aplique **6 transformaciones** sobre **600 imágenes BMP**, usando paralelización híbrida con **MPI y OpenMP**.

### Tecnologías Usadas

* Lenguaje C
* MPI (Message Passing Interface)
* OpenMP
* Qt Designer + Python (GUI)
* SSH (Secure Shell)
* NFS (Network File System)
* VirtualBox
* Ubuntu Server 22.04

---

## Cómo Compilar y Ejecutar

###  Compilación

Desde el nodo maestro (PC1), compila el programa con soporte para OpenMP:

Si tienes arm
```bash
mpicc -fopenmp main_MPI.c -o processor_arm
```
Si tienes x86
```bash
mpicc -fopenmp main_MPI.c -o processor_x86
```

### Ejecución

1. Asegúrate de tener configurado las IPs de los nodos:

```
192.168.1.11:1
192.168.1.10:1
192.168.1.12:1
```

2. Ejecuta el sistema desde el maestro:

```bash
mpiexec -np 24 -hosts pc1,pc2,pc3 /ruta/arch_test /ruta/imagenes_bmp
```


3. Las imágenes procesadas aparecerán en `imagen_transform/` y las métricas en archivos `metrics_rank.txt`.

### Requisitos Previos

* Conectividad LAN o NAT (si usas VirtualBox)
* SSH sin contraseña configurado (`ssh-keygen` y `ssh-copy-id`)
* Directorio `/mirror/` compartido vía NFS
* Carpeta de entrada `imagenes_bmp/` con imágenes BMP

---

## Acceso a la Documentación

Este documento contiene toda la información técnica del proyecto.

Si deseas consultar una versión visual o extenderlo a una wiki:
[Ver Documentación en GitHub Wiki (enlace de ejemplo)](https://github.com/juanpemedina/transformacion_img-mpi-openmp/wiki/01_descripci%C3%B3n)

---

## 🖼️ Captura del Sistema (GUI)

![Captura del sistema](https://drive.google.com/uc?export=view&id=1hY6Uc2dhRBsOyIrK2bJMrrgzRfcSLXHp)


---

## ✅ Autores

* Santiago Santos, Juan Medina, Hector Reyes
* Tecnológico de Monterrey · TC3003 · Junio 2025
