from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.api_client import APIClientError, get_all, patch, post

SHEET_NAME = "HV Dummy"


@dataclass
class ScanRecord:
    date: str = ""
    time: str = ""
    serial_count: str = ""
    ref_no: str = ""
    variant: str = ""
    m1: str = ""
    m2: str = ""
    m3: str = ""
    m4: str = ""
    dummy_pack_status: str = ""
    dummy_pack_qr: str = ""
    serial_number: str = ""
    issue_desc_1: str = ""
    issue_desc_2: str = ""
    action_plan: str = ""
    remark: str = ""
    admin_ack: str = ""
    id: str = ""
    sl_no: int | None = None

    @property
    def has_issue(self) -> bool:
        return bool(self.issue_desc_1.strip() or self.issue_desc_2.strip())

    @property
    def is_unacknowledged(self) -> bool:
        return self.has_issue and not self.admin_ack.strip()

    def as_row(self, sl_no: int) -> list:
        return [
            sl_no, self.date, self.time, self.serial_count, self.serial_number,
            self.ref_no, self.variant, self.m1, self.m2, self.m3, self.m4,
            self.dummy_pack_status, self.dummy_pack_qr, self.issue_desc_1,
            self.issue_desc_2, self.action_plan, self.remark, self.admin_ack,
        ]


def _from_api(data: dict[str, Any]) -> ScanRecord:
    return ScanRecord(
        date=str(data.get("date") or ""),
        time=str(data.get("time") or ""),
        serial_count=str(data.get("serial_count") or ""),
        ref_no=str(data.get("ref_no") or ""),
        variant=str(data.get("variant") or ""),
        m1=str(data.get("m1") or ""),
        m2=str(data.get("m2") or ""),
        m3=str(data.get("m3") or ""),
        m4=str(data.get("m4") or ""),
        dummy_pack_status=str(data.get("dummy_pack_status") or ""),
        dummy_pack_qr=str(data.get("dummy_pack_qr") or ""),
        serial_number=str(data.get("serial_number") or ""),
        issue_desc_1=str(data.get("issue_desc_1") or ""),
        issue_desc_2=str(data.get("issue_desc_2") or ""),
        action_plan=str(data.get("action_plan") or ""),
        remark=str(data.get("remark") or ""),
        admin_ack=str(data.get("admin_ack") or ""),
        id=str(data.get("id") or ""),
        sl_no=data.get("sl_no"),
    )


def append_scan_record(record: ScanRecord) -> str:
    response = post(
        "/logs/dummy",
        {
            "date": record.date,
            "time": record.time,
            "serial_count": record.serial_count,
            "serial_number": record.serial_number,
            "ref_no": record.ref_no,
            "variant": record.variant,
            "m1": record.m1,
            "m2": record.m2,
            "m3": record.m3,
            "m4": record.m4,
            "dummy_pack_status": record.dummy_pack_status,
            "dummy_pack_qr": record.dummy_pack_qr,
            "issue_desc_1": record.issue_desc_1,
            "issue_desc_2": record.issue_desc_2,
            "action_plan": record.action_plan,
            "remark": record.remark,
            "admin_ack": record.admin_ack,
        },
    )
    record.id = str(response.get("id") or "")
    record.sl_no = response.get("sl_no")
    if not record.id:
        raise APIClientError("Server saved the dummy log without returning its database id.")
    return record.id


def load_all_records_with_rows() -> list[tuple[str, ScanRecord]]:
    records = get_all("/logs/dummy")
    return [(str(row.get("id") or ""), _from_api(row)) for row in records]


def load_all_records() -> list[ScanRecord]:
    return [record for _record_id, record in load_all_records_with_rows()]


def load_unacknowledged_issues() -> list[tuple[str, ScanRecord]]:
    return [
        (record_id, record)
        for record_id, record in load_all_records_with_rows()
        if record.is_unacknowledged
    ]


def patch_admin_ack(record_id: str, ack_text: str) -> bool:
    try:
        patch(f"/logs/dummy/{record_id}", {"admin_ack": ack_text})
        return True
    except APIClientError as exc:
        if exc.status_code == 404:
            return False
        raise


def add_sheet(sheet_name: str) -> tuple[bool, str]:
    return False, "Additional log sheets are not supported by the server."


def open_log_file() -> None:
    raise APIClientError("Scan logs are stored on the server, not in a local Excel file.")
