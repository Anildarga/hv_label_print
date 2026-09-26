from __future__ import annotations

import tkinter as tk
from datetime import date

from models.hv.nomenclature.module_id import ParsedModuleId
from models.hv.nomenclature.serial_number import ParsedSerialNumber


def format_date_display(value: date) -> str:
    return value.strftime("%d/%B/%Y")


def apply_serial_fields(vars_map: dict[str, tk.StringVar], parsed: ParsedSerialNumber) -> None:
    vars_map["plant"].set(parsed.plant)
    vars_map["line"].set(parsed.line)
    vars_map["serial_count"].set(parsed.serial_count)
    vars_map["date"].set(format_date_display(parsed.as_date))


def apply_module_fields(vars_map: dict[str, tk.StringVar], parsed: ParsedModuleId) -> None:
    
    vars_map["variant"].set(parsed.variant)
    vars_map["plant"].set(parsed.plant)
    vars_map["line"].set(parsed.line)
    vars_map["shift"].set(parsed.shift)
    if "cell_mfr" in vars_map:
        vars_map["cell_mfr"].set(parsed.cell_mfr)
    if "group" in vars_map:
        vars_map["group"].set(parsed.group)