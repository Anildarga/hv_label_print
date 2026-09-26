from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk


def setup_hardware_scanner(
    entry: ttk.Entry,
    variable: tk.StringVar,
    on_scan: Callable[[str], None],
) -> None:
    """Bind Enter key so wedge-style scanners can submit scanned text."""
    entry.configure(font=("Consolas", 11))

    def _submit_scan(_event: tk.Event | None = None) -> str:
        scanned = variable.get().strip()
        if scanned:
            on_scan(scanned)
        return "break"

    entry.bind("<Return>", _submit_scan)
    entry.focus_set()