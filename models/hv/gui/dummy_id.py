from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from common.api_client import APIClientError
from models.hv.gui.battery_parameters import build_battery_parameters_panel, set_battery_parameters
from models.hv.gui.constants import VARIANT_OPTIONS, VARIANT_PARAMS, format_pack_qr_data, get_type_of_reess
from models.hv.gui.layout import FIELD_FONT, FIELD_IPADY, HEADING_FONT, LABEL_FONT
from models.hv.gui.print_actions import dispatch_zpl
from models.hv.gui.scan_history import open_scan_history
from models.hv.gui.scanner import setup_hardware_scanner
from models.hv.nomenclature.scan_handler import ScanType, identify_scan
from models.hv.printing.constants import PRINTER_DUMMY
from models.hv.printing.labels import build_pack_qr_label
from models.hv.session.pack_store import save_pack_serial
from models.hv.session.scan_log import ScanRecord, append_scan_record

MODULE_PLACEHOLDER_TEXT = "Module Level Completed"
INTEGRATION_STATUS_TEXT = "INTEGRATION OK"


class DummyIdGUI:

    def __init__(self, parent: tk.Misc | None = None, *, is_admin: bool = False, session=None) -> None:
        self.is_admin = is_admin
        self._session = session

        if parent is None:
            self.root = tk.Tk()
            self.host = self.root
            self.root.title("Dummy ID")
            self.root.geometry("900x520")
            self.root.minsize(760, 460)
        elif isinstance(parent, (tk.Tk, tk.Toplevel)):
            self.root = parent
            self.host = parent
            self.root.title("Dummy ID")
        else:
            self.root = parent.winfo_toplevel()
            self.host = parent

        self.serial_entry_var = tk.StringVar()
        self.print_var = tk.StringVar(value="print")
        self._parsed_serial = None

        self._build_ui()

    # ── UI
    def _build_ui(self) -> None:
        container = ttk.Frame(self.host, padding=(16, 12))
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Dummy ID", font=("Segoe UI", 18, "bold")).pack(
            anchor=tk.W, pady=(0, 14)
        )

        self._build_serial_row(container)

        self._param_labels, self.serial_number_var, _entry, self._captions = (
            build_battery_parameters_panel(container, dense=True, plain_labels=True)
        )

    def _build_serial_row(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, padding=10)
        section.pack(fill=tk.X, pady=(0, 12))

        row = ttk.Frame(section)
        row.pack(fill=tk.X)


        row.columnconfigure(0, weight=6)
        row.columnconfigure(1, weight=4)

        entry = ttk.Entry(row, textvariable=self.serial_entry_var, font=FIELD_FONT)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 14), ipady=FIELD_IPADY + 2)
        setup_hardware_scanner(entry, self.serial_entry_var, self._on_serial_submitted)

        controls = ttk.Frame(row)
        controls.grid(row=0, column=1, sticky="ew")
        ttk.Label(controls, text="Print Mode", font=LABEL_FONT).pack(anchor=tk.W)
        mode_row = ttk.Frame(controls)
        mode_row.pack(fill=tk.X, pady=(5, 0))
        ttk.Combobox(
            mode_row, textvariable=self.print_var, values=["print", "pdf"],
            state="readonly", width=10, justify="center",
        ).pack(side=tk.LEFT, ipady=FIELD_IPADY)
        ttk.Button(mode_row, text="History", command=self._open_history, width=10).pack(side=tk.LEFT, padx=(8, 0))

    # ── Serial entry → details popup
    def _on_serial_submitted(self, raw: str) -> None:
        result = identify_scan(raw)
        if result.scan_type != ScanType.SERIAL_NUMBER or result.serial is None:
            messagebox.showwarning(
                "Invalid Serial Number",
                parent=self.root,
            )
            self.serial_entry_var.set("")
            return

        self._parsed_serial = result.serial
        self.serial_entry_var.set(result.serial.raw)
        self._open_details_popup(preselect_variant=result.pack_variant)

    def _open_details_popup(self, *, preselect_variant: str | None) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Pack Details")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        frame = ttk.Frame(popup, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Enter Pack Details", font=HEADING_FONT).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )


        parsed = self._parsed_serial
        is_new_format = parsed is not None and parsed.is_new_format
        auto_variant = parsed.variant if is_new_format else None

        variant_var = tk.StringVar(
            value=auto_variant
            or (preselect_variant if preselect_variant in VARIANT_OPTIONS else VARIANT_OPTIONS[0])
        )
        ref_no_var = tk.StringVar()

        next_row = 1
        if not is_new_format:
            ttk.Label(frame, text="Variant").grid(row=next_row, column=0, sticky=tk.W, pady=3, padx=(0, 10))
            ttk.Combobox(
                frame, textvariable=variant_var, values=VARIANT_OPTIONS,
                state="readonly", width=22, justify="center",
            ).grid(row=next_row, column=1, sticky="ew", pady=3)
            next_row += 1

        ttk.Label(frame, text="Ref No").grid(row=next_row, column=0, sticky=tk.W, pady=3, padx=(0, 10))
        ttk.Entry(frame, textvariable=ref_no_var, width=24).grid(row=next_row, column=1, sticky="ew", pady=3)
        next_row += 1

        def _on_ok() -> None:
            popup.destroy()
            self._print_dummy_label(
                variant=variant_var.get(),
                ref_no=ref_no_var.get().strip(),
            )

        def _on_cancel() -> None:
            popup.destroy()
            self.serial_entry_var.set("") #clear the scan box
            self._parsed_serial = None

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=next_row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btn_row, text="Cancel", command=_on_cancel, width=8).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="OK", command=_on_ok, width=8).pack(side=tk.LEFT)

        frame.columnconfigure(1, weight=1)
        popup.bind("<Return>", lambda _e: _on_ok())
        popup.protocol("WM_DELETE_WINDOW", _on_cancel)

        popup.update_idletasks()
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - popup.winfo_width()) // 2
        ry = self.root.winfo_rooty() + (self.root.winfo_height() - popup.winfo_height()) // 2
        popup.geometry(f"+{max(0, rx)}+{max(0, ry)}")

    # ── Print + log (mirrors Battery Pack Dummy ID's backend)
    def _print_dummy_label(self, *, variant: str, ref_no: str) -> None:
        parsed = self._parsed_serial
        if parsed is None:
            return
        serial = parsed.raw

        category = "Export" if parsed.is_new_format and parsed.is_export else "Domestic"

        params = VARIANT_PARAMS.get(variant, VARIANT_PARAMS[VARIANT_OPTIONS[-1]])
        model_number = get_type_of_reess(variant)
        mfg_date = parsed.format_date()
        
        # pack_id = ttk.Combobox(self.root).grid(row=0, column=2, sticky="news")

        pack_qr = format_pack_qr_data(variant=variant, serial_number=serial)

        set_battery_parameters(
            self._param_labels,
            rated_capacity=params["rated_capacity"],
            max_voltage=params["max_voltage"],
            model_number=model_number,
            tac_number=params["tac_number"],
            emark=params["emark"],
            category=category,
            captions=self._captions,
        )
        self.serial_number_var.set(serial)

        zpl = build_pack_qr_label(
            pack_qr_data=pack_qr,
            model_number=model_number,
            serial_number=serial,
            tac_number=params["tac_number"],
            mfg_date=mfg_date,
            variant=variant,
            category=category,
        )

        now = datetime.now()
        record = ScanRecord(
            date=mfg_date,
            time=now.strftime("%I:%M:%S %p").lstrip("0"),
            serial_count=parsed.serial_count,
            ref_no=ref_no,
            variant=variant,
            m1=MODULE_PLACEHOLDER_TEXT,
            m2=MODULE_PLACEHOLDER_TEXT,
            m3=MODULE_PLACEHOLDER_TEXT,
            m4=MODULE_PLACEHOLDER_TEXT,
            dummy_pack_status=INTEGRATION_STATUS_TEXT,
            dummy_pack_qr=pack_qr,
            serial_number=serial,
        )
        try:
            append_scan_record(record)
            save_pack_serial(serial)
        except APIClientError as exc:
            messagebox.showerror(
                "Server unavailable",
                f"Could not save the scan. Printing is blocked until the server is reachable.\n\n{exc}",
                parent=self.root,
            )
            return

        dispatch_zpl(
            self.root, zpl, self.print_var.get(),
            default_name=f"dummy_{serial}.zpl", printer_name=PRINTER_DUMMY,
        )

        self.serial_entry_var.set("")
        self._parsed_serial = None

    def _open_history(self) -> None:
        open_scan_history(self.root, print_mode=self.print_var.get(), origin="dummy")


def open_dummy_id(parent: tk.Tk | tk.Toplevel | None = None) -> DummyIdGUI:
    return DummyIdGUI(parent)


if __name__ == "__main__":
    DummyIdGUI().mainloop()