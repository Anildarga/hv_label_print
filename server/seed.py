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
DATABASE_URL_ENV = "DATABASE_URL"


class SeedError(Exception):
    pass


def _parse_device(value: str) -> tuple[str, str]:
    name, separator, machine_hash = value.partition("=")
    name = name.strip()
    machine_hash = machine_hash.strip().lower()
    if not separator or not name:
        raise argparse.ArgumentTypeError(
            "Device must be written as NAME=64-character-machine-hash."
        )
    if not MACHINE_HASH_PATTERN.fullmatch(machine_hash):
        raise argparse.ArgumentTypeError("Machine hash must be 64 hexadecimal characters.")
    return name, machine_hash


def _read_password() -> str:
    password = getpass.getpass("Initial admin password: ").strip()
    confirmation = getpass.getpass("Confirm admin password: ").strip()
    if password != confirmation:
        raise SeedError("Passwords do not match.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SeedError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


def seed(devices: list[tuple[str, str]], username: str, password: str) -> None:
    database_url = os.getenv(DATABASE_URL_ENV, "").strip()
    if not database_url:
        raise SeedError(
            f"{DATABASE_URL_ENV} is not set; configure it with your PostgreSQL credentials."
        )

    try:
        import psycopg
    except ImportError as exc:
        raise SeedError(
            'Database driver is missing. Install it with: python -m pip install "psycopg[binary]"'
        ) from exc

    try:
        with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
            device_ids: list[tuple[str, str]] = []
            for name, machine_hash in devices:
                cursor.execute(
                    """
                    INSERT INTO devices (name, machine_hash, is_active)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (machine_hash)
                    DO UPDATE SET name = EXCLUDED.name, is_active = TRUE
                    RETURNING id
                    """,
                    (name, machine_hash),
                )
                device_ids.append((machine_hash, str(cursor.fetchone()[0])))

            cursor.execute(
                "SELECT 1 FROM users WHERE lower(username) = lower(%s)",
                (username,),
            )
            if cursor.fetchone() is not None:
                raise SeedError(
                    f'User "{username}" already exists; no password was changed.'
                )

            salt = os.urandom(16).hex()
            digest = _password_hash(password, salt)
            cursor.execute(
                """
                INSERT INTO users (device_id, username, password_salt, password_hash, role)
                VALUES (%s, %s, %s, %s, 'admin')
                RETURNING id
                """,
                (device_ids[0][1], username, salt, digest),
            )
            user_id = cursor.fetchone()[0]
    except SeedError:
        raise
    except Exception as exc:
        try:
            import psycopg
        except ImportError:
            raise SeedError(f"Database setup failed: {exc}") from exc
        if isinstance(exc, psycopg.Error):
            raise SeedError(f"Database setup failed: {exc}") from exc
        raise

    print(f'Success: {len(device_ids)} device(s) registered and enabled.')
    print(f'Success: initial admin "{username}" (id={user_id}) created.')


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed authorized devices and the initial admin account."
    )
    parser.add_argument(
        "--device",
        action="append",
        type=_parse_device,
        required=True,
        metavar="NAME=HASH",
        help="Device name and 64-character machine hash; repeat for each device.",
    )
    parser.add_argument("--admin-username", required=True, help="Initial admin username.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    username = args.admin_username.strip()
    if not username:
        print("Error: admin username cannot be empty.", file=sys.stderr)
        return 1
    if len({machine_hash for _name, machine_hash in args.device}) != len(args.device):
        print("Error: duplicate machine hashes were supplied.", file=sys.stderr)
        return 1

    try:
        password = _read_password()
        seed(args.device, username, password)
        return 0
    except SeedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
