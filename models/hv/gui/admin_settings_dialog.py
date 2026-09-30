from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from common.api_client import APIClientError
from models.hv.gui.auth_dialog import ManageUsersDialog
from models.hv.session.scan_log import (
    ScanRecord,
    load_all_records_with_rows,
    load_unacknowledged_issues,
    patch_admin_ack,
)
from models.hv.session.bms_scan_log import load_rework_records as load_bms_rework_records
from models.hv.session.pack_id_scan_log import load_all_records as load_pack_id_records

_DEFECT_COLS = [
    ("date",           "Date",              90),
    ("dummy_pack_qr",  "Pack QR",          220),
    ("serial_number",  "Serial Number",    150),
    ("issue_desc_1",   "Issue 1",          160),
    ("issue_desc_2",   "Issue 2",          160),
    ("action_plan",    "Action Plan",      160),
    ("remark",         "Remark",           120),
    ("admin_ack",      "Admin Acknowledgement", 200),
]


class AdminSettingsDialog(tk.Toplevel):

    def __init__(self, parent: tk.Misc, *, current_user: str) -> None:
        super().__init__(parent)
        self.title("Admin Settings")
        self.geometry("1200x600")
        self.minsize(900, 460)
        self.transient(parent.winfo_toplevel())

        self._current_user = current_user

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        manage_tab = ttk.Frame(notebook)
        self._defect_tab = ttk.Frame(notebook)
        self._messages_tab = ttk.Frame(notebook)
        self._bms_log_tab = ttk.Frame(notebook)
        self._pack_id_log_tab = ttk.Frame(notebook)

        notebook.add(manage_tab, text="Manage Users")
        notebook.add(self._defect_tab, text="Defect Log")
        notebook.add(self._messages_tab, text="Messages")
        notebook.add(self._bms_log_tab, text="BMS Scan Log")
        notebook.add(self._pack_id_log_tab, text="Pack ID Scan Log")

        self._build_manage_tab(manage_tab)
        self._defect_tree, self._defect_rows = self._build_defect_section(
            self._defect_tab, only_unacknowledged=False,
            empty_text="No defect entries yet.",
        )
        self._msg_tree, self._msg_rows = self._build_defect_section(
            self._messages_tab, only_unacknowledged=True,
            empty_text="No unacknowledged issues.",
        )
        self._build_bms_log_tab(self._bms_log_tab)
        self._build_pack_id_log_tab(self._pack_id_log_tab)

        notebook.bind("<<NotebookTabChanged>>", lambda _e: self._refresh_all())

    # ── Manage Users tab 
    def _build_manage_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent, text="Add or remove Admin and Operator accounts.",
            font=("Segoe UI", 10), padding=(4, 12),
        ).pack(anchor=tk.W)
        ttk.Button(
            parent, text="Open Manage Users…",
            command=lambda: self._open_manage_users(),
        ).pack(anchor=tk.W, padx=4)

    def _open_manage_users(self) -> None:
        ManageUsersDialog(self, self._current_user)

    # ── BMS Scan Log (rework entries only)
    def _build_bms_log_tab(self, parent: ttk.Frame) -> None:
        cols = [
            ("date",           "Date",            90),
            ("time",           "Time",            90),
            ("pack_qr_data",   "Pack QR Data",   220),
            ("bmb_id",         "BMB ID",         140),
            ("cmb_id",         "CMB ID",         140),
            ("rework_bmb_id",  "Rework BMB ID",  140),
            ("rework_cmb_id",  "Rework CMB ID",  140),
        ]
        tree = self._build_readonly_log_section(
            parent, cols,
            load_fn=lambda: [rec for _row, rec in load_bms_rework_records()],
            empty_text="No reworked bmb and cmb entries yet.",
        )
        self._bms_log_tree = tree

    # ── Battery Pack ID Scan Log (full log) 
    def _build_pack_id_log_tab(self, parent: ttk.Frame) -> None:
        cols = [
            ("date",          "Date",           90),
            ("time",          "Time",           90),
            ("serial_number", "Serial Number", 180),
            ("variant",       "Variant",       120),
            ("pack_qr_data",  "Pack QR Data",  260),
        ]
        tree = self._build_readonly_log_section(
            parent, cols,
            load_fn=load_pack_id_records,
            empty_text="No Battery Pack ID scans logged yet.",
        )
        self._pack_id_log_tree = tree

    def _build_readonly_log_section(
        self, parent: ttk.Frame, cols: list[tuple[str, str, int]], *, load_fn, empty_text: str,
    ) -> ttk.Treeview:
        top = ttk.Frame(parent, padding=(4, 8))
        top.pack(fill=tk.X)
        status_var = tk.StringVar(value=empty_text)
        ttk.Label(top, textvariable=status_var, foreground="#555").pack(side=tk.LEFT)
        btns = ttk.Frame(top)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text="Refresh", command=lambda: self._refresh_all()).pack(side=tk.LEFT)

        table_frame = ttk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=4)

        columns = [key for key, _label, _w in cols]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for key, label, width in cols:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor=tk.W)
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.__dict__.setdefault("_readonly_sections", []).append((tree, cols, load_fn, status_var, empty_text))
        self._populate_readonly(tree, cols, load_fn, status_var, empty_text)
        return tree

    def _populate_readonly(self, tree, cols, load_fn, status_var, empty_text) -> None:
        tree.delete(*tree.get_children())
        try:
            records = load_fn()
        except APIClientError as exc:
            messagebox.showerror(
                "Server error", f"Could not load scan log:\n{exc}", parent=self
            )
            records = []
        for i, rec in enumerate(records):
            values = [getattr(rec, key) for key, _l, _w in cols]
            record_id = str(getattr(rec, "id", "") or "")
            if not record_id:
                messagebox.showerror(
                    "Server error",
                    "Server returned a scan record without its database id.",
                    parent=self,
                )
                return
            tree.insert("", tk.END, iid=record_id, values=values)
        status_var.set(f"{len(records)} entr{'y' if len(records) == 1 else 'ies'}" if records else empty_text)

    # ── Defect Log / Messages 
    def _build_defect_section(
        self, parent: ttk.Frame, *, only_unacknowledged: bool, empty_text: str
    ) -> tuple[ttk.Treeview, dict[str, tuple[str, ScanRecord]]]:
        top = ttk.Frame(parent, padding=(4, 8))
        top.pack(fill=tk.X)
        status_var = tk.StringVar(value=empty_text)
        ttk.Label(top, textvariable=status_var, foreground="#555").pack(side=tk.LEFT)
        ttk.Button(top, text="Refresh", command=lambda: self._refresh_all()).pack(side=tk.RIGHT)

        table_frame = ttk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=4)

        columns = [key for key, _label, _w in _DEFECT_COLS]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for key, label, width in _DEFECT_COLS:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor=tk.W)
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        ack_frame = ttk.Frame(parent, padding=(4, 8))
        ack_frame.pack(fill=tk.X)
        ttk.Label(ack_frame, text="Admin Acknowledgement:").pack(side=tk.LEFT, padx=(0, 8))
        ack_var = tk.StringVar()
        ack_entry = ttk.Entry(ack_frame, textvariable=ack_var, width=60)
        ack_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        save_btn = ttk.Button(
            ack_frame, text="Save",
            command=lambda: self._save_ack(tree, rows_by_iid, ack_var, status_var, only_unacknowledged),
        )
        save_btn.pack(side=tk.LEFT)

        rows_by_iid: dict[str, tuple[str, ScanRecord]] = {}

        def _on_select(_event=None) -> None:
            sel = tree.selection()
            if not sel:
                ack_var.set("")
                return
            _record_id, rec = rows_by_iid.get(sel[0], (None, None))
            ack_var.set(rec.admin_ack if rec else "")

        tree.bind("<<TreeviewSelect>>", _on_select)

        # Stash refs needed by _refresh_all()
        self.__dict__.setdefault("_sections", []).append(
            (tree, rows_by_iid, status_var, only_unacknowledged, empty_text)
        )
        self._populate(tree, rows_by_iid, status_var, only_unacknowledged, empty_text)
        return tree, rows_by_iid

    def _populate(
        self,
        tree: ttk.Treeview,
        rows_by_iid: dict[str, tuple[str, ScanRecord]],
        status_var: tk.StringVar,
        only_unacknowledged: bool,
        empty_text: str,
    ) -> None:
        tree.delete(*tree.get_children())
        rows_by_iid.clear()

        try:
            data = load_unacknowledged_issues() if only_unacknowledged else [
                (record_id, rec)
                for record_id, rec in load_all_records_with_rows()
                if rec.has_issue
            ]
        except APIClientError as exc:
            status_var.set("Could not load defects from the server.")
            messagebox.showerror(
                "Server error", f"Could not load defect log:\n{exc}", parent=self
            )
            return

        for record_id, rec in data:
            iid = str(record_id)
            values = [getattr(rec, key) for key, _l, _w in _DEFECT_COLS]
            tree.insert("", tk.END, iid=iid, values=values)
            rows_by_iid[iid] = (record_id, rec)

        if data:
            status_var.set(f"{len(data)} entr{'y' if len(data) == 1 else 'ies'}")
        else:
            status_var.set(empty_text)

    def _refresh_all(self) -> None:
        for tree, rows_by_iid, status_var, only_unack, empty_text in self.__dict__.get("_sections", []):
            self._populate(tree, rows_by_iid, status_var, only_unack, empty_text)
        for tree, cols, load_fn, status_var, empty_text in self.__dict__.get("_readonly_sections", []):
            self._populate_readonly(tree, cols, load_fn, status_var, empty_text)

    def _save_ack(
        self,
        tree: ttk.Treeview,
        rows_by_iid: dict[str, tuple[str, ScanRecord]],
        ack_var: tk.StringVar,
        status_var: tk.StringVar,
        only_unacknowledged: bool,
    ) -> None:
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("warning", "Select a row first.", parent=self)
            return
        record_id, rec = rows_by_iid[sel[0]]
        try:
            ok = patch_admin_ack(record_id, ack_var.get().strip())
        except APIClientError as exc:
            messagebox.showerror(
                "Server error", f"Could not save acknowledgement:\n{exc}", parent=self
            )
            return
        if not ok:
            messagebox.showerror("error", "Could not save. Refresh and try again.", parent=self)
            return
        messagebox.showinfo("info", "Saved.", parent=self)
        self._refresh_all()


def open_admin_settings(parent: tk.Misc, *, current_user: str) -> None:
    AdminSettingsDialog(parent, current_user=current_user)
