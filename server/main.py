from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import contextmanager
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation

from common.nomenclature.serial_number import build_serial_number, parse_serial_number

app = FastAPI(title="HV Label Printer API", version="1.0.0")

TOKEN_TTL_SECONDS = 8 * 60 * 60
SERIAL_COUNTER_LOCK_ID = 791204610
LOG_TABLES = {
    "dummy": (
        "dummy_log",
        (
            "sl_no", "date", "time", "serial_count", "serial_number", "ref_no",
            "variant", "m1", "m2", "m3", "m4", "dummy_pack_status",
            "dummy_pack_qr", "issue_desc_1", "issue_desc_2", "action_plan",
            "remark", "admin_ack",
        ),
    ),
    "pack-id": (
        "pack_id_log",
        ("sl_no", "date", "time", "serial_number", "variant", "pack_qr_data"),
    ),
    "bms": (
        "bms_log",
        (
            "sl_no", "date", "time", "pack_qr_data", "bmb_id", "cmb_id",
            "rework_bmb_id", "rework_cmb_id",
        ),
    ),
}


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class NewUser(Credentials):
    role: str = "operator"


class DummyLogRecord(BaseModel):
    sl_no: int | None = None
    date: str = ""
    time: str = ""
    serial_count: str = ""
    serial_number: str = ""
    ref_no: str = ""
    variant: str = ""
    m1: str = ""
    m2: str = ""
    m3: str = ""
    m4: str = ""
    dummy_pack_status: str = ""
    dummy_pack_qr: str = ""
    issue_desc_1: str = ""
    issue_desc_2: str = ""
    action_plan: str = ""
    remark: str = ""
    admin_ack: str = ""


class DummyLogPatch(BaseModel):
    ref_no: str | None = None
    serial_count: str | None = None
    issue_desc_1: str | None = None
    issue_desc_2: str | None = None
    action_plan: str | None = None
    remark: str | None = None
    admin_ack: str | None = None


class PackIdLogRecord(BaseModel):
    sl_no: int | None = None
    date: str = ""
    time: str = ""
    serial_number: str = ""
    variant: str = ""
    pack_qr_data: str = ""


class PackIdLogPatch(BaseModel):
    serial_number: str | None = None
    variant: str | None = None
    pack_qr_data: str | None = None


class BmsLogRecord(BaseModel):
    sl_no: int | None = None
    date: str = ""
    time: str = ""
    pack_qr_data: str = ""
    bmb_id: str = ""
    cmb_id: str = ""
    rework_bmb_id: str = ""
    rework_cmb_id: str = ""


class BmsReworkPatch(BaseModel):
    rework_bmb_id: str | None = None
    rework_cmb_id: str | None = None


class SerialAllocation(BaseModel):
    current_serial: str = Field(min_length=1, max_length=64)


class SerialUpdate(BaseModel):
    serial_number: str = Field(min_length=1, max_length=64)


@contextmanager
def _connection():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Install the server dependencies") from exc

    try:
        connection = psycopg.connect(database_url, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        raise HTTPException(status_code=503, detail="Database operation failed") from exc
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _require_device(x_machine_hash: str = Header(..., alias="X-Machine-Hash")) -> dict[str, Any]:
    machine_hash = x_machine_hash.strip().lower()
    if len(machine_hash) != 64 or any(c not in "0123456789abcdef" for c in machine_hash):
        raise HTTPException(status_code=403, detail="Unauthorized device")

    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name
            FROM devices
            WHERE machine_hash = %s AND is_active = TRUE
            """,
            (machine_hash,),
        )
        device = cursor.fetchone()
    if device is None:
        raise HTTPException(status_code=403, detail="Unauthorized device")
    return device


def _token_secret() -> bytes:
    secret = os.getenv("AUTH_TOKEN_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="AUTH_TOKEN_SECRET must contain at least 32 characters",
        )
    return secret.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _issue_token(username: str, device_id: UUID) -> str:
    claims = {
        "sub": username,
        "role": "admin",
        "device_id": str(device_id),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    payload = _b64encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_token_secret(), payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{_b64encode(signature)}"


def _read_token(token: str) -> dict[str, Any]:
    try:
        payload, encoded_signature = token.split(".", 1)
        signature = _b64decode(encoded_signature)
        expected = hmac.new(
            _token_secret(), payload.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        claims = json.loads(_b64decode(payload))
        if int(claims["exp"]) <= int(time.time()):
            raise ValueError("Expired token")
        return claims
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token") from exc


def _require_admin(
    authorization: str = Header(...),
    device: dict[str, Any] = Depends(_require_device),
) -> dict[str, Any]:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Admin bearer token required")
    claims = _read_token(token)
    if claims.get("device_id") != str(device["id"]):
        raise HTTPException(status_code=403, detail="Token is not valid for this device")
    username = claims.get("sub")
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, role FROM users WHERE username = %s",
            (username,),
        )
        user = cursor.fetchone()
    if user is None or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"id": user["id"], "username": username, "device": device}


def _password_hash(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _insert_log(
    table_key: str,
    values: dict[str, Any],
    device: dict[str, Any],
) -> dict[str, Any]:
    table, columns = LOG_TABLES[table_key]
    fields = tuple(
        column for column in columns
        if not (column == "sl_no" and values[column] is None)
    )
    insert_columns = ("device_id", *fields)
    placeholders = ", ".join(["%s"] * len(insert_columns))
    column_sql = ", ".join(insert_columns)
    params = (device["id"], *(values[column] for column in fields))
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) RETURNING *",
                params,
            )
            record = cursor.fetchone()
        return record
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Duplicate identifier") from exc


def _list_log(table_key: str, limit: int, offset: int) -> list[dict[str, Any]]:
    table, _columns = LOG_TABLES[table_key]
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"SELECT * FROM {table} ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return list(cursor.fetchall())


def _patch_log(
    table_key: str,
    record_id: UUID,
    changes: dict[str, Any],
) -> dict[str, Any]:
    table, columns = LOG_TABLES[table_key]
    allowed = set(columns)
    changes = {key: value for key, value in changes.items() if key in allowed}
    if not changes:
        raise HTTPException(status_code=400, detail="No patchable fields supplied")
    assignments = ", ".join(f"{column} = %s" for column in changes)
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET {assignments} WHERE id = %s RETURNING *",
                (*changes.values(), record_id),
            )
            record = cursor.fetchone()
        if record is None:
            raise HTTPException(status_code=404, detail="Log record not found")
        return record
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Duplicate identifier") from exc


@app.get("/devices/check")
def check_device(device: dict[str, Any] = Depends(_require_device)) -> dict[str, Any]:
    return {"authorized": True, "device_id": device["id"], "name": device["name"]}


@app.get("/serial/current")
def get_current_serial(
    device: dict[str, Any] = Depends(_require_device),
) -> dict[str, str]:
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT serial_number, serial_count
            FROM serial_counter
            ORDER BY created_at, id
            LIMIT 1
            """
        )
        row = cursor.fetchone()
    if row is None:
        return {"serial_number": "", "serial_count": ""}
    return {"serial_number": row["serial_number"], "serial_count": row["serial_count"]}


