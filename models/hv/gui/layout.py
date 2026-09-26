from __future__ import annotations

import tkinter as tk
from tkinter import ttk

LABEL_FONT = ("Segoe UI", 10, "bold")
FIELD_FONT = ("Segoe UI", 10)
DISPLAY_FONT = ("Consolas", 11)
VALUE_FONT = ("Segoe UI", 10)
HEADING_FONT = ("Segoe UI", 13, "bold")

FIELD_IPADY = 5
CELL_PADX = (0, 10)

_STYLES_CONFIGURED = False


def configure_styles(root: tk.Misc) -> None:
    global _STYLES_CONFIGURED
    if _STYLES_CONFIGURED:
        return

    style = ttk.Style(root)

    style.configure(
        "Plain.TEntry",
        borderwidth=0,
        relief="sunken", #flat
        padding=0,
        fieldbackground=style.lookup("TFrame", "background") or "SystemButtonFace",
    )
    style.map(
        "Plain.TEntry",
        fieldbackground=[("readonly", style.lookup("TFrame", "background") or "SystemButtonFace")],
    )

    style.configure("TCombobox", justify="center")
    root.option_add("*TCombobox*Listbox.justify", "center")

    _STYLES_CONFIGURED = True


def configure_equal_columns(frame: ttk.Frame, count: int, *, uniform: str = "field") -> None:
    for column in range(count):
        frame.columnconfigure(column, weight=1, uniform=uniform)


def add_field_cell(
    parent: ttk.Frame,
    column: int,
    label: str,
    widget: tk.Widget,
    *,
    rowspan: int = 1,
    padx: tuple[int, int] = CELL_PADX,
) -> ttk.Frame:
    cell = ttk.Frame(parent)
    cell.grid(row=0, column=column, rowspan=rowspan, sticky="nsew", padx=padx)
    cell.columnconfigure(0, weight=1)

    ttk.Label(cell, text=label, font=LABEL_FONT).pack(anchor=tk.W)
    widget.pack(fill=tk.X, pady=(5, 0), ipady=FIELD_IPADY)
    return cell