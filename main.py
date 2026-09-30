from __future__ import annotations

import sys
import traceback
from pathlib import Path
from tkinter import messagebox
# import webbrowser
#import subprocess
# import os

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tkinter as tk
# from tkinter import ttk


from common.api_client import APIClientError
from common.auth.machine_lock import is_authorized
from common.auth.session import Session
from models.hv.app import HVApp


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ASSETS_DIR = _base_dir() / "models" / "hv" / "assets"


def _install_error_dialog(root: tk.Tk) -> None:
    def _report(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb)
        detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))[-1500:]
        try:
            messagebox.showerror("Unexpected error", f"{exc_value}\n\n{detail}", parent=root)
        except Exception:
            pass

    root.report_callback_exception = _report


# def _show_unauthorized_dialog(root: tk.Tk) -> None:
    
#     dialog = tk.Toplevel(root)
#     dialog.title("\u26A0 Auth error")
#     # dialog.minsize(200,100)
#     dialog.resizable(False, False)
#     dialog.protocol("WM_DELETE_WINDOW", lambda: (dialog.destroy(), root.destroy()))
    
    
#     def contact_admin():
#         webbrowser.open("mailto:radarcalibration@ultraviolette.com?subject=Access%20Request%20to%20HV%20Label%20Printer")
#         #webbrowser.open("https://teams.microsoft.com/l/chat/48:notes/conversations?context=%7B%22contextType%22%3A%22chat%22%7D?subject=Support%20Request")
#         root.destroy()
        
    # frame = ttk.Frame(dialog, padding=24)
    # frame.pack()
    # ttk.Label(
    #     frame, text="This machine is not authorised.",
    #     font=("calibri", 13),
    # ).pack(pady=(0, 16))
    # ttk.Button(
    #         frame, text="Contact Admin",
    #         command=contact_admin,
    #     ).pack(side="left", padx=(5,30))
    # ttk.Button(
    #     frame, text="Close",
    #     command=lambda: (dialog.destroy(), root.destroy()),
    # ).pack(side="left")
    

    # dialog.update_idletasks()
    # x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
    # y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
    # dialog.geometry(f"+{x}+{y}")

    # dialog.grab_set()
    # dialog.wait_window()


def main() -> None:
    root = tk.Tk()
    
    # def _resource_path(relative: str) -> Path:
    #     base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    #     return base / relative

    try:
        authorized = is_authorized()
    except APIClientError as exc:
        root.withdraw()
        messagebox.showerror(
            "Server unavailable",
            f"Cannot verify this machine or print labels until the server is reachable.\n\n{exc}",
        )
        root.destroy()
        return
    if not authorized:
        root.withdraw()  # never show the main window
        # _show_unauthorized_dialog
        messagebox.showwarning("Warning", "This Machine is not Authorized")
        sys.exit(1)

    root.title("HV Label Printer — ULTRAVIOLETTE AUTOMATIVE")
    # root.geometry("1280x860")
    # root.minsize(1000, 600)
    root.resizable(False,False)
    root.state("zoomed")

    icon_path = ASSETS_DIR / "logo.ico"
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except tk.TclError:
            pass


    _install_error_dialog(root)

    session = Session() # logged out by default — AuthBar shows its own Login button
    try:
        HVApp(root, session=session).pack(fill=tk.BOTH, expand=False)
    except APIClientError as exc:
        messagebox.showerror(
            "Server unavailable",
            f"Could not load server-backed serial data. Printing is blocked until the server is reachable.\n\n{exc}",
            parent=root,
        )
        root.destroy()
        return
    

    root.mainloop()


if __name__ == "__main__":
    main()