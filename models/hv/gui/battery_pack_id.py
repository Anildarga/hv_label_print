from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from models.hv.gui.battery_parameters import build_battery_parameters_panel, set_battery_parameters
from models.hv.gui.category_controls import add_category_field, bind_category_variant
from models.hv.gui.constants import VARIANT_OPTIONS, VARIANT_PARAMS, format_pack_qr_data, get_emark, get_type_of_reess
from models.hv.gui.layout import FIELD_FONT, FIELD_IPADY, HEADING_FONT, LABEL_FONT, configure_equal_columns
from models.hv.gui.permissions import set_combobox_enabled
from models.hv.gui.print_actions import dispatch_zpl
from models.hv.gui.scan_history import open_scan_history
from models.hv.gui.scanner import setup_hardware_scanner
from models.hv.nomenclature.scan_handler import ScanType, identify_scan
from models.hv.nomenclature.serial_number import parse_serial_number
from models.hv.printing.constants import PRINTER_PACK_ID
from models.hv.printing.labels import build_battery_pack_id_label
from datetime import datetime

from models.hv.session.pack_store import save_pack_serial
from models.hv.session.pack_id_scan_log import PackIdScanRecord
from models.hv.session.pack_id_scan_log import append_scan_record as append_pack_id_scan_record


class BatteryPackIdGUI:

    def __init__(self, parent: tk.Misc | None = None, *, is_admin: bool = False, session=None) -> None:
        self.is_admin = is_admin
        self._session = session
        if parent is None:
            self.root = tk.Tk()
            self.host = self.root
            self.root.title("Battery Pack ID")
            self.root.geometry("1100x520")
        elif isinstance(parent, (tk.Tk, tk.Toplevel)):
            self.root = parent
            self.host = parent
            self.root.title("Battery Pack ID")
        else:
            self.root = parent.winfo_toplevel()
            self.host = parent

        self._param_labels: dict[str, ttk.Label] = {}
        self._category_combo: ttk.Combobox | None = None
        self._variant_combo: ttk.Combobox | None = None
        self._serial_number_entry: ttk.Entry | None = None
        self.category_var = tk.StringVar(value="Domestic")
        self.variant_var = tk.StringVar(value=VARIANT_OPTIONS[-1])
        self.scanner_var = tk.StringVar()
        self.print_var = tk.StringVar(value="print")

        self._build_ui()
        self._on_variant_change()
        self._apply_permissions()


    def _build_ui(self) -> None:
        container = ttk.Frame(self.host, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text="Battery Pack ID",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor=tk.W, pady=(0, 14))

        self._build_config_row(container)
        self._build_scanner_section(container)
        self._param_labels, self.serial_number_var, self._serial_number_entry, self._captions = (
            build_battery_parameters_panel(container, plain_labels=True)
        )

    def _build_config_row(self, parent: ttk.Frame) -> None:
        config_frame = ttk.Frame(parent, padding=(0, 0, 0, 10))
        config_frame.pack(fill=tk.X)

        ttk.Label(config_frame, text="Configuration", font=HEADING_FONT).pack(anchor=tk.W, pady=(0, 6))

        row = ttk.Frame(config_frame)
        row.pack(fill=tk.X)
        configure_equal_columns(row, 2)

        self._category_combo = add_category_field(row, self.category_var, grid_column=0)
        self._variant_combo = self._add_config_dropdown(
            row, 1, "Variant", self.variant_var, VARIANT_OPTIONS
        )

        if self._variant_combo is not None:
            bind_category_variant(
                self.category_var,
                self.variant_var,
                self._variant_combo,
                self._on_variant_change,
            )
        self.variant_var.trace_add("read", self._on_variant_change)

    def _add_config_dropdown(
        self,
        parent: ttk.Frame,
        column: int,
        label: str,
        variable: tk.StringVar,
        values: list[str],
    ) -> ttk.Combobox:
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, sticky="nsew", padx=(0, 10))
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text=label, font=LABEL_FONT).pack(anchor=tk.W)
        combo = ttk.Combobox(
            frame,
            textvariable=variable,
            values=values,
            state="readonly",
            font=FIELD_FONT,
        )
        combo.pack(fill=tk.X, pady=(5, 0), ipady=FIELD_IPADY)
        return combo

    def _on_variant_change(self, *_args: object) -> None:
        if not self._param_labels:
            return

        variant = self.variant_var.get()
        params = VARIANT_PARAMS.get(variant, VARIANT_PARAMS[VARIANT_OPTIONS[-1]])

        category = self.category_var.get()

        set_battery_parameters(
            self._param_labels,
            rated_capacity=params["rated_capacity"],
            max_voltage=params["max_voltage"],
            model_number=get_type_of_reess(variant),
            tac_number=params["tac_number"],
            emark=params["emark"],
            category=category,
            captions=self._captions,
        )

    def _build_scanner_section(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent, padding=(0, 0, 0, 10))
        bar.pack(fill=tk.X)
        bar.columnconfigure(0, weight=1)

        ttk.Label(bar, text="Scanner", font=HEADING_FONT).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6)
        )

        scanner_entry = ttk.Entry(bar, textvariable=self.scanner_var, font=FIELD_FONT)
        scanner_entry.grid(row=1, column=0, sticky="ew", ipady=FIELD_IPADY + 1)
        setup_hardware_scanner(scanner_entry, self.scanner_var, self._on_scan)

        controls = ttk.Frame(bar)
        controls.grid(row=1, column=1, sticky=tk.E, padx=(10, 0))
        ttk.Combobox(
            controls, textvariable=self.print_var, values=["print", "pdf"],
            state="readonly", width=8, justify="center",
        ).pack(side=tk.LEFT, ipady=FIELD_IPADY, padx=(0, 8))
        ttk.Button(controls, text="Clear", command=self._on_clear, width=8).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(controls, text="History", command=self._open_history, width=10).pack(side=tk.LEFT, padx=(0, 8))

    def _on_clear(self) -> None:
        """Clear the scan box and the displayed serial/parameters, ready
        for the next scan."""
        self.scanner_var.set("")
        self.serial_number_var.set("")
        if self._param_labels:
            for widget in self._param_labels.values():
                widget.configure(text="")

    def _open_history(self) -> None:
        open_scan_history(
            self.root,
            print_mode=self.print_var.get(),
            variant=self.variant_var.get(),
            origin="pack_id",
        )

    def _apply_permissions(self) -> None:
        
        if self._category_combo is not None:
            set_combobox_enabled(self._category_combo, self.is_admin)
        if self._variant_combo is not None:
            set_combobox_enabled(self._variant_combo, self.is_admin)

    def _param_value(self, key: str) -> str:
        widget = self._param_labels.get(key)
        if widget is None:
            return ""
        return str(widget.cget("text"))

    def _mfg_date_for_serial(self, serial_number: str) -> str:
        parsed = parse_serial_number(serial_number)
        if parsed is None:
            return ""
        return parsed.format_date()

    def _store_serial_if_present(self) -> None:
        serial_number = self.serial_number_var.get().strip()
        if serial_number:
            save_pack_serial(serial_number)

    def _print_label(self, serial_number: str) -> None:
        category = self.category_var.get()

        pack_qr_data = format_pack_qr_data(
            variant=self.variant_var.get(),
            serial_number=serial_number,
        )

        zpl = build_battery_pack_id_label(
            serial_number=serial_number,
            rated_capacity=self._param_value("rated_capacity"),
            max_voltage=self._param_value("max_voltage"),
            model_number=self._param_value("model_number"),
            tac_number=self._param_value("tac_number"),
            variant=self.variant_var.get(),
            category=category,
            mfg_date=self._mfg_date_for_serial(serial_number),
            pack_qr_data=pack_qr_data,
        )
        self._store_serial_if_present()
        dispatch_zpl(
            self.root,
            zpl,
            self.print_var.get(),
            default_name=f"pack_{serial_number}.zpl",
            printer_name=PRINTER_PACK_ID,
        )
    
        now = datetime.now()
        pw = self._session.excel_password if hasattr(self, "_session") and self._session else "06082003"
        record = PackIdScanRecord(
            date=self._mfg_date_for_serial(serial_number),
            time=now.strftime("%I:%M:%S %p").lstrip("0"),
            serial_number=serial_number,
            variant=self.variant_var.get(),
            pack_qr_data=pack_qr_data,
        )
        try:
            append_pack_id_scan_record(record, excel_password=pw)
        except Exception:
            pass

    def _reset_fields(self) -> None:
        self.scanner_var.set("")
        

    def _on_scan(self, raw: str) -> None:
        if not raw:
            return

        result = identify_scan(raw)
        self.scanner_var.set(result.raw)

        if result.scan_type == ScanType.SERIAL_NUMBER and result.serial is not None:
            if result.pack_variant is None:
                self.scanner_var.set("")
                messagebox.showwarning(
                    "Scan", "Serial Number scanned. Expecting a Pack QR or bmb_cmb code.", parent=self.root
                )
                return

            self.scanner_var.set("")  
            self.serial_number_var.set(result.serial.raw)
            
            if result.pack_variant:
                self.variant_var.set(result.pack_variant)
            # Always trigger a parameter refresh (covers bare serial scans too)
            self._on_variant_change()

            # Auto-print the label, then reset fields after a brief preview delay
            self._print_label(result.serial.raw)
            self.root.after(1000, self._reset_fields)
            return

        if result.scan_type == ScanType.MODULE_ID:
            messagebox.showwarning(
                "Scan",
                "Module ID scanned. expects the pack serial QR code.",
                parent=self.root,
            )
            return

        if result.scan_type == ScanType.BMS_ID:
            messagebox.showwarning(
                "Scan",
                "BMS ID scanned. expects the pack serial QR code.",
                parent=self.root,
            )
            return
        
        else:
            messagebox.showwarning(
                "Scan",
                "Unrecognized code. Scan the pack serial number QR code.",
                parent=self.root,
            )
            self.scanner_var.set("")
            

    def run(self) -> None:
        self.root.mainloop()


def open_battery_pack_id(parent: tk.Tk | tk.Toplevel | None = None) -> BatteryPackIdGUI:
    return BatteryPackIdGUI(parent)


def main() -> None:
    app = BatteryPackIdGUI()
    app.run()


if __name__ == "__main__":
    main()
