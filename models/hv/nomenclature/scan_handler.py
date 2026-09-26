"""Pack serial QR format:  VX156060:A120260608006675
VX156060:ABA51202605281A00111
"""
from __future__ import annotations

import re
from dataclasses import dataclass#, field
from enum import Enum

from models.hv.gui.constants import REESS_TO_VARIANT
from models.hv.nomenclature.bms_id import parse_bmb_cmb_id, parse_bms_id, parse_bms_qr
from models.hv.nomenclature.module_id import ParsedModuleId, parse_module_id
from models.hv.nomenclature.serial_number import ParsedSerialNumber, parse_serial_number

_PACK_QR_PATTERN = re.compile(
    r"^(?P<reess>[A-Z0-9]+):(?P<serial>[A-Z0-9]+)$",
    re.IGNORECASE,
)

VARIANT_BY_REESS: dict[str, str] = REESS_TO_VARIANT


class ScanType(Enum):
    SERIAL_NUMBER = "serial_number"
    MODULE_ID = "module_id"
    BMB_ID = "bmb_id"
    CMB_ID = "cmb_id"
    BMS_ID = "bms_id"  
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScanResult:
    raw: str
    scan_type: ScanType
    serial: ParsedSerialNumber | None = None
    module: ParsedModuleId | None = None
    bms_id: str | None = None
    bms_sw_version: str | None = None  
    bmb_cmb: object | None = None  
    pack_variant: str | None = None 
    pack_revision: str | None = None  


def identify_scan(value: str) -> ScanResult:
    cleaned = value.strip()
    if not cleaned:
        return ScanResult(raw="", scan_type=ScanType.UNKNOWN)

    pack_qr_match = _PACK_QR_PATTERN.match(cleaned)
    if pack_qr_match:
        reess_part = pack_qr_match.group("reess").upper()
        serial_raw = pack_qr_match.group("serial")
        serial = parse_serial_number(serial_raw)
        if serial is not None:
            variant = VARIANT_BY_REESS.get(reess_part)
            return ScanResult(
                raw=cleaned.upper(),
                scan_type=ScanType.SERIAL_NUMBER,
                serial=serial,
                pack_variant=variant,
                pack_revision=None,
            )

    module = parse_module_id(cleaned)
    if module is not None:
        return ScanResult(raw=module.raw, scan_type=ScanType.MODULE_ID, module=module)

    serial = parse_serial_number(cleaned)
    if serial is not None:
        return ScanResult(raw=serial.raw, scan_type=ScanType.SERIAL_NUMBER, serial=serial)

    bmb_cmb = parse_bmb_cmb_id(cleaned)
    if bmb_cmb is not None:
        scan_type = ScanType.BMB_ID if bmb_cmb.kind == "BMB" else ScanType.CMB_ID
        return ScanResult(raw=bmb_cmb.raw, scan_type=scan_type, bmb_cmb=bmb_cmb)

    bms_qr = parse_bms_qr(cleaned)
    if bms_qr is not None:
        return ScanResult(
            raw=bms_qr.bms_id,
            scan_type=ScanType.BMS_ID,
            bms_id=bms_qr.bms_id,
            bms_sw_version=bms_qr.sw_version,
        )

    bms_id = parse_bms_id(cleaned)
    if bms_id is not None:
        return ScanResult(raw=bms_id, scan_type=ScanType.BMS_ID, bms_id=bms_id)

    return ScanResult(raw=cleaned.upper(), scan_type=ScanType.UNKNOWN)