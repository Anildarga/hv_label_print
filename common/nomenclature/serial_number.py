from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

# OLD format plant codes
PLANT_CODES = {
    "jigani": "A",
    "domlur": "B",
}
PLANT_BY_CODE = {code: name for name, code in PLANT_CODES.items()}

SERIAL_NUMBER_PATTERN = re.compile(
    r"^(?P<plant>[AB])(?P<line>[123])(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})"
    r"(?P<serial_count>\d{6})$"
)

# -- NEW format code 
NEW_PLANT_CODES = {
    "jigani": "A",
    "domlur": "B",
    "plant_c": "C",  
}
NEW_PLANT_BY_CODE = {code: name for name, code in NEW_PLANT_CODES.items()}

MODEL_CODES = {
    "low voltage": "A",
    "high voltage": "B",
    "shockwave": "C",
    "tesseract": "D",
}
MODEL_BY_CODE = {code: name for name, code in MODEL_CODES.items()}

MODULE_VARIANT_CODES_NEW = {
    # "33P": "A1",  # low voltage
    # "48P": "A2",  # low voltage
    "12P": "A3",  # high voltage
    "16P": "A4",  # high voltage
    "24P": "A5",  # high voltage
    "27P": "A6",  # high voltage
    # "8P": "A7",   # NA
    # "10P": "A8",  #NA
}
VARIANT_BY_CODE_NEW = {code: name for name, code in MODULE_VARIANT_CODES_NEW.items()}

# Category: numeric in the new format.
CATEGORY_CODES_NEW = {
    "domestic": "1",
    "export": "2",
}
CATEGORY_BY_CODE_NEW = {code: name for name, code in CATEGORY_CODES_NEW.items()}

# Shift: letter in the new format.
SHIFT_CODES_NEW = {"A": "A", "B": "B", "C": "C"}

NEW_SERIAL_NUMBER_PATTERN = re.compile(
    r"^(?P<plant>[ABC])(?P<model>[ABCD])(?P<variant>A[3-6])(?P<line>[123])"
    r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})"
    r"(?P<category>[12])(?P<shift>[ABC])(?P<serial_count>\d{5})$"
)


@dataclass(frozen=True)
class ParsedSerialNumber:
    plant: str
    line: str
    year: int
    month: int
    day: int
    serial_count: str
    raw: str
    # New-format-only fields - empty/None when parsed from the old format.
    model: str | None = None
    variant: str | None = None
    shift: str | None = None
    category: str | None = None

    @property
    def is_new_format(self) -> bool:
        return self.model is not None

    @property
    def is_export(self) -> bool:
        return (self.category or "").strip().lower() == "export"

    @property
    def as_date(self) -> date:
        return date(self.year, self.month, self.day)

    def format_date(self) -> str:
        return self.as_date.strftime("%d %b %Y")


def build_serial_number(
    *,
    plant: str,
    line: str,
    when: datetime | date,
    serial_count: str,
    model: str | None = None,
    variant: str | None = None,
    shift: str | None = None,
    category: str | None = None,
) -> str:
    
    plant_key = plant.strip().lower()
    if isinstance(when, datetime):
        when = when.date()

    new_format_requested = any(v is not None for v in (model, variant, shift, category))

    if not new_format_requested:
        if plant_key not in PLANT_CODES:
            raise ValueError(f"Unsupported plant: {plant}")
        if line not in {"1", "2", "3"}:
            raise ValueError(f"Unsupported line: {line}")

        count = re.sub(r"\D", "", serial_count or "").zfill(6)[-6:]

        return f"{PLANT_CODES[plant_key]}{line}{when:%Y%m%d}{count}"

    # -- NEW format --
    if plant_key not in NEW_PLANT_CODES:
        raise ValueError(f"Unsupported plant: {plant}")
    if line not in {"1", "2", "3"}:
        raise ValueError(f"Unsupported line: {line}")

    model_key = (model or "").strip().lower()
    if model_key not in MODEL_CODES:
        raise ValueError(f"Unsupported model: {model}")

    variant_key = (variant or "").strip().upper()
    if variant_key not in MODULE_VARIANT_CODES_NEW:
        raise ValueError(f"Unsupported variant: {variant}")

    shift_key = (shift or "").strip().upper()
    if shift_key not in SHIFT_CODES_NEW:
        raise ValueError(f"Unsupported shift: {shift}")

    category_key = (category or "").strip().lower()
    if category_key not in CATEGORY_CODES_NEW:
        raise ValueError(f"Unsupported category: {category}")

    count = re.sub(r"\D", "", serial_count or "").zfill(5)[-5:]

    return (
        f"{NEW_PLANT_CODES[plant_key]}"
        f"{MODEL_CODES[model_key]}"
        f"{MODULE_VARIANT_CODES_NEW[variant_key]}"
        f"{line}"
        f"{when:%Y%m%d}"
        f"{CATEGORY_CODES_NEW[category_key]}"
        f"{SHIFT_CODES_NEW[shift_key]}"
        f"{count}"
    )


def build_serial_number_for_model(
    model: str,
    *,
    plant: str,
    line: str,
    when: datetime | date,
    serial_count: str,
    variant: str,
    shift: str,
    category: str,
) -> str:
    
    return build_serial_number(
        plant=plant,
        line=line,
        when=when,
        serial_count=serial_count,
        model=model,
        variant=variant,
        shift=shift,
        category=category,
    )


def _parse_new_format(cleaned: str) -> ParsedSerialNumber | None:
    match = NEW_SERIAL_NUMBER_PATTERN.match(cleaned)
    if not match:
        return None

    g = match.groupdict()
    plant_code = g["plant"]
    model_code = g["model"]
    variant_code = g["variant"]
    category_code = g["category"]

    if plant_code not in NEW_PLANT_BY_CODE:
        return None
    if model_code not in MODEL_BY_CODE:
        return None
    if variant_code not in VARIANT_BY_CODE_NEW:
        return None

    try:
        date(int(g["year"]), int(g["month"]), int(g["day"]))
    except ValueError:
        return None

    return ParsedSerialNumber(
        plant=NEW_PLANT_BY_CODE[plant_code],
        line=g["line"],
        year=int(g["year"]),
        month=int(g["month"]),
        day=int(g["day"]),
        serial_count=g["serial_count"],
        raw=cleaned,
        model=MODEL_BY_CODE[model_code],
        variant=VARIANT_BY_CODE_NEW[variant_code],
        shift=g["shift"],
        category=CATEGORY_BY_CODE_NEW[category_code],
    )


def _parse_old_format(cleaned: str) -> ParsedSerialNumber | None:
    match = SERIAL_NUMBER_PATTERN.match(cleaned)
    if not match:
        return None

    g = match.groupdict()
    plant_code = g["plant"]

    if plant_code not in PLANT_BY_CODE:
        return None

    try:
        date(int(g["year"]), int(g["month"]), int(g["day"]))
    except ValueError:
        return None

    return ParsedSerialNumber(
        plant=PLANT_BY_CODE[plant_code],
        line=g["line"],
        year=int(g["year"]),
        month=int(g["month"]),
        day=int(g["day"]),
        serial_count=g["serial_count"],
        raw=cleaned,
    )


def parse_serial_number(value: str) -> ParsedSerialNumber | None:
    cleaned = value.strip().upper()

    if len(cleaned) == 20:
        return _parse_new_format(cleaned)
    if len(cleaned) == 16:
        return _parse_old_format(cleaned)

    return _parse_new_format(cleaned) or _parse_old_format(cleaned)
