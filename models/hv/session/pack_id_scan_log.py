from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.api_client import APIClientError, get_all, post

SHEET_NAME = "Pack ID"


@dataclass
class PackIdScanRecord:
    date: str = ""
    time: str = ""
    serial_number: str = ""
    variant: str = ""
    pack_qr_data: str = ""
    id: str = ""
    sl_no: int | None = None

    def as_row(self, sl_no: int) -> list:
        return [
            sl_no, self.date, self.time, self.serial_number,
            self.variant, self.pack_qr_data,
        ]


def _from_api(data: dict[str, Any]) -> PackIdScanRecord:
    return PackIdScanRecord(
        date=str(data.get("date") or ""),
        time=str(data.get("time") or ""),
        serial_number=str(data.get("serial_number") or ""),
        variant=str(data.get("variant") or ""),
        pack_qr_data=str(data.get("pack_qr_data") or ""),
        id=str(data.get("id") or ""),
        sl_no=data.get("sl_no"),
    )


def append_scan_record(record: PackIdScanRecord) -> str:
    response = post(
        "/logs/pack-id",
        {
            "date": record.date,
            "time": record.time,
            "serial_number": record.serial_number,
            "variant": record.variant,
            "pack_qr_data": record.pack_qr_data,
        },
    )
    record.id = str(response.get("id") or "")
    record.sl_no = response.get("sl_no")
    if not record.id:
        raise APIClientError("Server saved the pack ID log without returning its database id.")
    return record.id


def load_all_records() -> list[PackIdScanRecord]:
    return [_from_api(row) for row in get_all("/logs/pack-id")]


def open_log_file() -> None:
    raise APIClientError("Pack ID logs are stored on the server, not in a local Excel file.")
