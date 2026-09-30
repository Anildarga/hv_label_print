from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any
from tkinter import messagebox, ttk

from common.api_client import APIClientError
from common.auth.user_store import ROLE_ADMIN, ROLE_OPERATOR, add_user, authenticate_user, delete_user, list_users


class _CenteredDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

    def _center_over_parent(self, parent: tk.Misc) -> None:
        parent_widget = parent.winfo_toplevel()
        self.update_idletasks()
        x = parent_widget.winfo_rootx() + (parent_widget.winfo_width() - self.winfo_width()) // 2
        y = parent_widget.winfo_rooty() + (parent_widget.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


class LoginDialog(_CenteredDialog):
    def __init__(self, parent: tk.Misc, on_success: Callable[..., Any]) -> None:
        self._on_success = on_success
        super().__init__(parent, "Login")

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Login", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12)
        )

        ttk.Label(frame, text="Username").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(frame, textvariable=self.username_var, width=28)
        self.username_entry.grid(row=1, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Password").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(frame, textvariable=self.password_var, width=28, show="*")
        self.password_entry.grid(row=2, column=1, sticky=tk.EW, pady=4)

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky=tk.E, pady=(16, 0))

        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Login", command=self._submit).pack(side=tk.LEFT)

        frame.columnconfigure(1, weight=1)
        self.username_entry.focus_set()
        self.bind("<Return>", lambda _event: self._submit())

        self._center_over_parent(parent)

    def _submit(self) -> None:
        password = self.password_var.get()
        try:
            ok, message, role = authenticate_user(self.username_var.get(), password)
        except APIClientError as exc:
            messagebox.showerror(
                "Server unavailable",
                f"Could not sign in. Check the server connection and try again.\n\n{exc}",
                parent=self,
            )
            return
        if not ok:
            messagebox.showerror("Login", message, parent=self)
            return
        self._on_success(message, password, role)
        self.destroy()


class ManageUsersDialog(_CenteredDialog):

    def __init__(self, parent: tk.Misc, current_user: str) -> None:
        self.current_user = current_user
        super().__init__(parent, "Manage Users")

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Manage Users", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12)
        )

        ttk.Label(frame, text="Existing Users").grid(row=1, column=0, columnspan=2, sticky=tk.W)
        self.users_listbox = tk.Listbox(frame, height=7, width=36)
        self.users_listbox.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 10))
        self._refresh_users()

        ttk.Button(frame, text="Remove Selected", command=self._on_delete).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 14)
        )

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        ttk.Label(frame, text="Add New User", font=("Segoe UI", 10, "bold")).grid(
            row=5, column=0, columnspan=2, sticky=tk.W, pady=(0, 8)
        )

        ttk.Label(frame, text="Username").grid(row=6, column=0, sticky=tk.W, pady=4)
        self.new_username_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.new_username_var, width=28).grid(row=6, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Password (>=8)").grid(row=7, column=0, sticky=tk.W, pady=4)
        self.new_password_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.new_password_var, width=28, show="*").grid(
            row=7, column=1, sticky=tk.EW, pady=4
        )

        ttk.Label(frame, text="Role").grid(row=8, column=0, sticky=tk.W, pady=4)
        self.new_role_var = tk.StringVar(value="Operator")
        ttk.Combobox(
            frame, textvariable=self.new_role_var, values=["Admin", "Operator"],
            state="readonly", width=25,
        ).grid(row=8, column=1, sticky=tk.EW, pady=4)

        buttons = ttk.Frame(frame)
        buttons.grid(row=9, column=0, columnspan=2, sticky=tk.E, pady=(16, 0))
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Add User", command=self._on_add).pack(side=tk.LEFT)

        frame.columnconfigure(1, weight=1)
        self._center_over_parent(parent)

    def _refresh_users(self) -> None:
        self.users_listbox.delete(0, tk.END)
        try:
            users = list_users()
        except APIClientError as exc:
            messagebox.showerror(
                "Server error", f"Could not load users:\n{exc}", parent=self
            )
            return
        for username, role in users:
            role_label = "Admin" if role == ROLE_ADMIN else "Operator"
            label = f"{username}  ({role_label})"
            if username == self.current_user:
                label += "  — you"
            self.users_listbox.insert(tk.END, label)

    def _on_add(self) -> None:
        role = ROLE_ADMIN if self.new_role_var.get() == "Admin" else ROLE_OPERATOR
        try:
            ok, message = add_user(self.new_username_var.get(), self.new_password_var.get(), role)
        except APIClientError as exc:
            messagebox.showerror("Server error", f"Could not add user:\n{exc}", parent=self)
            return
        if not ok:
            messagebox.showerror("Add User", message, parent=self)
            return
        messagebox.showinfo("Add User", message, parent=self)
        self.new_username_var.set("")
        self.new_password_var.set("")
        self._refresh_users()

    def _on_delete(self) -> None:
        selection = self.users_listbox.curselection()
        if not selection:
            messagebox.showwarning("Remove User", "Select a user to remove.", parent=self)
            return

        label = self.users_listbox.get(selection[0])
        username = label.split("  (")[0]

        if not messagebox.askyesno("Remove User", f'Remove "{username}"?', parent=self):
            return

        try:
            ok, message = delete_user(username, current_user=self.current_user)
        except APIClientError as exc:
            messagebox.showerror("Server error", f"Could not remove user:\n{exc}", parent=self)
            return
        if not ok:
            messagebox.showerror("Remove User", message, parent=self)
            return
        messagebox.showinfo("Remove User", message, parent=self)
        self._refresh_users()


def open_login_dialog(parent: tk.Misc, on_success: Callable[..., Any]) -> None:
    LoginDialog(parent, on_success)