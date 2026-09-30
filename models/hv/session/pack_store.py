from __future__ import annotations

from common.api_client import get, post, put
from models.hv.nomenclature.serial_number import build_serial_number, parse_serial_number


def save_pack_serial(serial_number: str) -> None:
    serial_number = serial_number.strip()
    if not serial_number:
        return
    parsed = parse_serial_number(serial_number)
    if parsed is None:
        raise ValueError("Invalid pack serial number.")
    put("/serial/current", {"serial_number": parsed.raw})


def load_pack_serial() -> str:
    state = get("/serial/current")
    return str(state.get("serial_number") or "").strip()


def load_pack_serial_count() -> str:
    state = get("/serial/current")
    return str(state.get("serial_count") or "").strip()


def save_pack_serial_count(serial_count: str) -> None:
    serial_count = serial_count.strip()
    if not serial_count:
        return
    current = load_pack_serial()
    parsed = parse_serial_number(current)
    if parsed is None:
        raise ValueError("Cannot update serial count because no valid pack serial is stored.")
    width = 5 if parsed.is_new_format else 6
    if not serial_count.isdigit() or len(serial_count) > width:
        raise ValueError(f"Serial count must contain at most {width} digits.")
    extra = {}
    if parsed.is_new_format:
        extra = {
            "model": parsed.model,
            "variant": parsed.variant,
            "shift": parsed.shift,
            "category": parsed.category,
        }
    updated_serial = build_serial_number(
        plant=parsed.plant,
        line=parsed.line,
        when=parsed.as_date,
        serial_count=serial_count.zfill(width),
        **extra,
    )
    save_pack_serial(updated_serial)


def increment_pack_serial() -> str:
    current = load_pack_serial()
    if not current:
        return ""
    allocation = post("/serial/allocate", {"current_serial": current})
    serial_number = str(allocation.get("serial_number") or "").strip()
    if not serial_number:
        raise RuntimeError("Server allocated a serial number but returned an empty value.")
    return serial_number
