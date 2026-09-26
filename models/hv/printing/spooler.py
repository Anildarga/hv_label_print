from __future__ import annotations

import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

from models.hv.printing.constants import PRINTER_NAME


_PRINTER_CACHE: dict[str, tuple[str, float]] = {}
_PRINTER_CACHE_TTL_SECONDS = 120.0


class DOCINFO1(ctypes.Structure):
    _fields_ = [
        ("pDocName",    wintypes.LPWSTR),
        ("pOutputFile", wintypes.LPWSTR),
        ("pDatatype",   wintypes.LPWSTR),
    ]


def _list_installed_printers() -> list[str]:
    if os.name != "nt":
        return []
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Printer | Select-Object -ExpandProperty Name"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _resolve_printer_name(printer_name: str) -> str:
    cached = _PRINTER_CACHE.get(printer_name)
    if cached is not None:
        resolved, cached_at = cached
        if time.monotonic() - cached_at < _PRINTER_CACHE_TTL_SECONDS:
            return resolved

    if os.name != "nt":
        raise OSError("Raw ZPL printing is only supported on Windows.")
    names = _list_installed_printers()

    if printer_name in names:
        resolved = printer_name
    else:
        resolved = next(
            (name for name in names if printer_name.lower() in name.lower()),
            None,
        )
        if resolved is None:
            if not names:
                resolved = printer_name  # nothing to compare against — try it as-is
            else:
                raise OSError(
                    f'Printer "{printer_name}" not found. Available printers: {", ".join(names)}'
                )

    _PRINTER_CACHE[printer_name] = (resolved, time.monotonic())
    return resolved


def send_zpl(zpl: str, printer_name: str = PRINTER_NAME) -> None:
    resolved_name = _resolve_printer_name(printer_name)
    payload = zpl.encode("utf-8")

    winspool = ctypes.WinDLL("winspool.drv")  

    winspool.OpenPrinterW.argtypes  = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    winspool.OpenPrinterW.restype   = wintypes.BOOL
    winspool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(DOCINFO1)]
    winspool.StartDocPrinterW.restype  = wintypes.DWORD
    winspool.StartPagePrinter.argtypes = [wintypes.HANDLE]
    winspool.StartPagePrinter.restype  = wintypes.BOOL
    winspool.WritePrinter.argtypes  = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    winspool.WritePrinter.restype   = wintypes.BOOL
    winspool.EndPagePrinter.argtypes  = [wintypes.HANDLE]
    winspool.EndPagePrinter.restype   = wintypes.BOOL
    winspool.EndDocPrinter.argtypes   = [wintypes.HANDLE]
    winspool.EndDocPrinter.restype    = wintypes.BOOL
    winspool.ClosePrinter.argtypes    = [wintypes.HANDLE]
    winspool.ClosePrinter.restype     = wintypes.BOOL

    hprinter = wintypes.HANDLE()
    if not winspool.OpenPrinterW(resolved_name, ctypes.byref(hprinter), None):
        raise OSError(f'Could not open printer "{resolved_name}" (OpenPrinterW failed, error {ctypes.GetLastError()}).')

    try:
        job_id = 0
        last_error = 0
        for datatype in ("RAW", None):
            doc_info = DOCINFO1("BMS Label", None, datatype)
            job_id = winspool.StartDocPrinterW(hprinter, 1, ctypes.byref(doc_info))
            if job_id != 0:
                break
            last_error = ctypes.GetLastError()

        if job_id == 0:
            raise OSError(
                f'StartDocPrinterW failed (error {last_error}). '
                f'This usually means the printer driver for "{resolved_name}" is missing '
                f'or corrupted — try restarting the Print Spooler service or '
                f'reinstalling the ZDesigner driver.'
            )

        try:
            if not winspool.StartPagePrinter(hprinter):
                raise OSError(f'StartPagePrinter failed (error {ctypes.GetLastError()}).')

            written = wintypes.DWORD(0)
            buf = ctypes.create_string_buffer(payload)
            if not winspool.WritePrinter(hprinter, buf, len(payload), ctypes.byref(written)):
                raise OSError(f'WritePrinter failed (error {ctypes.GetLastError()}).')
            if written.value != len(payload):
                raise OSError(f'WritePrinter wrote {written.value}/{len(payload)} bytes.')
        finally:
            winspool.EndPagePrinter(hprinter)
            winspool.EndDocPrinter(hprinter)
    finally:
        winspool.ClosePrinter(hprinter)


def save_zpl(zpl: str, path: str | Path) -> Path:
    output = Path(path)
    output.write_text(zpl, encoding="utf-8")
    return output  #6363676070