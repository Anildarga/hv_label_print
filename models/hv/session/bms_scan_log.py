from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.api_client import APIClientError, get_all, patch, post

SHEET_NAME = "bmb_cmb"


@dataclass
class BmsScanRecord:
    date: str = ""
    time: str = ""
    pack_qr_data: str = ""
    bmb_id: str = ""
    cmb_id: str = ""
    rework_bmb_id: str = ""
    rework_cmb_id: str = ""
    id: str = ""
    sl_no: int | None = None

    @property
    def is_reworked(self) -> bool:
        return bool(self.rework_bmb_id.strip() or self.rework_cmb_id.strip())

    def as_row(self, sl_no: int) -> list:
        return [
            sl_no, self.date, self.time, self.pack_qr_data, self.bmb_id,
            self.cmb_id, self.rework_bmb_id, self.rework_cmb_id,
        ]


def _from_api(data: dict[str, Any]) -> BmsScanRecord:
    return BmsScanRecord(
        date=str(data.get("date") or ""),
        time=str(data.get("time") or ""),
        pack_qr_data=str(data.get("pack_qr_data") or ""),
        bmb_id=str(data.get("bmb_id") or ""),
        cmb_id=str(data.get("cmb_id") or ""),
        rework_bmb_id=str(data.get("rework_bmb_id") or ""),
        rework_cmb_id=str(data.get("rework_cmb_id") or ""),
        id=str(data.get("id") or ""),
        sl_no=data.get("sl_no"),
    )


def append_scan_record(record: BmsScanRecord) -> str:
    response = post(
        "/logs/bms",
        {
            "date": record.date,
            "time": record.time,
            "pack_qr_data": record.pack_qr_data,
            "bmb_id": record.bmb_id,
            "cmb_id": record.cmb_id,
            "rework_bmb_id": record.rework_bmb_id,
            "rework_cmb_id": record.rework_cmb_id,
        },
    )
    record.id = str(response.get("id") or "")
    record.sl_no = response.get("sl_no")
    if not record.id:
        raise APIClientError("Server saved the BMS log without returning its database id.")
    return record.id


def load_all_records_with_rows() -> list[tuple[str, BmsScanRecord]]:
    return [
        (str(row.get("id") or ""), _from_api(row))
        for row in get_all("/logs/bms")
    ]


def load_all_records() -> list[BmsScanRecord]:
    return [record for _record_id, record in load_all_records_with_rows()]


def patch_rework(
    pack_qr_data: str, kind: str, value: str
) -> bool:
    if not pack_qr_data.strip():
        return False
    if kind.upper() not in {"BMB", "CMB"}:
        raise ValueError("Rework kind must be BMB or CMB.")
    record = find_record_by_pack_qr(pack_qr_data)
    if record is None or not record.id:
        return False
    column = "rework_bmb_id" if kind.upper() == "BMB" else "rework_cmb_id"
    try:
        patch(f"/logs/bms/{record.id}/rework", {column: value})
        return True
    except APIClientError as exc:
        if exc.status_code == 404:
            return False
        raise


def find_record_by_pack_qr(pack_qr_data: str) -> BmsScanRecord | None:
    target = pack_qr_data.strip()
    if not target:
        return None
    return next(
        (
            record
            for _record_id, record in load_all_records_with_rows()
            if record.pack_qr_data.strip() == target
        ),
        None,
    )


def load_rework_records() -> list[tuple[str, BmsScanRecord]]:
    return [
        (record_id, record)
        for record_id, record in load_all_records_with_rows()
        if record.is_reworked
    ]


def open_log_file() -> None:
    raise APIClientError("BMS logs are stored on the server, not in a local Excel file.")
