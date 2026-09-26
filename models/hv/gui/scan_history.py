from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk

from models.hv.gui.constants import VARIANT_OPTIONS
from models.hv.gui.print_actions import dispatch_zpl
from models.hv.printing.constants import PRINTER_DUMMY
from models.hv.printing.labels import build_battery_pack_id_label, build_bmb_cmb_combined_label, build_pack_qr_label

# Three separate logs, one per screen — see session/scan_log.py,
# session/pack_id_scan_log.py, session/bms_scan_log.py.
from models.hv.session.scan_log import load_all_records as load_dummy_records, open_log_file as open_dummy_log_file
from models.hv.session.pack_id_scan_log import load_all_records as load_pack_id_records, open_log_file as open_pack_id_log_file
from models.hv.session.bms_scan_log import load_all_records as load_bms_records, open_log_file as open_bms_log_file

_ORIGIN_LABELS = {"dummy": "Battery Pack Dummy ID", "pack_id": "Battery Pack ID", "bmb_cmb": "BMB / CMB ID"}


_COL_DEFS = {
    "dummy": [
        ("sl_no",         "Sl.No",                50,  "center"),
        ("date",          "Date",                  95,  "center"),
        ("time",          "Time",                 100,  "center"),
        ("serial_count",  "Serial Count",         100,  "center"),
        ("serial_number", "Pack ID (Serial No)",  160,  "w"),
        ("ref_no",        "Ref No",                90,  "center"),
        ("variant",       "Variant",               90,  "center"),
        ("m1",            "M1",                   160,  "w"),
        ("m2",            "M2",                   160,  "w"),
        ("m3",            "M3",                   160,  "w"),
        ("m4",            "M4",                   160,  "w"),
        ("dummy_status",  "Dummy Pack ID Status", 160,  "center"),
        ("dummy_qr",      "Dummy Pack QR",        200,  "w"),
        ("issue_1",       "Issue Desc 1",         180,  "w"),
        ("issue_2",       "Issue Desc 2",         180,  "w"),
        ("action_plan",   "Action Plan",          180,  "w"),
        ("remark",        "Remark",               120,  "w"),
    ],
    "pack_id": [
        ("sl_no",         "Sl.No",           50,  "center"),
        ("date",          "Date",            95,  "center"),
        ("time",          "Time",           100,  "center"),
        ("serial_number", "Serial Number",  180,  "w"),
        ("variant",       "Variant",        110,  "center"),
        ("pack_qr_data",  "Pack QR Data",   260,  "w"),
    ],
    "bmb_cmb": [
        ("sl_no",           "Sl.No",           50,  "center"),
        ("date",            "Date",            95,  "center"),
        ("time",            "Time",           100,  "center"),
        ("pack_qr_data",    "Pack QR Data",   240,  "w"),
        ("bmb_id",          "BMB ID",         150,  "center"),
        ("cmb_id",          "CMB ID",         150,  "center"),
        ("rework_bmb_id",   "Rework BMB ID",  150,  "center"),
        ("rework_cmb_id",   "Rework CMB ID",  150,  "center"),
    ],
}


