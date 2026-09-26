""" VX156610-E1611109G260076 """

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from models.hv.gui.constants import (
    MODULE_VARIANT_CODES, VARIANT_BY_CODE,
    GROUP_CODES, GROUP_BY_CODE,
    CELL_MFR_CODES, CELL_MFR_BY_CODE,
    PLANT_CODES_HV, PLANT_BY_CODE_HV,
    SHIFT_CODES_HV,
    MONTH_CODES, MONTH_BY_CODE,
    VARIANT_TO_MODEL,
)

_SUB_PATTERN = re.compile(
    r"^(?P<variant>[C-F])"
    r"(?P<group>[1-6])"
    r"(?P<cell_mfr>[1-6])"
    r"(?P<plant>[123ABC])" #plant encoded (either 123 and ABC)
    r"(?P<line>[123])"
    r"(?P<shift>[123])"
    r"(?P<dd>\d{2})"
    r"(?P<month>[A-L])"
    r"(?P<yy>\d{2})"
    r"(?P<serial>\d{4})$"
)

_FULL_PATTERN = re.compile(
    r"^(?P<part_number>VX15[0-9]{4})-(?P<sub>[C-F][1-6][1-6][123ABC][123][123]\d{2}[A-L]\d{6})$"
)


@dataclass(frozen=True)
class ParsedModuleId:
    variant: str        
    part_number: str   
    group: str        
    cell_mfr: str      
    plant: str        
    line: str          
    day: int
    month: int
    year: int
    shift: str        
    serial: str       
    sub_id: str         
    raw: str          

    @property
    def as_date(self) -> date:
        return date(self.year, self.month, self.day)


def build_module_sub_id(
    *,
    variant: str,
    group: str,
    cell_mfr: str,
    plant: str,
    line: str,
    when: date | datetime,
    shift: str,
    serial: str,
) -> str:
    if isinstance(when, datetime):
        when = when.date()

    v_code  = MODULE_VARIANT_CODES.get(variant.strip())
    g_code  = GROUP_CODES.get(group.strip())
    cm_code = CELL_MFR_CODES.get(cell_mfr.strip())
    p_code  = PLANT_CODES_HV.get(plant.strip())
    sh_code = SHIFT_CODES_HV.get(shift.strip())
    m_code  = MONTH_CODES.get(when.month)

    if not all([v_code, g_code, cm_code, p_code, sh_code, m_code]):
        raise ValueError(
            f"Invalid code: variant={variant}, group={group}, "
            f"cell_mfr={cell_mfr}, plant={plant}, shift={shift}, month={when.month}"
        )
    if line not in ("1", "2", "3"):
        raise ValueError(f"Invalid line: {line}")

    digits = re.sub(r"\D", "", serial or "")
    if not digits:
        raise ValueError(f"Invalid module serial: {serial!r}")

    serial_number = int(digits)
    if not 0 <= serial_number <= 9999:
        raise ValueError(
            f"Module serial must be between 0000 and 9999; got {serial_number}."
        )

    count = f"{serial_number:04d}"

    return (
        f"{v_code}"
        f"{g_code}"
        f"{cm_code}"
        f"{p_code}"
        f"{line}"
        f"{sh_code}"
        f"{when.day:02d}"
        f"{m_code}"
        f"{when.year % 100:02d}"
        f"{count}"
    )


def build_full_module_id(
    *,
    variant: str,
    group: str,
    cell_mfr: str,
    plant: str,
    line: str,
    when: date | datetime,
    shift: str,
    serial: str,
) -> str:
    part_number = VARIANT_TO_MODEL.get(variant.strip())
    if not part_number:
        raise ValueError(f"Unknown variant: {variant}")
    sub = build_module_sub_id(
        variant=variant, group=group, cell_mfr=cell_mfr,
        plant=plant, line=line, when=when, shift=shift, serial=serial,
    )
    return f"{part_number}-{sub}"


def build_all_module_ids(
    *,
    variant: str,
    group: str,
    cell_mfr: str,
    plant: str,
    line: str,
    when: date | datetime,
    shift: str,
    start_serial: str,
    count: int = 4,
) -> list[str]:
    digits = re.sub(r"\D", "", start_serial or "")
    if not digits:
        raise ValueError(f"Invalid starting module serial: {start_serial!r}")

    start = int(digits)
    if count < 1:
        raise ValueError(f"Module ID count must be at least 1; got {count}.")

    end = start + count - 1
    if start < 0 or end > 9999:
        raise ValueError(
            f"Module serial sequence {start:04d}-{end:04d} exceeds the 0000-9999 range."
        )

    ids: list[str] = []
    for offset in range(count):
        serial = f"{start + offset:04d}"
        ids.append(
            build_full_module_id(
                variant=variant, group=group, cell_mfr=cell_mfr,
                plant=plant, line=line, when=when, shift=shift, serial=serial,
            )
        )
    return ids


build_module_id = build_full_module_id


def parse_module_id(value: str) -> ParsedModuleId | None:
    cleaned = value.strip().upper()
    m = _FULL_PATTERN.match(cleaned)
    if not m:
        return None

    part_number = m.group("part_number")
    sub   = m.group("sub")
    sm    = _SUB_PATTERN.match(sub)
    if not sm:
        return None

    g = sm.groupdict()
    variant  = VARIANT_BY_CODE.get(g["variant"])
    cell_mfr = CELL_MFR_BY_CODE.get(g["cell_mfr"])
    plant    = PLANT_BY_CODE_HV.get(g["plant"])
    group    = GROUP_BY_CODE.get(g["group"])
    month    = MONTH_BY_CODE.get(g["month"])

    if not all([variant, cell_mfr, plant, group, month]):
        return None

    if VARIANT_TO_MODEL.get(variant) != part_number:
        return None

    year  = 2000 + int(g["yy"])
    day   = int(g["dd"])
    try:
        date(year, month, day)
    except ValueError:
        return None

    shift_map = {"1": "Shift 1", "2": "Shift 2", "3": "Shift 3"}

    return ParsedModuleId(
        variant=variant,
        part_number=part_number,
        group=group,
        cell_mfr=cell_mfr,
        plant=plant,
        line=g["line"],
        day=day, month=month, year=year,
        shift=shift_map[g["shift"]],
        serial=g["serial"],
        sub_id=sub,
        raw=cleaned,
    )