@app.put("/serial/current")
def set_current_serial(
    request: SerialUpdate,
    device: dict[str, Any] = Depends(_require_device),
) -> dict[str, str]:
    parsed = parse_serial_number(request.serial_number)
    if parsed is None:
        raise HTTPException(status_code=422, detail="Invalid serial_number")
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (SERIAL_COUNTER_LOCK_ID,))
            cursor.execute(
                """
                SELECT id FROM serial_counter
                ORDER BY created_at, id
                LIMIT 1 FOR UPDATE
                """
            )
            current = cursor.fetchone()
            if current is None:
                cursor.execute(
                    """
                    INSERT INTO serial_counter (device_id, serial_number, serial_count)
                    VALUES (%s, %s, %s)
                    RETURNING serial_number, serial_count
                    """,
                    (device["id"], parsed.raw, parsed.serial_count),
                )
                row = cursor.fetchone()
            else:
                cursor.execute(
                    """
                    UPDATE serial_counter
                    SET serial_number = %s, serial_count = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING serial_number, serial_count
                    """,
                    (parsed.raw, parsed.serial_count, current["id"]),
                )
                row = cursor.fetchone()
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Serial number already allocated") from exc
    return {"serial_number": row["serial_number"], "serial_count": row["serial_count"]}


@app.post("/serial/allocate")
def allocate_serial(
    request: SerialAllocation,
    device: dict[str, Any] = Depends(_require_device),
) -> dict[str, str]:
    parsed_seed = parse_serial_number(request.current_serial)
    if parsed_seed is None:
        raise HTTPException(status_code=422, detail="Invalid current_serial")

    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (SERIAL_COUNTER_LOCK_ID,))
            cursor.execute(
                """
                SELECT id, serial_number
                FROM serial_counter
                ORDER BY created_at, id
                LIMIT 1 FOR UPDATE
                """
            )
            stored = cursor.fetchone()
            if stored is None:
                cursor.execute(
                    """
                    INSERT INTO serial_counter (device_id, serial_number, serial_count)
                    VALUES (%s, %s, %s)
                    RETURNING id, serial_number
                    """,
                    (device["id"], parsed_seed.raw, parsed_seed.serial_count),
                )
                stored = cursor.fetchone()
            current = parse_serial_number(stored["serial_number"])
            if current is None:
                raise HTTPException(status_code=409, detail="Stored serial number is invalid")

            count = int(current.serial_count) + 1
            width = 5 if current.is_new_format else 6
            if count >= 10**width:
                raise HTTPException(
                    status_code=409,
                    detail="Serial counter exhausted; initialize a new series",
                )
            next_serial = build_serial_number(
                plant=current.plant,
                line=current.line,
                when=date(current.year, current.month, current.day),
                serial_count=str(count).zfill(width),
                model=current.model,
                variant=current.variant,
                shift=current.shift,
                category=current.category,
            )
            cursor.execute(
                """
                UPDATE serial_counter
                SET serial_number = %s, serial_count = %s, updated_at = now()
                WHERE id = %s
                """,
                (next_serial, str(count).zfill(width), stored["id"]),
            )
    except HTTPException:
        raise
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Serial number already allocated") from exc
    return {"serial_number": next_serial, "serial_count": str(count).zfill(width)}


