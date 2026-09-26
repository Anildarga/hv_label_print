from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from models.hv.gui.layout import DISPLAY_FONT, FIELD_FONT, FIELD_IPADY, LABEL_FONT, HEADING_FONT
from models.hv.gui.print_actions import dispatch_zpl
from models.hv.gui.scan_history import open_scan_history
from models.hv.gui.scanner import setup_hardware_scanner
from models.hv.nomenclature.bms_id import short_bmb_cmb_id
from models.hv.nomenclature.scan_handler import ScanType, identify_scan
from models.hv.printing.constants import PRINTER_BMS_ID
from models.hv.printing.labels import build_bmb_cmb_combined_label
from models.hv.session.bms_scan_log import BmsScanRecord, append_scan_record, find_record_by_pack_qr, patch_rework

_RESET_DELAY_MS = 1000


class BmsIdGUI:

    def __init__(
        self, parent: tk.Misc | None = None, *, is_admin: bool = False, session=None
    ) -> None:
        self.is_admin = is_admin
        self._session = session

        if parent is None:
            self.root = tk.Tk()
            self.host = self.root
            self.root.title("BMB / CMB ID")
            self.root.geometry("900x480")
            self.root.minsize(700, 400)
        elif isinstance(parent, (tk.Tk, tk.Toplevel)):
            self.root = parent
            self.host = parent
        else:
            self.root = parent.winfo_toplevel()
            self.host = parent

        self.pack_qr_var = tk.StringVar()
        self.bmb_id_var = tk.StringVar()
        self.cmb_id_var = tk.StringVar()
        self.rework_bmb_var = tk.StringVar()
        self.rework_cmb_var = tk.StringVar()
        self.rework_mode_var = tk.StringVar(value="No")   # explicit rework toggle — default off
        self.scanner_var = tk.StringVar()
        self.print_var = tk.StringVar(value="print")

        self._pack_qr_raw = ""     # in-memory only — never persisted/restored
        self._pack_date = ""       # get date from scanned pack qr data
        self._bmb_parsed = None    # ParsedBmbCmbId, once scanned (new-entry mode)
        self._cmb_parsed = None
        self._existing_record = None  # BmsScanRecord, when rework mode finds a match

        self._build_ui()
        self._apply_rework_visibility()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.host, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="BMB / CMB ID", font=("Segoe UI", 18, "bold")).pack(anchor=tk.W, pady=(0, 14))

        # Display: Pack QR / BMB ID / CMB ID, filled in as each is scanned
        self._display_frame = ttk.Frame(container, padding=(0, 0, 0, 12))
        self._display_frame.pack(fill=tk.X)
        ttk.Label(self._display_frame, text="Pack QR:", font=LABEL_FONT).grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=2)
        ttk.Label(self._display_frame, textvariable=self.pack_qr_var, font=("Segoe UI", 10), foreground="#0a5c9e").grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(self._display_frame, text="BMB ID:", font=LABEL_FONT).grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=2)
        ttk.Label(self._display_frame, textvariable=self.bmb_id_var, font=DISPLAY_FONT).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(self._display_frame, text="CMB ID:", font=LABEL_FONT).grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=2)
        ttk.Label(self._display_frame, textvariable=self.cmb_id_var, font=DISPLAY_FONT).grid(row=2, column=1, sticky=tk.W, pady=2)

        # Rework ID rows — only gridded (visible) when Rework = Yes.
        self._rework_bmb_label = ttk.Label(self._display_frame, text="Rework BMB ID:", font=LABEL_FONT)
        self._rework_bmb_value = ttk.Label(self._display_frame, textvariable=self.rework_bmb_var, font=DISPLAY_FONT, foreground="#b34700")
        self._rework_cmb_label = ttk.Label(self._display_frame, text="Rework CMB ID:", font=LABEL_FONT)
        self._rework_cmb_value = ttk.Label(self._display_frame, textvariable=self.rework_cmb_var, font=DISPLAY_FONT, foreground="#b34700")

        scan_frame = ttk.Frame(container)
        scan_frame.pack(fill=tk.X)

        scan_section = ttk.Frame(scan_frame, padding=10)
        scan_section.pack(fill=tk.X, pady=(0, 12),)

        row = ttk.Frame(scan_section)
        row.pack(fill=tk.X)
        row.columnconfigure(0, weight=1)

        scanner_entry = ttk.Entry(row, textvariable=self.scanner_var, font=FIELD_FONT)
        scanner_entry.grid(row=0, column=0, sticky="ew", ipady=FIELD_IPADY + 1)
        setup_hardware_scanner(scanner_entry, self.scanner_var, self._on_scan)

        controls = ttk.Frame(row)
        controls.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))

        ttk.Label(controls, text="Rework", font=LABEL_FONT).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Combobox(
            controls, textvariable=self.rework_mode_var, values=["Yes", "No" ],
            state="readonly", width=8, justify="center",
        ).pack(side=tk.LEFT, ipady=FIELD_IPADY, padx=(0, 8))
        self.rework_mode_var.trace_add("write", lambda *_a: self._on_rework_toggle())

        ttk.Combobox(
            controls, textvariable=self.print_var, values=["print", "pdf"],
            state="readonly", width=8, justify="center",
        ).pack(side=tk.LEFT, ipady=FIELD_IPADY, padx=(0, 8))
        ttk.Button(controls, text="History", command=self._open_history, width=10).pack(side=tk.LEFT, ipady=FIELD_IPADY, padx=(0, 8))

    def _open_history(self) -> None:
        open_scan_history(self.root, print_mode=self.print_var.get(), origin="bmb_cmb")

    # ── Rework toggle 
    def _on_rework_toggle(self) -> None:
        self._apply_rework_visibility()
        self._reset_display()

    def _apply_rework_visibility(self) -> None:
        if self.rework_mode_var.get() == "Yes":
            self._rework_bmb_label.grid(row=3, column=0, sticky=tk.W, padx=(0, 10), pady=2)
            self._rework_bmb_value.grid(row=3, column=1, sticky=tk.W, pady=2)
            self._rework_cmb_label.grid(row=4, column=0, sticky=tk.W, padx=(0, 10), pady=2)
            self._rework_cmb_value.grid(row=4, column=1, sticky=tk.W, pady=2)
        else:
            self._rework_bmb_label.grid_remove()
            self._rework_bmb_value.grid_remove()
            self._rework_cmb_label.grid_remove()
            self._rework_cmb_value.grid_remove()

    def _is_rework(self) -> bool:
        return self.rework_mode_var.get() == "Yes"

    # ── Scanning 
    def _on_scan(self, raw: str) -> None:
        if not raw:
            return
        self.scanner_var.set("")

        result = identify_scan(raw)

        if result.scan_type == ScanType.SERIAL_NUMBER and result.serial is not None:
            if result.pack_variant is None:
                messagebox.showwarning(
                    "Scan", "Serial Number scanned. But Expecting a Pack QR or bmb_cmb code.", parent=self.root
                )
                return

            self._pack_qr_raw = result.raw
            self._pack_date = result.serial.format_date()
            self.pack_qr_var.set(result.raw)

            if self._is_rework():
                existing = find_record_by_pack_qr(result.raw)
                if existing is None:
                    messagebox.showwarning(
                        "Rework", "Scan dummy pack id first to continue with rework.", parent=self.root
                    )
                    self._pack_qr_raw = ""
                    self.pack_qr_var.set("")
                    self._existing_record = None
                    return
                self._existing_record = existing
                self.bmb_id_var.set(existing.bmb_id)
                self.cmb_id_var.set(existing.cmb_id)
                self.rework_bmb_var.set(existing.rework_bmb_id)
                self.rework_cmb_var.set(existing.rework_cmb_id)
            else:
                self.bmb_id_var.set("")
                self.cmb_id_var.set("")
                self._bmb_parsed = None
                self._cmb_parsed = None
            return

        if result.scan_type in (ScanType.BMB_ID, ScanType.CMB_ID) and result.bmb_cmb is not None:
            kind = result.bmb_cmb.kind  # "BMB" or "CMB"

            if self._is_rework():
                self._save_rework(kind, result.bmb_cmb.raw)
                return

            if kind == "BMB":
                self.bmb_id_var.set(result.bmb_cmb.raw)
                self._bmb_parsed = result.bmb_cmb
            else:
                self.cmb_id_var.set(result.bmb_cmb.raw)
                self._cmb_parsed = result.bmb_cmb
            self._check_and_print()
            return

        if result.scan_type == ScanType.MODULE_ID:
            messagebox.showwarning(
                "Scan", "Module ID scanned. But Expecting a Pack QR or bmb_cmb code.", parent=self.root
            )
            return

        messagebox.showwarning(
            "Scan", "Unrecognized code. But Expecting a Pack QR, BMB, or CMB code.", parent=self.root,
        )

    # ── Rework: patch log + immediate reprint with corrected ID 
    def _save_rework(self, kind: str, full_raw_id: str) -> None:
        if not self._pack_qr_raw or self._existing_record is None:
            return
        pw = self._session.excel_password if self._session else "06082003"
        ok = patch_rework(self._pack_qr_raw, kind, full_raw_id, excel_password=pw)
        if not ok:
            messagebox.showwarning("Rework", "Dummy Pack id not found in scan history.", parent=self.root)
            return

        if kind == "BMB":
            self.rework_bmb_var.set(full_raw_id)
        else:
            self.rework_cmb_var.set(full_raw_id)

        effective_bmb_raw = self.rework_bmb_var.get().strip() or self._existing_record.bmb_id.strip()
        effective_cmb_raw = self.rework_cmb_var.get().strip() or self._existing_record.cmb_id.strip()
        if not (effective_bmb_raw and effective_cmb_raw):
            return  # shouldn't happen — original row always has both

        zpl = build_bmb_cmb_combined_label(
            bmb_serial=short_bmb_cmb_id(effective_bmb_raw),
            cmb_serial=short_bmb_cmb_id(effective_cmb_raw),
            pack_qr_data=self._pack_qr_raw,
        )
        dispatch_zpl(
            self.root, zpl, self.print_var.get(),
            default_name=f"rework_bmb_cmb_{short_bmb_cmb_id(effective_bmb_raw)}.zpl",
            printer_name=PRINTER_BMS_ID,
        )
        self.root.after(_RESET_DELAY_MS, self._reset_display)

    # ── New-entry: collect all three, then auto-print + log 
    def _check_and_print(self) -> None:
        if not (self._pack_qr_raw and self._bmb_parsed is not None and self._cmb_parsed is not None):
            return

        pack_qr = self._pack_qr_raw
        zpl = build_bmb_cmb_combined_label(
            bmb_serial=self._bmb_parsed.short_id,
            cmb_serial=self._cmb_parsed.short_id,
            pack_qr_data=pack_qr,
        )
        dispatch_zpl(
            self.root, zpl, self.print_var.get(),
            default_name=f"bmb_cmb_{self._bmb_parsed.short_id}.zpl",
            printer_name=PRINTER_BMS_ID,
        )

        now = datetime.now()
        record = BmsScanRecord(
            date=self._pack_date,
            time=now.strftime("%I:%M:%S %p").lstrip("0"),
            pack_qr_data=pack_qr,
            bmb_id=self._bmb_parsed.raw,   # FULL ID in the scan log
            cmb_id=self._cmb_parsed.raw,
        )
        try:
            excel_pw = self._session.excel_password if self._session else "06082003"
            append_scan_record(record, excel_password=excel_pw)
        except Exception:
            pass

        self.root.after(_RESET_DELAY_MS, self._reset_display)

    def _reset_display(self) -> None:
        self.pack_qr_var.set("")
        self.bmb_id_var.set("")
        self.cmb_id_var.set("")
        self.rework_bmb_var.set("")
        self.rework_cmb_var.set("")
        self._pack_qr_raw = ""
        self._pack_date = ""
        self._bmb_parsed = None
        self._cmb_parsed = None
        self._existing_record = None

    def run(self) -> None:
        self.root.mainloop()


def open_bms_id(parent: tk.Tk | tk.Toplevel | None = None) -> BmsIdGUI:
    return BmsIdGUI(parent)


def main() -> None:
    BmsIdGUI().run()


if __name__ == "__main__":
    main()
