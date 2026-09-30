from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from server.main import _password_hash

MACHINE_HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
MIN_PASSWORD_LENGTH = 6


class ManageError(Exception):
    pass


def _connect():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ManageError("DATABASE_URL is not set.")

    try:
        import psycopg
    except ImportError as exc:
        raise ManageError(
            'Database driver is missing. Install it with: python -m pip install "psycopg[binary]"'
        ) from exc

    try:
        return psycopg.connect(database_url)
    except psycopg.Error as exc:
        raise ManageError(f"Could not connect to the database: {exc}") from exc


def _machine_hash(value: str) -> str:
    cleaned = value.strip().lower()
    if not MACHINE_HASH_PATTERN.fullmatch(cleaned):
        raise ManageError("Machine hash must be exactly 64 hexadecimal characters.")
    return cleaned


def _password_from_prompt() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ManageError("Passwords do not match.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ManageError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


def _add_device(args: argparse.Namespace) -> None:
    machine_hash = _machine_hash(args.hash)
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO devices (name, machine_hash)
            VALUES (%s, %s)
            ON CONFLICT (machine_hash)
            DO UPDATE SET name = EXCLUDED.name
            RETURNING id, name
            """,
            (args.name.strip(), machine_hash),
        )
        device_id, name = cursor.fetchone()
    print(f'Success: device "{name}" ({device_id}) is registered.')


def _list_devices(_args: argparse.Namespace) -> None:
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, machine_hash, is_active, created_at
            FROM devices
            ORDER BY name, created_at, id
            """
        )
        devices = cursor.fetchall()

    if not devices:
        print("No devices are registered.")
        return
    for device_id, name, machine_hash, is_active, created_at in devices:
        status = "enabled" if is_active else "disabled"
        print(
            f"{name or '(unnamed)'} | {status} | hash={machine_hash.strip()} "
            f"| id={device_id} | added={created_at}"
        )


def _set_device_enabled(args: argparse.Namespace, enabled: bool) -> None:
    machine_hash = _machine_hash(args.hash)
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE devices
            SET is_active = %s
            WHERE machine_hash = %s
            RETURNING name
            """,
            (enabled, machine_hash),
        )
        device = cursor.fetchone()
    if device is None:
        raise ManageError("No device has that machine hash.")
    status = "enabled" if enabled else "disabled"
    print(f'Success: device "{device[0]}" is {status}.')


def _add_user(args: argparse.Namespace) -> None:
    username = args.username.strip()
    if not username:
        raise ManageError("Username cannot be empty.")
    password = _password_from_prompt()
    salt = os.urandom(16).hex()
    password_hash = _password_hash(password, salt)

    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM devices
            WHERE is_active = TRUE
            ORDER BY created_at, id
            LIMIT 1
            """
        )
        device = cursor.fetchone()
        if device is None:
            raise ManageError("No enabled device exists; add a device before adding users.")
        cursor.execute(
            """
            INSERT INTO users (device_id, username, password_salt, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (device[0], username, salt, password_hash, args.role),
        )
        user_id = cursor.fetchone()[0]
    print(f'Success: user "{username}" ({args.role}, id={user_id}) was added.')


def _reset_password(args: argparse.Namespace) -> None:
    username = args.username.strip()
    if not username:
        raise ManageError("Username cannot be empty.")
    password = _password_from_prompt()
    salt = os.urandom(16).hex()
    password_hash = _password_hash(password, salt)

    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE users
            SET password_salt = %s, password_hash = %s
            WHERE lower(username) = lower(%s)
            RETURNING username
            """,
            (salt, password_hash, username),
        )
        user = cursor.fetchone()
    if user is None:
        raise ManageError(f'No user named "{username}" exists.')
    print(f'Success: password was reset for user "{user[0]}".')


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage HV Label Printer devices and user accounts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_device = subparsers.add_parser("add-device", help="Add a device or update its name.")
    add_device.add_argument("--name", required=True, help="Human-readable device name.")
    add_device.add_argument("--hash", required=True, help="64-character machine hash.")
    add_device.set_defaults(run=_add_device)

    list_devices = subparsers.add_parser("list-devices", help="List registered devices.")
    list_devices.set_defaults(run=_list_devices)

    disable_device = subparsers.add_parser("disable-device", help="Disable a device without deleting it.")
    disable_device.add_argument("--hash", required=True, help="64-character machine hash.")
    disable_device.set_defaults(run=lambda args: _set_device_enabled(args, False))

    enable_device = subparsers.add_parser("enable-device", help="Enable a registered device.")
    enable_device.add_argument("--hash", required=True, help="64-character machine hash.")
    enable_device.set_defaults(run=lambda args: _set_device_enabled(args, True))

    add_user = subparsers.add_parser("add-user", help="Add a user account.")
    add_user.add_argument("--username", required=True, help="New username.")
    add_user.add_argument("--role", required=True, choices=("admin", "operator"))
    add_user.set_defaults(run=_add_user)

    reset_password = subparsers.add_parser("reset-password", help="Reset a user's password.")
    reset_password.add_argument("--username", required=True, help="Account username.")
    reset_password.set_defaults(run=_reset_password)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        args.run(args)
        return 0
    except ManageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        try:
            import psycopg
        except ImportError:
            print(f"Error: {exc}", file=sys.stderr)
        else:
            if isinstance(exc, psycopg.Error):
                print(f"Database error: {exc}", file=sys.stderr)
            else:
                print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
