#!/usr/bin/env python3
"""Interfaz visual para exportar listas de LectorManga en Windows."""

from __future__ import annotations

import contextlib
import io
import shlex
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import export_lists

DEFAULT_BASE_URL = "https://lectormanga.nakamasweb.com/profile/follow"


class ExportApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ZonaTMO/LectorManga Exporter")
        self.root.geometry("760x560")

        self.cookie_file_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(Path.cwd() / "exports"))
        self.base_url_var = tk.StringVar(value=DEFAULT_BASE_URL)

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

        ttk.Button(frame, text="Exportar listas", command=self.run_export).grid(row=8, column=0, columnspan=3, sticky="we", pady=(14, 10))

        self.log = tk.Text(frame, height=16, wrap="word")
        self.log.grid(row=9, column=0, columnspan=3, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)
        frame.rowconfigure(9, weight=1)

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
        self.root.update_idletasks()

    def run_export(self) -> None:
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

        self._log(f"$ export_lists.py {shlex.join(cli_args)}")
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                return_code = export_lists.main(cli_args)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo ejecutar export_lists.py\n{exc}")
            return

        stdout_value = stdout_buffer.getvalue().strip()
        stderr_value = stderr_buffer.getvalue().strip()

        if stdout_value:
            self._log(stdout_value)
        if stderr_value:
            self._log("[stderr]\n" + stderr_value)

        if return_code == 0:
            messagebox.showinfo("Listo", f"Exportación finalizada en:\n{output_dir}")
        else:
            messagebox.showwarning("Advertencia", "La exportación terminó con errores. Revisa el log.")


def main() -> int:
    root = tk.Tk()
    ExportApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
