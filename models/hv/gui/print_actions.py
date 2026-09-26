from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from models.hv.printing.spooler import save_zpl, send_zpl


def add_print_controls(
    parent: ttk.Frame,
    print_var: tk.StringVar,
    on_print: object,
) -> ttk.Button:

    ttk.Label(parent, text="Print", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

    controls = ttk.Frame(parent)
    controls.pack(anchor=tk.W, pady=(4, 0))

    ttk.Combobox(
        controls,
        textvariable=print_var,
        values=["print", "pdf"],
        state="readonly",
        width=10,
    ).pack(side=tk.LEFT, padx=(0, 6))

    print_btn = ttk.Button(controls, text="Print", command=on_print, width=10)  # type: ignore[arg-type]
    print_btn.pack(side=tk.LEFT)
    return print_btn


def dispatch_zpl(
    parent: tk.Misc,
    zpl: str,
    mode: str,
    *,
    default_name: str = "label.zpl",
    printer_name: str | None = None,
) -> None:
   
    try:
        if mode == "print":
            if printer_name:
                send_zpl(zpl, printer_name=printer_name)
            else:
                send_zpl(zpl)
            messagebox.showinfo("Print Success", "Label sent to printer.", parent=parent)
            return

        # Save as .txt with the same ZPL content
        txt_name = default_name.rsplit(".", 1)[0] + ".txt"
        path = filedialog.asksaveasfilename(
            parent=parent,
            title="Save Label as Text",
            defaultextension=".txt",
            initialfile=txt_name,
            filetypes=[("Text files", "*.txt"), ("ZPL files", "*.zpl"), ("All files", "*.*")],
        )
        if not path:
            return

        saved = save_zpl(zpl, path)
        messagebox.showinfo("Save", f"Label saved to:\n{saved}", parent=parent)
    except OSError as exc:
        messagebox.showerror("Print", str(exc), parent=parent)


def dispatch_zpl_batch(
    parent: tk.Misc,
    zpl_labels: list[str],
    mode: str,
    *,
    default_name: str = "labels.zpl",
) -> None:
    
    if not zpl_labels:
        messagebox.showwarning("Print", "No labels to print.", parent=parent)
        return

    try:
        if mode == "print":
            for zpl in zpl_labels:
                send_zpl(zpl)
            messagebox.showinfo(
                "Print",
                f"{len(zpl_labels)} label(s) sent to Zebra ZD421.",
                parent=parent,
            )
            return

        path = filedialog.asksaveasfilename(
            parent=parent,
            title="Save ZPL Labels",
            defaultextension=".zpl",
            initialfile=default_name,
            filetypes=[("ZPL files", "*.zpl"), ("All files", "*.*")],
        )
        if not path:
            return

        saved = save_zpl("".join(zpl_labels), path)
        messagebox.showinfo("Save", f"Labels saved to:\n{saved}", parent=parent)
    except OSError as exc:
        messagebox.showerror("Print", str(exc), parent=parent)