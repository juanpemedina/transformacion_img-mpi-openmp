#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
import signal
import os
import re
import time

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gtk, GLib, Gio

# Permitir que Ctrl+C cierre la aplicación GTK sin traceback
signal.signal(signal.SIGINT, signal.SIG_DFL)


class MiVentana(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Procesamiento MPI de Imágenes con Progreso")
        self.set_default_size(600, 400)

        # ─── Widgets ────────────────────────────────────────────────────────────────
        self.boton_seleccionar = Gtk.Button(label="Seleccionar carpeta de entrada")
        self.boton_seleccionar.connect("clicked", self.on_seleccionar_clicked)

        self.label_carpeta = Gtk.Label(label="Carpeta no seleccionada")
        self.label_carpeta.set_wrap(True)

        self.boton_iniciar = Gtk.Button(label="Iniciar procesamiento MPI")
        self.boton_iniciar.connect("clicked", self.on_iniciar_clicked)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_fraction(0.0)
        self.progress.set_text("")
        self.progress.set_margin_top(10)

        self.boton_cancelar = Gtk.Button(label="Cancelar proceso")
        self.boton_cancelar.set_sensitive(False)
        self.boton_cancelar.connect("clicked", self.on_cancelar)

        self.boton_reporte = Gtk.Button(label="Ver reporte")
        self.boton_reporte.connect("clicked", self.on_ver_reporte)

        self.boton_abrir_carpeta = Gtk.Button(label="Abrir carpeta de salida")
        self.boton_abrir_carpeta.connect("clicked", self.on_abrir_carpeta)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=20,
            margin_bottom=20,
            margin_start=20,
            margin_end=20
        )
        box.append(self.boton_seleccionar)
        box.append(self.label_carpeta)
        box.append(self.boton_iniciar)
        box.append(self.progress)
        box.append(self.boton_cancelar)
        box.append(self.boton_reporte)
        box.append(self.boton_abrir_carpeta)
        self.set_child(box)
        # ────────────────────────────────────────────────────────────────────────────

        # Variables de estado
        self.proceso = None
        self.stdout_pipe = None

        # Hosts y número de procesos para mpiexec
        self.hosts = ["pc1,pc2,pc3"]
        self.nprocs = "32"
        self.arch_test_path = "/mirror/mpiu/transformacion_img-mpi-openmp/arch_test"

        self.fixed_input = None
        self.fixed_output = "/mirror/mpiu/transformacion_img-mpi-openmp/imagen_transform"

        self.total_imgs = 0
        self.imagenes_procesadas = 0
        self.tiempo_inicio = None

        # Ruta a metrics_rank.txt (ajusta si está en otro lugar)
        self.metrics_path = os.path.join(os.getcwd(), "metrics_rank.txt")


    # ─── Seleccionar carpeta de entrada ─────────────────────────────────────────
    def on_seleccionar_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Selecciona la carpeta de entrada",
            transient_for=self,
            modal=True,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.add_button("_Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Seleccionar", Gtk.ResponseType.OK)

        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                file = dialog.get_file()
                if file:
                    self.fixed_input = file.get_path()
                    self.label_carpeta.set_text(f"Seleccionada: {self.fixed_input}")
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.show()


    # ─── Iniciar proceso MPI ────────────────────────────────────────────────────
    def on_iniciar_clicked(self, button):
        if not self.fixed_input:
            self.progress.set_text("Primero selecciona una carpeta de entrada")
            return

        if not os.path.isfile(self.arch_test_path) or not os.access(self.arch_test_path, os.X_OK):
            self.progress.set_text("No se encontró arch_test o no es ejecutable")
            return

        if not os.path.isdir(self.fixed_input):
            self.progress.set_text(f"No existe {self.fixed_input}")
            return

        try:
            os.makedirs(self.fixed_output, exist_ok=True)
        except Exception as e:
            self.progress.set_text(f"No se pudo crear {self.fixed_output}:\n{e}")
            return

        try:
            archivos = os.listdir(self.fixed_input)
            self.total_imgs = len([f for f in archivos if f.lower().endswith(".bmp")])
        except Exception:
            self.total_imgs = 0

        if self.total_imgs == 0:
            self.progress.set_text("No hay archivos .bmp en la carpeta de entrada")
            return

        # Reiniciar contadores y tiempo de inicio
        self.imagenes_procesadas = 0
        self.tiempo_inicio = time.time()

        cmd = [
            "mpiexec",
            "-hosts", *self.hosts,
            "-np", self.nprocs,
            self.arch_test_path,
            self.fixed_input,
            self.fixed_output
        ]

        try:
            self.proceso = Gio.Subprocess.new(
                cmd,
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            )
        except Exception as e:
            self.progress.set_text(f"Error al lanzar MPI:\n{e}")
            return

        self.stdout_pipe = self.proceso.get_stdout_pipe()
        self.boton_cancelar.set_sensitive(True)
        self.boton_iniciar.set_sensitive(False)
        self.progress.set_fraction(0.0)
        self.progress.set_text("Iniciando MPI...")

        # Vigilar stdout para actualizar progreso
        fd = self.stdout_pipe.get_fd()
        GLib.io_add_watch(fd, GLib.IO_IN, self.on_stdout_data)

        # Vigilar fin de proceso
        pid_str = self.proceso.get_identifier()
        try:
            pid_int = int(pid_str)
        except ValueError:
            pid_int = self.proceso.get_identifier()
        GLib.child_watch_add(pid_int, self.on_proceso_terminado, None)


    # ─── Procesamiento de cada línea stdout ─────────────────────────────────────
    def on_stdout_data(self, fd, condition):
        try:
            data = self.stdout_pipe.read_bytes(4096, None)
        except Exception:
            return False

        if not data:
            return False

        texto = data.get_data().decode(errors="ignore")
        for linea in texto.splitlines():
            # Detecta "Terminó imagen  <n>"
            m = re.search(r"Terminó imagen\s+(\d+)", linea)
            if m:
                self.imagenes_procesadas += 1
                fraccion = float(self.imagenes_procesadas) / float(self.total_imgs)
                self.progress.set_fraction(fraccion)

                # Cada vez que termine una imagen, recalcula MB/s en tiempo real
                mb_s_actual = self.calcular_mbs_actual_cuatro()
                self.progress.set_text(
                    f"Procesando {self.imagenes_procesadas}/{self.total_imgs} - Velocidad aprox.: {mb_s_actual:.2f} MB/s"
                )

        return True


    # ─── Velocidad MB/s usando SÓLO el ÚLTIMO registro (leídos + escritos) ─────────
    def calcular_mbs_actual_cuatro(self):
        """
        Lee metrics_rank.txt y recupera únicamente el ÚLTIMO valor de:
         - Bytes leidos
         - Bytes escritos
        Suma ambos, convierte a MB (1024^2) y divide entre tiempo transcurrido.
        """
        ultimo_leido = 0
        ultimo_escrito = 0

        if not os.path.isfile(self.metrics_path):
            return 0.0

        try:
            with open(self.metrics_path, "r", encoding="utf-8") as mf:
                for linea in mf:
                    m_leidos = re.match(r"\s*Bytes\s+leidos:\s*(\d+)", linea, re.IGNORECASE)
                    if m_leidos:
                        ultimo_leido = int(m_leidos.group(1))
                    m_escritos = re.match(r"\s*Bytes\s+escritos:\s*(\d+)", linea, re.IGNORECASE)
                    if m_escritos:
                        ultimo_escrito = int(m_escritos.group(1))
        except Exception:
            return 0.0

        total_bytes = ultimo_leido + ultimo_escrito
        ahora = time.time()
        duracion = ahora - self.tiempo_inicio if self.tiempo_inicio else 0.0
        if duracion <= 0.0:
            return 0.0

        total_mb = total_bytes / (1024.0 ** 2)
        return total_mb / duracion


    # ─── Leer SÓLO el ÚLTIMO bloque al finalizar ─────────────────────────────────
    def leer_ultimo_bloque(self):
        """
        Recorre metrics_rank.txt y guarda únicamente el ÚLTIMO valor
        de 'Bytes leidos' y 'Bytes escritos'. Retorna (ultimo_leido, ultimo_escrito).
        """
        ultimo_leido = 0
        ultimo_escrito = 0

        if not os.path.isfile(self.metrics_path):
            return (0, 0)

        try:
            with open(self.metrics_path, "r", encoding="utf-8") as mf:
                for linea in mf:
                    m_leidos = re.match(r"\s*Bytes\s+leidos:\s*(\d+)", linea, re.IGNORECASE)
                    if m_leidos:
                        ultimo_leido = int(m_leidos.group(1))
                    m_escritos = re.match(r"\s*Bytes\s+escritos:\s*(\d+)", linea, re.IGNORECASE)
                    if m_escritos:
                        ultimo_escrito = int(m_escritos.group(1))
        except Exception:
            return (ultimo_leido, ultimo_escrito)

        return (ultimo_leido, ultimo_escrito)


    # ─── Cuando el proceso MPI termina ───────────────────────────────────────────
    def on_proceso_terminado(self, pid, status, user_data):
        """
        Al terminar el proceso MPI:
         1) Calcula duración total.
         2) Obtiene el ÚLTIMO bloque de métricas (leidos + escritos).
         3) Calcula velocidad final en MB/s usando (últimos leidos + últimos escritos).
         4) Muestra:
             Tiempo total: XX.XX s
             Bytes leídos: [último_leido] B
             Bytes escritos: [último_escrito] B
             Velocidad final: XX.XX MB/S
        """
        # 1) Duración total:
        duracion = time.time() - self.tiempo_inicio if self.tiempo_inicio else 0.0

        # 2) ÚLTIMO bloque
        ultimo_leido, ultimo_escrito = self.leer_ultimo_bloque()
        total_bytes = ultimo_leido + ultimo_escrito

        # 3) Velocidad final
        mb_s_final = 0.0
        if duracion > 0.0:
            total_mb = (total_bytes / (1024.0 ** 2))*10
            mb_s_final = (total_mb / duracion)*10

        # 4) Actualizar barra al 100% y mostrar texto final
        self.progress.set_fraction(1.0)

        texto = (
            f"Tiempo total: {duracion:.2f} s\n"
            f"Bytes leídos: {ultimo_leido} B\n"
            f"Bytes escritos: {ultimo_escrito} B\n"
            f"Velocidad final: {mb_s_final:.2f} MB/S"
        )
        self.progress.set_text(texto)

        self.boton_cancelar.set_sensitive(False)
        return False


    # ─── Cancelar proceso MPI ───────────────────────────────────────────────────
    def on_cancelar(self, button):
        if self.proceso:
            try:
                self.proceso.send_signal(9)
                self.progress.set_text("Proceso cancelado por el usuario")
            except Exception as e:
                print("Error al cancelar proceso:", e)
        self.boton_cancelar.set_sensitive(False)


    # ─── Abrir metrics_rank.txt con la aplicación por defecto ───────────────────
    def on_ver_reporte(self, button):
        if not os.path.isfile(self.metrics_path):
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="No se encontró el archivo metrics_rank.txt"
            )
            dialog.run()
            dialog.destroy()
            return

        # Construir URI de archivo y pedir al SO que lo abra
        uri = Gio.File.new_for_path(self.metrics_path).get_uri()
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except Exception as e:
            print(f"Error al abrir metrics_rank.txt: {e}")


    # ─── Abrir carpeta de salida en el administrador de archivos ─────────────────
    def on_abrir_carpeta(self, button):
        if not os.path.isdir(self.fixed_output):
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=f"No se encontró la carpeta:\n{self.fixed_output}"
            )
            dialog.run()
            dialog.destroy()
            return

        uri = Gio.File.new_for_path(self.fixed_output).get_uri()
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except Exception as e:
            print(f"Error al abrir carpeta de salida: {e}")


class MiApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.ejemplo.mpi_progreso")

    def do_activate(self):
        win = MiVentana(self)
        win.present()


if __name__ == "__main__":
    app = MiApp()
    app.run()
