from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path


from models.hv.printing.spooler import DOCINFO1, PRINTER_NAME, _resolve_printer_name

FONT_FILES = [
    (r"C:\Users\RadarCalibration\Downloads\Fonts\Fonts\BrutalType-Black.ttf", "BRUTALTYPE-BLACK.TTF"),
    (r"C:\Users\RadarCalibration\Downloads\Fonts\Fonts\BrutalType-Medium.ttf", "BRUTALTYPE-MEDIUM.TTF"),
]

# Printer's E: memory (other memory locations also there. refer them)
DEST_DRIVE = "E"


def _build_du_payload(font_bytes: bytes, printer_filename: str) -> bytes:
    
    name = Path(printer_filename).stem[:8].upper()
    ext = Path(printer_filename).suffix.lstrip(".").upper() or "TTF"
    header = f"~DU{DEST_DRIVE}:{name}.{ext},{len(font_bytes)},".encode("ascii")
    return header + font_bytes


def send_zpl_bytes(payload: bytes, printer_name: str = PRINTER_NAME) -> None:
    
    resolved_name = _resolve_printer_name(printer_name)

    winspool = ctypes.WinDLL("winspool.drv")
    winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    winspool.OpenPrinterW.restype = wintypes.BOOL
    winspool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(DOCINFO1)]
    winspool.StartDocPrinterW.restype = wintypes.DWORD
    winspool.StartPagePrinter.argtypes = [wintypes.HANDLE]
    winspool.StartPagePrinter.restype = wintypes.BOOL
    winspool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    winspool.WritePrinter.restype = wintypes.BOOL
    winspool.EndPagePrinter.argtypes = [wintypes.HANDLE]
    winspool.EndPagePrinter.restype = wintypes.BOOL
    winspool.EndDocPrinter.argtypes = [wintypes.HANDLE]
    winspool.EndDocPrinter.restype = wintypes.BOOL
    winspool.ClosePrinter.argtypes = [wintypes.HANDLE]
    winspool.ClosePrinter.restype = wintypes.BOOL

    hprinter = wintypes.HANDLE()
    if not winspool.OpenPrinterW(resolved_name, ctypes.byref(hprinter), None):
        raise OSError(f'Could not open printer "{resolved_name}" (error {ctypes.GetLastError()}).')

    try:
        job_id = 0
        last_error = 0
        for datatype in ("RAW", None):
            doc_info = DOCINFO1("BMS Font Install", None, datatype)
            job_id = winspool.StartDocPrinterW(hprinter, 1, ctypes.byref(doc_info))
            if job_id != 0:
                break
            last_error = ctypes.GetLastError()

        if job_id == 0:
            raise OSError(f"StartDocPrinterW failed (error {last_error}).")

        try:
            if not winspool.StartPagePrinter(hprinter):
                raise OSError(f"StartPagePrinter failed (error {ctypes.GetLastError()}).")

            written = wintypes.DWORD(0)
            buf = ctypes.create_string_buffer(payload, len(payload))
            if not winspool.WritePrinter(hprinter, buf, len(payload), ctypes.byref(written)):
                raise OSError(f"WritePrinter failed (error {ctypes.GetLastError()}).")
            if written.value != len(payload):
                raise OSError(f"WritePrinter wrote {written.value}/{len(payload)} bytes.")
        finally:
            winspool.EndPagePrinter(hprinter)
            winspool.EndDocPrinter(hprinter)
    finally:
        winspool.ClosePrinter(hprinter)


def main() -> None:
    if os.name != "nt":
        print("This script must be run on the Windows PC connected to the printer.")
        sys.exit(1)

    for local_path, printer_filename in FONT_FILES:
        path = Path(local_path)
        if not path.exists():
            print(f"SKIPPED — file not found: {local_path}")
            continue

        font_bytes = path.read_bytes()
        payload = _build_du_payload(font_bytes, printer_filename)

        print(f"Uploading {path.name} ({len(font_bytes):,} bytes) -> {DEST_DRIVE}:{printer_filename} ...")
        try:
            send_zpl_bytes(payload)
        except OSError as exc:
            print(f"  FAILED: {exc}")
            continue
        print(f"  Done — reference it in ZPL as ^A@N,h,w,{DEST_DRIVE}:{printer_filename}")

    print("Font install finished, only one time upload needed.")


if __name__ == "__main__":
    main() 
    """ python install_fonts.py """