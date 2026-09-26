from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from models.hv.gui.constants import CATEGORY_OPTIONS, variants_for_category
from models.hv.gui.layout import FIELD_FONT, FIELD_IPADY


def add_category_field(
    parent: ttk.Frame,
    category_var: tk.StringVar,
    *,
    grid_column: int | None = None,
) -> ttk.Combobox:
    """Add Category field — same style as other config fields, bold label, no box."""
    compact = grid_column is not None
    frame = ttk.Frame(parent)
    if compact:
        frame.grid(row=0, column=grid_column, sticky="nsew", padx=(0, 8))
    else:
        frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

    frame.columnconfigure(0, weight=1)
    ttk.Label(frame, text="Category", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
    combo = ttk.Combobox(
        frame, textvariable=category_var, values=CATEGORY_OPTIONS,
        state="readonly", font=FIELD_FONT,
    )
    combo.pack(fill=tk.X, pady=(2, 0), ipady=2 if compact else FIELD_IPADY)
    return combo


def bind_category_variant(
    category_var: tk.StringVar,
    variant_var: tk.StringVar,
    variant_widget: ttk.Combobox,
    on_variant_update: Callable[[], None],
) -> None:

    def _apply_category_rules(*_args: object) -> None:
        options = variants_for_category(category_var.get())
        variant_widget.configure(values=options)
        if variant_var.get() not in options:
            variant_var.set(options[0])
        on_variant_update()

    category_var.trace_add("write", _apply_category_rules)
    _apply_category_rules()