class ScanHistoryDialog(tk.Toplevel):

    def __init__(
        self,
        parent: tk.Misc,
        *,
        print_mode: str = "print",
        variant: str = VARIANT_OPTIONS[-1],
        revision: str = "V0",
        session=None,
        origin: str = "dummy",
    ) -> None:
        super().__init__(parent)
        origin_label = _ORIGIN_LABELS.get(origin, origin)
        self.title(f"Scan History - Reprint: {origin_label}")
        self.geometry("1300x560")
        self.minsize(900, 400)

        self._print_mode = print_mode
        self._variant = variant
        self._revision = revision
        self._session = session
        self._origin = origin  
        self._col_defs = _COL_DEFS[origin]
        self._records: list = []
        self._last_mtime: float = 0.0
        self._auto_refresh_id: str | None = None

        self._build_ui()
        self._load_records()
        self._center_over_parent(parent)
        self._start_auto_refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=(10, 8, 10, 4))
        top.pack(fill=tk.X)

        ttk.Label(top, text="Scan History", font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Open Excel", command=self._open_excel, width=12).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Refresh", command=self._load_records, width=10).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Reprint Selected", command=self._on_reprint, width=16).pack(side=tk.LEFT)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 0))

        col_ids = [c[0] for c in self._col_defs]
        self.tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="browse")

        for col_id, heading, width, anchor in self._col_defs:
            self.tree.heading(col_id, text=heading, anchor="center")
            self.tree.column(col_id, width=width, anchor=anchor, stretch=False)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("odd",  background="#ffffff")
        self.tree.tag_configure("even", background="#eef2f7")
        self.tree.bind("<Double-1>", lambda _e: self._on_reprint())

        self._status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self._status_var, font=("Segoe UI", 9), padding=(10, 4)).pack(anchor=tk.W)

    def _log_file_for_origin(self):
        if self._origin == "pack_id":
            from models.hv.session.pack_id_scan_log import LOG_FILE
        elif self._origin == "bmb_cmb":
            from models.hv.session.bms_scan_log import LOG_FILE
        else:
            from models.hv.session.scan_log import LOG_FILE
        return LOG_FILE

    def _load_records(self) -> None:
        if self._origin == "pack_id":
            self._records = load_pack_id_records()
        elif self._origin == "bmb_cmb":
            self._records = load_bms_records()
        else:
            self._records = load_dummy_records()

        try:
            log_file = self._log_file_for_origin()
            if log_file.exists():
                self._last_mtime = os.path.getmtime(str(log_file))
        except Exception:
            pass

        for item in self.tree.get_children():
            self.tree.delete(item)

        col_ids = [c[0] for c in self._col_defs]
        for idx, rec in enumerate(self._records):
            tag = "even" if idx % 2 == 0 else "odd"
            values = [idx + 1 if col_id == "sl_no" else getattr(rec, self._attr_for(col_id), "") for col_id in col_ids]
            self.tree.insert("", tk.END, iid=str(idx), values=values, tags=(tag,))
        self._status_var.set(f"{len(self._records)} record(s) loaded.")

    def _attr_for(self, col_id: str) -> str:
        return {
            "dummy_status": "dummy_pack_status",
            "dummy_qr":     "dummy_pack_qr",
        }.get(col_id, col_id)

    def _start_auto_refresh(self) -> None:
        self._check_file_modified()

    def _check_file_modified(self) -> None:
        try:
            log_file = self._log_file_for_origin()
            if log_file.exists():
                current_mtime = os.path.getmtime(str(log_file))
                if current_mtime > self._last_mtime and self._last_mtime > 0:
                    self._load_records()
        except Exception:
            pass
        self._auto_refresh_id = self.after(3000, self._check_file_modified)

    def _on_close(self) -> None:
        if self._auto_refresh_id:
            self.after_cancel(self._auto_refresh_id)
        self.destroy()

    def _on_reprint(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Reprint", "Select a row to reprint.", parent=self)
            return
        idx = int(selection[0])
        rec = self._records[idx]

        if self._origin == "pack_id":
            self._reprint_pack_id(idx, rec)
        elif self._origin == "bmb_cmb":
            self._reprint_bmb_cmb(idx, rec)
        else:
            self._reprint_dummy(idx, rec)

    def _reprint_dummy(self, idx: int, rec) -> None:
      
        if not rec.dummy_pack_qr:
            messagebox.showwarning("Reprint", "No pack QR data for this record.", parent=self)
            return

        from models.hv.gui.constants import VARIANT_PARAMS, get_type_of_reess
        variant = rec.variant.strip() if rec.variant.strip() in VARIANT_OPTIONS else self._variant
        params = VARIANT_PARAMS.get(variant, VARIANT_PARAMS[VARIANT_OPTIONS[-1]])
        model_number = get_type_of_reess(variant)

        
        category = "Domestic"

        zpl = build_pack_qr_label(
            pack_qr_data=rec.dummy_pack_qr,
            model_number=model_number,
            serial_number=rec.serial_number,
            tac_number=params["tac_number"],
            mfg_date=rec.date,
            variant=variant,
            category=category,
        )
        dispatch_zpl(self, zpl, self._print_mode, default_name=f"reprint_dummy_{idx+1}.zpl", printer_name=PRINTER_DUMMY)
        self._status_var.set(f"Reprinted (Dummy Pack QR) row {idx + 1}")

    def _reprint_pack_id(self, idx: int, rec) -> None:
        
        if not rec.pack_qr_data:
            messagebox.showwarning("Reprint", "No pack QR data for this record.", parent=self)
            return

        from models.hv.nomenclature.scan_handler import ScanType, identify_scan
        result = identify_scan(rec.pack_qr_data)
        if result.scan_type != ScanType.SERIAL_NUMBER or result.serial is None:
            messagebox.showwarning("Reprint", "Pack QR data for this record isn't valid.", parent=self)
            return

        from models.hv.gui.constants import VARIANT_PARAMS, get_type_of_reess
        variant = rec.variant.strip() if rec.variant.strip() in VARIANT_OPTIONS else (result.pack_variant or self._variant)
        serial_number = rec.serial_number or result.serial.raw
        
        category = "Domestic"
        params = VARIANT_PARAMS.get(variant, VARIANT_PARAMS[VARIANT_OPTIONS[-1]])
        model_number = get_type_of_reess(variant)

        zpl = build_battery_pack_id_label(
            serial_number=serial_number,
            rated_capacity=params["rated_capacity"],
            max_voltage=params["max_voltage"],
            model_number=model_number,
            tac_number=params["tac_number"],
            variant=variant,
            category=category,
            mfg_date=rec.date,
            pack_qr_data=rec.pack_qr_data,
        )
        dispatch_zpl(self, zpl, self._print_mode, default_name=f"reprint_pack_id_{idx+1}.zpl", printer_name=PRINTER_DUMMY)
        self._status_var.set(f"Reprinted (Battery Pack ID) row {idx + 1}")

    def _reprint_bmb_cmb(self, idx: int, rec) -> None:
        
        effective_bmb = rec.rework_bmb_id.strip() or rec.bmb_id.strip()
        effective_cmb = rec.rework_cmb_id.strip() or rec.cmb_id.strip()
        if not (effective_bmb and effective_cmb):
            messagebox.showwarning("Reprint", "This record doesn't have both a BMB ID and a CMB ID yet.", parent=self)
            return

        from models.hv.nomenclature.bms_id import short_bmb_cmb_id
        zpl = build_bmb_cmb_combined_label(
            bmb_serial=short_bmb_cmb_id(effective_bmb),
            cmb_serial=short_bmb_cmb_id(effective_cmb),
            pack_qr_data=rec.pack_qr_data,
        )
        dispatch_zpl(self, zpl, self._print_mode, default_name=f"reprint_bmb_cmb_{idx+1}.zpl", printer_name=PRINTER_DUMMY)
        note = " (using rework ID)" if (rec.rework_bmb_id.strip() or rec.rework_cmb_id.strip()) else ""
        self._status_var.set(f"Reprinted (bmb_cmb) row {idx + 1}{note}")

    def _open_excel(self) -> None:
        try:
            if self._origin == "pack_id":
                open_pack_id_log_file()
            elif self._origin == "bmb_cmb":
                open_bms_log_file()
            else:
                open_dummy_log_file()
        except Exception as exc:
            messagebox.showerror("Open Excel", f"Could not open log file:\n{exc}", parent=self)

    def _center_over_parent(self, parent: tk.Misc) -> None:
        p = parent.winfo_toplevel()
        self.update_idletasks()
        x = p.winfo_rootx() + (p.winfo_width() - self.winfo_width()) // 2
        y = p.winfo_rooty() + (p.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")


def open_scan_history(
    parent: tk.Misc,
    *,
    print_mode: str = "print",
    variant: str = VARIANT_OPTIONS[-1],
    revision: str = "V0",
    session=None,
    origin: str = "dummy",
) -> None:
    try:
        dialog = ScanHistoryDialog(
            parent, print_mode=print_mode, variant=variant, revision=revision,
            session=session, origin=origin,
        )
        
        dialog.lift()
        dialog.attributes("-topmost", True)
        dialog.after(150, lambda: dialog.attributes("-topmost", False))
        dialog.focus_force()
    except Exception as exc:
        
        import traceback
        traceback.print_exc()
        messagebox.showerror(
            "Scan History",
            f"Could not open Scan History:\n{exc}",
            parent=parent if isinstance(parent, (tk.Tk, tk.Toplevel)) else parent.winfo_toplevel(),
        )