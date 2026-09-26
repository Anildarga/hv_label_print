from __future__ import annotations

VARIANT_OPTIONS = ["12P", "16P", "24P", "27P"] #33p and 48p are low voltage type, 8p and 10p are shockwave type.

VARIANT_TO_MODEL = {
    "12P": "VX156590",
    "16P": "VX156600",
    "24P": "VX156610",
    "27P": "VX156620",
}

MODEL_TO_VARIANT = {v: k for k, v in VARIANT_TO_MODEL.items()}

REESS_BY_MODEL = {
    "VX156620": "VX155800",
    "VX156610": "VX156060",
    "VX156600": "VX156070",
    "VX156590": "VX156080",
}

REESS_TO_VARIANT = {reess: MODEL_TO_VARIANT[model] for model, reess in REESS_BY_MODEL.items()}

VARIANT_PARAMS = {
    "12P": {
        "rated_capacity": "6 kWh",
        "max_voltage":    "116.2 V",
        "model_number":   "VX156590",
        "type_of_reess":  "VX156080",
        "tac_number":     "AS8318",
        "emark":          "E11*136R01/00*0113*00",
        "energy_kwh":     "6 kWh",
    },
    "16P": {
        "rated_capacity": "8.1 kWh",
        "max_voltage":    "116.2 V",
        "model_number":   "VX156600",
        "type_of_reess":  "VX156070",
        "tac_number":     "AS8317",
        "emark":          "E11*136R01/00*0112*00",
        "energy_kwh":     "8.1 kWh",
    },
    "24P": {
        "rated_capacity": "12.1 kWh",
        "max_voltage":    "116.2 V",
        "model_number":   "VX156610",
        "type_of_reess":  "VX156060",
        "tac_number":     "AS8316",
        "emark":          "E11*136R01/00*0110*00",
        "energy_kwh":     "12.1 kWh",
    },
    "27P": {
        "rated_capacity": "13.6 kWh",
        "max_voltage":    "116.2 V",
        "model_number":   "VX156620",
        "type_of_reess":  "VX155800",
        "tac_number":     "AS8315",
        "emark":          "E11*136R01/00*0111*00",
        "energy_kwh":     "13.6 kWh",
    },
}


MODULE_VARIANT_CODES = {
    "12P": "C",
    "16P": "D",
    "24P": "E",
    "27P": "F",
}
VARIANT_BY_CODE = {v: k for k, v in MODULE_VARIANT_CODES.items()}

GROUP_CODES = {f"G{i}": str(i) for i in range(1, 7)}
GROUP_BY_CODE = {v: k for k, v in GROUP_CODES.items()}
GROUP_OPTIONS = [f"G{i}" for i in range(1, 7)]

CELL_MFR_CODES = {
    "Molical":   "1",
    "Samsung":   "2",
    "BAK":       "3",
    "EVE":       "4",
    "LG":        "5",
    "Ten Power": "6",
}
CELL_MFR_BY_CODE = {v: k for k, v in CELL_MFR_CODES.items()}
CELL_MFR_OPTIONS = list(CELL_MFR_CODES.keys())

PLANT_CODES_HV = {
    "Jigani": ("1"),
    "Domlur": ("2"),
    "TBD": ("3"),
}
PLANT_BY_CODE_HV = {
    "1": "Jigani",
    "A": "Jigani",

    "2": "Domlur",
    "B": "Domlur",

    "3": "TBD",
    "C": "TBD",
}
PLANT_OPTIONS = list(PLANT_CODES_HV.keys())

LINE_CODES = {"Line 1": "1", "Line 2": "2", "Line 3": "3"}
LINE_OPTIONS = list(LINE_CODES.keys())

SHIFT_CODES_HV = {"Shift 1": "1", "Shift 2": "2", "Shift 3": "3"}
SHIFT_OPTIONS = list(SHIFT_CODES_HV.keys())

MONTH_CODES = {
    1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F",
    7: "G", 8: "H", 9: "I", 10: "J", 11: "K", 12: "L",
}
MONTH_BY_CODE = {v: k for k, v in MONTH_CODES.items()}

def year_code(year: int) -> str:
    return str(year % 100).zfill(2)

def year_from_code(code: str) -> int:
    return 2000 + int(code)

CATEGORY_OPTIONS = ["Domestic", "Export"]

RANGE_CODES = {variant: str(i) for i, variant in enumerate(VARIANT_OPTIONS, start=1)}
RANGE_OPTIONS = list(RANGE_CODES.values())


def get_range(variant: str) -> str:
    return RANGE_CODES.get(variant.strip(), "")

BATTERY_PARAM_ROWS = [
    ("Rated Capacity", "rated_capacity", False),
    ("Max Voltage",     "max_voltage",    False),
    ("Model Number",    "model_number",   False),
    ("TAC Number",      "tac_number",     False),
    ("Serial Number",   "serial_number",  True),
]


def variants_for_category(category: str) -> list[str]:
    if category.strip().lower() == "export":
        return [v for v in VARIANT_OPTIONS if VARIANT_PARAMS[v]["emark"] != "NA"]
    return list(VARIANT_OPTIONS)


def format_pack_qr_data(*, variant: str, serial_number: str) -> str:
    reess = get_type_of_reess(variant)
    return f"{reess}:{serial_number.strip()}"


def get_model_number(variant: str) -> str:
    return VARIANT_TO_MODEL.get(variant.strip(), "")


def get_part_number(variant: str) -> str:
    return get_model_number(variant)


def get_full_model_number(variant: str, revision: str) -> str:
    part = get_part_number(variant)
    revision = (revision or "").strip().upper()
    return f"{part}-{revision}" if part and revision else part


def get_type_of_reess(variant: str) -> str:
    model = get_model_number(variant)
    return REESS_BY_MODEL.get(model, "NA")


def get_tac_number(variant: str) -> str:
    return VARIANT_PARAMS.get(variant.strip(), {}).get("tac_number", "NA")


def get_emark(variant: str) -> str:
    return VARIANT_PARAMS.get(variant.strip(), {}).get("emark", "NA")


def get_rated_capacity(variant: str) -> str:
    return VARIANT_PARAMS.get(variant.strip(), {}).get("rated_capacity", "NA")


def get_max_voltage(variant: str) -> str:
    return VARIANT_PARAMS.get(variant.strip(), {}).get("max_voltage", "NA")


def get_emark_res_code(variant: str) -> str:
    import re as _re
    raw = get_emark(variant)
    match = _re.match(r"E(\d+)\*(\d+)R(\d+)/\d+\*(\d+)\*\d+", raw)
    if not match:
        return "NA"
    _e_num, prefix, r_num, suffix = match.groups()
    return f"{prefix}RES-{r_num}{suffix}"


SRB_BY_VARIANT = {
    "12P": "SRB05",
    "16P": "SRB07",
    "24P": "SRB10",
    "27P": "SRB12",
}


def get_srb_code(variant: str) -> str:
    return SRB_BY_VARIANT.get(variant.strip(), "NA")