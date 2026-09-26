from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from models.hv.nomenclature.serial_number import build_serial_number, parse_serial_number
from models.hv.session.paths import get_base_dir

PACK_SESSION_FILE = get_base_dir() / "data" / "pack_session.json"

_SAVE_RETRY_ATTEMPTS = 5
_SAVE_RETRY_DELAY_SECONDS = 0.05


def _load() -> dict[str, str]:
    if not PACK_SESSION_FILE.exists():
        return {}
    try:
        with PACK_SESSION_FILE.open(encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
       
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, str]) -> None:
    PACK_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
  
    fd, tmp_path = tempfile.mkstemp(
        dir=PACK_SESSION_FILE.parent, prefix=PACK_SESSION_FILE.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

        last_error: OSError | None = None
        for attempt in range(_SAVE_RETRY_ATTEMPTS):
            try:
                os.replace(tmp_path, PACK_SESSION_FILE)
                return
            except OSError as exc:
                last_error = exc
                if attempt < _SAVE_RETRY_ATTEMPTS - 1:
                    time.sleep(_SAVE_RETRY_DELAY_SECONDS * (attempt + 1))
        assert last_error is not None
        raise last_error
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def save_pack_serial(serial_number: str) -> None:
    
    serial_number = serial_number.strip()
    if not serial_number:
        return
    data = _load()
    data["serial_number"] = serial_number

    parsed = parse_serial_number(serial_number)
    if parsed is not None:
        data["serial_count"] = parsed.serial_count

    _save(data)


def load_pack_serial() -> str:
    return _load().get("serial_number", "").strip()


def load_pack_serial_count() -> str:
    return _load().get("serial_count", "").strip()


def save_pack_serial_count(serial_count: str) -> None:
    serial_count = serial_count.strip()
    if not serial_count:
        return
    data = _load()
    data["serial_count"] = serial_count
    _save(data)


def increment_pack_serial() -> str:
    current = load_pack_serial()
    if not current:
        return ""

    parsed = parse_serial_number(current)
    if parsed is None:
        return current

    pad = 5 if parsed.is_new_format else 6
    new_count = str(int(parsed.serial_count) + 1).zfill(pad)

    extra = {}
    if parsed.is_new_format:
        extra = {
            "model": parsed.model,
            "variant": parsed.variant,
            "shift": parsed.shift,
            "category": parsed.category,
        }

    new_serial = build_serial_number(
        plant=parsed.plant,
        line=parsed.line,
        when=parsed.as_date,
        serial_count=new_count,
        **extra,
    )
    save_pack_serial(new_serial)
    return new_serial