@app.post("/logs/dummy", status_code=201)
def append_dummy_log(
    record: DummyLogRecord,
    device: dict[str, Any] = Depends(_require_device),
) -> dict[str, Any]:
    return _insert_log("dummy", record.model_dump(), device)


@app.get("/logs/dummy")
def list_dummy_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _device: dict[str, Any] = Depends(_require_device),
) -> list[dict[str, Any]]:
    return _list_log("dummy", limit, offset)


@app.patch("/logs/dummy/{record_id}")
def patch_dummy_log(
    record_id: UUID,
    patch: DummyLogPatch,
    _admin: dict[str, Any] = Depends(_require_admin),
) -> dict[str, Any]:
    return _patch_log("dummy", record_id, patch.model_dump(exclude_unset=True))


@app.post("/logs/pack-id", status_code=201)
def append_pack_id_log(
    record: PackIdLogRecord,
    device: dict[str, Any] = Depends(_require_device),
) -> dict[str, Any]:
    return _insert_log("pack-id", record.model_dump(), device)


@app.get("/logs/pack-id")
def list_pack_id_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _device: dict[str, Any] = Depends(_require_device),
) -> list[dict[str, Any]]:
    return _list_log("pack-id", limit, offset)


@app.patch("/logs/pack-id/{record_id}")
def patch_pack_id_log(
    record_id: UUID,
    patch: PackIdLogPatch,
    _admin: dict[str, Any] = Depends(_require_admin),
) -> dict[str, Any]:
    return _patch_log("pack-id", record_id, patch.model_dump(exclude_unset=True))


@app.post("/logs/bms", status_code=201)
def append_bms_log(
    record: BmsLogRecord,
    device: dict[str, Any] = Depends(_require_device),
) -> dict[str, Any]:
    return _insert_log("bms", record.model_dump(), device)


@app.get("/logs/bms")
def list_bms_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _device: dict[str, Any] = Depends(_require_device),
) -> list[dict[str, Any]]:
    return _list_log("bms", limit, offset)


@app.patch("/logs/bms/{record_id}/rework")
def patch_bms_rework(
    record_id: UUID,
    patch: BmsReworkPatch,
    _device: dict[str, Any] = Depends(_require_device),
) -> dict[str, Any]:
    return _patch_log("bms", record_id, patch.model_dump(exclude_unset=True))


@app.post("/users/authenticate")
def authenticate_user(
    credentials: Credentials,
    device: dict[str, Any] = Depends(_require_device),
) -> dict[str, Any]:
    username = credentials.username.strip()
    password = credentials.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT username, password_salt, password_hash, role
            FROM users WHERE lower(username) = lower(%s)
            """,
            (username,),
        )
        user = cursor.fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    actual = _password_hash(password, user["password_salt"])
    if not hmac.compare_digest(actual, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    username = user["username"]
    token = _issue_token(username, device["id"]) if user["role"] == "admin" else None
    return {
        "username": username,
        "role": user["role"],
        "access_token": token,
        "token_type": "bearer" if token else None,
        "expires_in": TOKEN_TTL_SECONDS if token else None,
    }


@app.get("/users")
def list_users(
    _admin: dict[str, Any] = Depends(_require_admin),
) -> list[dict[str, Any]]:
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, username, role, device_id, created_at FROM users ORDER BY lower(username)"
        )
        return list(cursor.fetchall())


@app.post("/users", status_code=201)
def add_user(
    request: NewUser,
    admin: dict[str, Any] = Depends(_require_admin),
) -> dict[str, Any]:
    username = request.username.strip()
    password = request.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if len(password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
    if request.role not in {"admin", "operator"}:
        raise HTTPException(status_code=422, detail="Invalid role")

    salt = secrets.token_hex(16)
    password_hash = _password_hash(password, salt)
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (device_id, username, password_salt, password_hash, role)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, username, role, device_id, created_at
                """,
                (admin["device"]["id"], username, salt, password_hash, request.role),
            )
            return cursor.fetchone()
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Username already exists") from exc


@app.delete("/users/{user_id}")
def delete_user(
    user_id: UUID,
    admin: dict[str, Any] = Depends(_require_admin),
) -> dict[str, str]:
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(791204613)")
        cursor.execute("SELECT username, role FROM users WHERE id = %s FOR UPDATE", (user_id,))
        target = cursor.fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")
        if target["username"] == admin["username"]:
            raise HTTPException(
                status_code=409,
                detail="You cannot delete the account you're currently logged in as",
            )
        if target["role"] == "admin":
            cursor.execute("SELECT count(*) AS count FROM users WHERE role = 'admin'")
            if cursor.fetchone()["count"] <= 1:
                raise HTTPException(status_code=409, detail="At least one admin account must remain")
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    return {"deleted": target["username"]}
