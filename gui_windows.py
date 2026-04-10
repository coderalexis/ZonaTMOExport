#!/usr/bin/env python3
"""Interfaz visual para exportar listas de LectorManga en Windows."""

from __future__ import annotations

import io
import queue
import shlex
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import export_lists

DEFAULT_BASE_URL = "https://lectormanga.nakamasweb.com/profile/follow/true"

LOG_POLL_MS = 100  # cada cuánto revisa la cola de mensajes


class QueueWriter:
    """Reemplaza stdout/stderr para enviar cada print() a una cola thread-safe."""

    def __init__(self, log_queue: queue.Queue) -> None:
        self._queue = log_queue

    def write(self, text: str) -> None:
        if text and text.strip():
            self._queue.put(text)

    def flush(self) -> None:
        pass


class ExportApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ZonaTMO/LectorManga Exporter")
        self.root.geometry("760x560")

        self.cookie_file_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(Path.cwd() / "exports"))
        self.base_url_var = tk.StringVar(value=DEFAULT_BASE_URL)
        self.with_progress_var = tk.BooleanVar(value=False)

        self._running = False
        self._log_queue: queue.Queue[str] = queue.Queue()

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=14)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(
            frame,
            text="Exportador de listas (LectorManga)",
            font=("Segoe UI", 14, "bold"),
        )
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        info = ttk.Label(
            frame,
            text=(
                "1) Exporta tus cookies con la extensión 'Get cookies.txt LOCALLY'.\n"
                "2) Selecciona el archivo cookies.txt y la carpeta de salida.\n"
                "3) Pulsa 'Exportar listas'."
            ),
            justify="left",
        )
        info.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))

        ttk.Label(frame, text="Archivo cookies.txt").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.cookie_file_var, width=70).grid(row=3, column=0, columnspan=2, sticky="we", padx=(0, 8))
        ttk.Button(frame, text="Buscar...", command=self.select_cookie_file).grid(row=3, column=2, sticky="we")

        ttk.Label(frame, text="Carpeta de salida").grid(row=4, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self.output_dir_var, width=70).grid(row=5, column=0, columnspan=2, sticky="we", padx=(0, 8))
        ttk.Button(frame, text="Buscar...", command=self.select_output_dir).grid(row=5, column=2, sticky="we")

        ttk.Label(frame, text="Base URL").grid(row=6, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self.base_url_var, width=70).grid(row=7, column=0, columnspan=3, sticky="we")

        ttk.Checkbutton(
            frame,
            text="Incluir progreso de capítulos (más lento)",
            variable=self.with_progress_var,
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.export_btn = ttk.Button(frame, text="Exportar listas", command=self.run_export)
        self.export_btn.grid(row=9, column=0, columnspan=3, sticky="we", pady=(14, 10))

        self.log = tk.Text(frame, height=16, wrap="word")
        self.log.grid(row=10, column=0, columnspan=3, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)
        frame.rowconfigure(10, weight=1)

    def select_cookie_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecciona tu cookies.txt",
            filetypes=[("Cookies text", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.cookie_file_var.set(path)

    def select_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Selecciona carpeta destino")
        if path:
            self.output_dir_var.set(path)

    def _log(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def _poll_log_queue(self) -> None:
        """Lee mensajes de la cola y los muestra en el widget de log."""
        while True:
            try:
                msg = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self._log(msg)

        if self._running:
            self.root.after(LOG_POLL_MS, self._poll_log_queue)

    def _export_thread(self, cli_args: list[str], output_dir: str) -> None:
        """Ejecuta export_lists.main() en un hilo secundario."""
        writer = QueueWriter(self._log_queue)
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout = writer  # type: ignore[assignment]
            sys.stderr = writer  # type: ignore[assignment]
            return_code = export_lists.main(cli_args)
        except Exception as exc:
            self._log_queue.put(f"[ERROR] {exc}")
            return_code = 1
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        # Notificar al hilo principal que terminó
        self.root.after(0, self._on_export_finished, return_code, output_dir)

    def _on_export_finished(self, return_code: int, output_dir: str) -> None:
        """Callback en el hilo principal cuando el export termina."""
        # Vaciar mensajes pendientes
        self._running = False
        self._poll_log_queue()

        self.export_btn.configure(state="normal")

        if return_code == 0:
            messagebox.showinfo("Listo", f"Exportación finalizada en:\n{output_dir}")
        else:
            messagebox.showwarning("Advertencia", "La exportación terminó con errores. Revisa el log.")

    def run_export(self) -> None:
        if self._running:
            return

        cookie_file = self.cookie_file_var.get().strip()
        output_dir = self.output_dir_var.get().strip()
        base_url = self.base_url_var.get().strip() or DEFAULT_BASE_URL

        if not cookie_file:
            messagebox.showerror("Falta archivo", "Selecciona el archivo cookies.txt.")
            return
        if not Path(cookie_file).exists():
            messagebox.showerror("Archivo inválido", "El archivo cookies.txt no existe.")
            return
        if not output_dir:
            messagebox.showerror("Falta carpeta", "Selecciona una carpeta de salida.")
            return

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        cli_args = [
            "--base-url",
            base_url,
            "--cookie-file",
            cookie_file,
            "--output-dir",
            output_dir,
        ]

        if self.with_progress_var.get():
            cli_args.append("--with-progress")

        self.log.delete("1.0", "end")
        self._log(f"$ export_lists.py {shlex.join(cli_args)}")

        self._running = True
        self.export_btn.configure(state="disabled")
        self.root.after(LOG_POLL_MS, self._poll_log_queue)

        thread = threading.Thread(
            target=self._export_thread,
            args=(cli_args, output_dir),
            daemon=True,
        )
        thread.start()


def main() -> int:
    root = tk.Tk()
    ExportApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
