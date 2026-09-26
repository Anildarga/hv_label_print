from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from common.auth.user_store import authenticate_user


class LoginScreen(ttk.Frame):
    

    def __init__(self, parent: tk.Misc, on_success: Callable[[str, str, str], None]) -> None:
        super().__init__(parent)
        self._on_success = on_success

        container = ttk.Frame(self, padding=32)
        container.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(
            container, text="BMS Label Suite — Login",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=2, pady=(0, 20))

        ttk.Label(container, text="Username").grid(row=1, column=0, sticky=tk.W, pady=6)
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(container, textvariable=self.username_var, width=30)
        self.username_entry.grid(row=1, column=1, sticky=tk.EW, pady=6)

        ttk.Label(container, text="Password").grid(row=2, column=0, sticky=tk.W, pady=6)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(container, textvariable=self.password_var, width=30, show="*")
        self.password_entry.grid(row=2, column=1, sticky=tk.EW, pady=6)

        ttk.Button(container, text="Login", command=self._submit).grid(
            row=3, column=0, columnspan=2, pady=(20, 0), sticky=tk.EW
        )

        container.columnconfigure(1, weight=1)
        self.username_entry.focus_set()
        self.bind_all("<Return>", lambda _e: self._submit())

    def _submit(self) -> None:
        password = self.password_var.get()
        ok, message, role = authenticate_user(self.username_var.get(), password)
        if not ok:
            messagebox.showerror("Login", message, parent=self)
            return
        self.unbind_all("<Return>")
        self._on_success(message, password, role)