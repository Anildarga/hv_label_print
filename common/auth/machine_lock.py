from __future__ import annotations

import hashlib
import platform
import sys

from common.api_client import APIClientError, get

AUTHORIZED_HASHES = {"6ffd448e61c84b0f5d2eb41304eb76df0b2cfb0f79d2476a5f8ab232b6a5f0b2", "0300cac0dfe775b53c6ee8ed0a35a22e1e5b8db8b8712aa44f7e34435233e767", "542208c237138aafade60a7190238712faa9a7683c567701dd026338fecf9e7d", "a9cd7d93c0388e793fb35cfdd708ca04c33a7975b8eb72a9d816fa012064aa70", "2e4d2fa6c54b82a39f2ee81d71ff7441f6ea666335bce7199fbecea4330c7a86"}


def _raw_machine_id() -> str:
    if platform.system() != "Windows":
        return "NON-WINDOWS-DEV-ENVIRONMENT"

    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        )
        value, _type = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return str(value)
    except OSError:
        return "UNREADABLE-MACHINE-GUID"


def get_machine_hash() -> str:
    raw = _raw_machine_id()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_authorized() -> bool:
    try:
        result = get("/devices/check")
    except APIClientError as exc:
        if exc.status_code == 403:
            return False
        raise
    if not isinstance(result, dict):
        return False
    return result.get("authorized") is True


if __name__ == "__main__":
    print("This machine's hash:")
    print(get_machine_hash())
    print()
    print("Register it with: python server\\manage.py add-device --name \"PC name\" --hash <machine_hash>")
    sys.exit(0)