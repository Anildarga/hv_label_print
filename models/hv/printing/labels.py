from __future__ import annotations

from models.hv.gui.constants import (
    get_emark,
    get_emark_res_code,
    get_rated_capacity,
    get_srb_code,
    get_tac_number,
    get_type_of_reess,
)
from models.hv.printing.zpl import (
    build_battery_pack_id_zpl_unified,
    build_bmb_cmb_combined_zpl,
    build_bmb_cmb_zpl,
    build_bms_id_zpl,
    build_hv_module_label_domestic,
    build_hv_module_label_export,
    build_hv_pack_label_domestic,
    build_hv_pack_label_export,
    build_pack_qr_zpl,
)


def build_hv_module_label(
    *,
    full_module_id: str,
    variant: str,
    model_number: str,
    mfg_date: str,
    mfg_year: str,
    category: str,
) -> str:
    is_export = category.strip().lower() == "export"
    params = dict(
        full_module_id=full_module_id,
        variant=variant,
        model_number=model_number,
        type_of_reess=get_type_of_reess(variant),
        rated_capacity=get_rated_capacity(variant),
    )
    if is_export:
        return build_hv_module_label_export(
            emark=get_emark(variant),
            mfg_year=mfg_year,
            **params,
        )
    return build_hv_module_label_domestic(
        tac_number=get_tac_number(variant),
        mfg_date=mfg_date,
        **params,
    )


def build_hv_pack_label(
    *,
    module_id: str,
    variant: str,
    model_number: str,
    mfg_date: str,
    mfg_year: str,
    category: str,
) -> str:
    is_export = category.strip().lower() == "export"
    params = dict(
        module_id=module_id,
        variant=variant,
        model_number=model_number,
        type_of_reess=get_type_of_reess(variant),
        rated_capacity=get_rated_capacity(variant),
    )
    if is_export:
        return build_hv_pack_label_export(
            emark=get_emark(variant),
            mfg_year=mfg_year,
            **params,
        )
    return build_hv_pack_label_domestic(
        tac_number=get_tac_number(variant),
        mfg_date=mfg_date,
        **params,
    )


def build_pack_qr_label(
    *,
    pack_qr_data: str,
    model_number: str,
    serial_number: str,
    tac_number: str,
    mfg_date: str,
    variant: str = "",
    category: str = "Domestic",
) -> str:
    is_export = category.strip().lower() == "export"
    value = get_emark(variant) if (is_export and variant) else tac_number
    tac_label = "E-Marking No" if (is_export and variant) else "TAC Number"
    return build_pack_qr_zpl(
        pack_qr_data=pack_qr_data,
        model_number=model_number,
        serial_number=serial_number,
        tac_number=value,
        tac_label=tac_label,
        mfg_date=mfg_date,
    )


def build_bmb_cmb_combined_label(*, bmb_serial: str, cmb_serial: str, pack_qr_data: str = "") -> str:
    return build_bmb_cmb_combined_zpl(bmb_serial=bmb_serial, cmb_serial=cmb_serial, pack_qr_data=pack_qr_data)


def build_bmb_cmb_label(*, kind: str, value: str, pack_qr_data: str = "") -> str:
    return build_bmb_cmb_zpl(kind=kind, value=value, pack_qr_data=pack_qr_data)


def build_bms_id_label(*, bms_id: str, pack_qr_data: str = "") -> str:
    return build_bms_id_zpl(bms_id=bms_id, pack_qr_data=pack_qr_data)


def _emark_res(variant: str) -> str:
    full = get_emark(variant)
    if not full or "*" not in full:
        return full
    return full.split("*", 1)[1]


def build_battery_pack_id_label(
    *,
    serial_number: str,
    rated_capacity: str,
    max_voltage: str,
    model_number: str,
    tac_number: str,
    variant: str,
    category: str,
    mfg_date: str,
    pack_qr_data: str = "",
    made_in: str = "India",
) -> str:
   
    qr_data = pack_qr_data or serial_number
    mfg_year = mfg_date[-4:] if len(mfg_date) >= 4 else mfg_date
    return build_battery_pack_id_zpl_unified(
        rated_capacity=rated_capacity,
        max_voltage=max_voltage,
        type_of_reess=get_type_of_reess(variant),
        serial_number=serial_number,
        tac_number=tac_number or get_tac_number(variant),
        emark_res=get_emark_res_code(variant),
        srb_code=get_srb_code(variant),
        made_in=made_in,
        mfg_year=mfg_year,
        qr_data=qr_data,
    )


def build_scanned_module_label(*, full_module_id: str, variant: str, category: str) -> str:
    return build_hv_module_label(
        full_module_id=full_module_id,
        variant=variant,
        model_number=get_model_number_for_label(variant),
        mfg_date="",
        mfg_year="",
        category=category,
    )


def get_model_number_for_label(variant: str) -> str:
    from models.hv.gui.constants import get_model_number
    return get_model_number(variant)