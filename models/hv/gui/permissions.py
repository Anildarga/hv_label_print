from __future__ import annotations

from tkinter import ttk


def set_combobox_enabled(combo: ttk.Combobox, enabled: bool) -> None:
    combo.configure(state="readonly" if enabled else "disabled")


def set_entry_enabled(entry: ttk.Entry, enabled: bool) -> None:
    entry.configure(state="normal" if enabled else "disabled")


def set_button_enabled(button: ttk.Button, enabled: bool) -> None:
    button.state(["!disabled"] if enabled else ["disabled"])