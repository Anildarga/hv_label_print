# HV Label Printer API

FastAPI/PostgreSQL service for shared device authorization, serial allocation,
user administration, and the three production scan logs.

## Requirements

- Windows 10/11
- Python 3.10+
- PostgreSQL 13+

## Create the database

Install PostgreSQL and create a database and login, for example:

```powershell
psql -U postgres
```

At the `psql` prompt:

```sql
CREATE ROLE hv_app WITH LOGIN PASSWORD '<your-database-password>';
CREATE DATABASE hvlabel OWNER hv_app;
\q
```

Apply the schema from the repository root:

```powershell
psql "postgresql://hv_app:<your-database-password>@localhost:5432/hvlabel" -f server\schema.sql
```

Register authorized workstations and create the first admin with the
`server\seed.py` command described below. The machine hash is produced by the
desktop app's `common.auth.machine_lock.get_machine_hash()`.
Set the `DATABASE_URL` environment variable to
`postgresql://hv_app:<your-database-password>@localhost:5432/hvlabel` before
running the server or administrative scripts. Replace the password placeholder
locally; do not commit or print the real password. URL-encode special
characters in the password when placing it in a connection URI.

## Install and run on Windows

From the repository root, create and activate a virtual environment, then
install the server dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install fastapi "uvicorn[standard]" "psycopg[binary]"
```

Set the database connection string and a private token-signing secret of at
least 32 characters. Keep both values outside source control:

```powershell
$env:DATABASE_URL = "postgresql://hv_app:<your-database-password>@localhost:5432/hvlabel"
$env:AUTH_TOKEN_SECRET = "replace-with-a-random-secret-at-least-32-characters"
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

For a server reachable by other production workstations, bind to the
appropriate private interface instead of `127.0.0.1` and protect traffic with
TLS at a trusted reverse proxy or network gateway. Do not expose this service
or PostgreSQL directly to the public internet. Each API request, including
authentication, must include the `X-Machine-Hash` header. Admin operations
also require the bearer token returned when an admin authenticates.

## API

| Method | Path | Access |
| --- | --- | --- |
| `GET` | `/devices/check` | Authorized device |
| `GET`, `PUT` | `/serial/current` | Authorized device |
| `POST` | `/serial/allocate` | Authorized device |
| `POST`, `GET` | `/logs/dummy` | Authorized device |
| `PATCH` | `/logs/dummy/{record_id}` | Admin |
| `POST`, `GET` | `/logs/pack-id` | Authorized device |
| `PATCH` | `/logs/pack-id/{record_id}` | Admin |
| `POST`, `GET` | `/logs/bms` | Authorized device |
| `PATCH` | `/logs/bms/{record_id}/rework` | Authorized device |
| `POST` | `/users/authenticate` | Authorized device |
| `GET`, `POST` | `/users` | Admin |
| `DELETE` | `/users/{user_id}` | Admin |

List endpoints accept `limit` (1–500, default 100) and `offset` query
parameters and return records newest first. `sl_no` is retained for Excel
compatibility and is assigned automatically when omitted; the UUID `id` is
the stable API identifier. Empty identifier fields are not treated as
duplicates. Unique indexes and database triggers reject duplicate
case-insensitive pack serial, module, BMB, or CMB IDs.

Serial allocation accepts `{"current_serial": "<last allocated or seed serial>"}`.
The first request seeds the shared counter from that value; each request then
increments and stores the next serial in a transaction, returning
`{"serial_number": "...", "serial_count": "..."}`. Later requests use the
database counter as authoritative, so a stale client value cannot roll the
counter back. The counter is shared by all authorized devices. A `409` response
indicates a duplicate or an exhausted counter.

## Configure desktop clients

The desktop app requires `requests` in its Python environment. Set the API URL
in `common\api_config.json` (`server_url`) to the server's reachable private
address, for example `http://192.168.1.20:8000`, or set the
`HV_LABEL_SERVER_URL` environment variable. The environment variable takes
precedence. The default `http://127.0.0.1:8000` is suitable only when the
server runs on the same PC. For packaged Windows builds, update the bundled
`common\api_config.json` or set the environment variable on the workstation.

FastAPI's interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## Managing devices and users

Run the management commands from the repository root in the same activated
environment used for the server. They use `DATABASE_URL` and the `devices`
and `users` tables created by `schema.sql`. Passwords are requested twice
with hidden input; they are never command-line arguments or printed. Password
hashes use the same salted SHA-256 format as `server/main.py`.

```powershell
# Register a new production PC. Safe to repeat: an existing hash only updates its name.
python server\manage.py add-device --name "Main PC" --hash <machine_hash>

# Review all registered devices and their enabled/disabled state.
python server\manage.py list-devices

# Disable a PC without deleting it or affecting log rows linked to it.
python server\manage.py disable-device --hash <machine_hash>

# Re-enable a previously registered PC.
python server\manage.py enable-device --hash <machine_hash>

# Add a user; enter and confirm the password at the hidden prompts.
python server\manage.py add-user --username <name> --role admin
python server\manage.py add-user --username <name> --role operator

# Reset an existing user's password using hidden prompts.
python server\manage.py reset-password --username <name>
```

When adding a user, the account's `device_id` is associated with the first
enabled device in the database (ordered by creation time). Add at least one
device first. To authorize another PC later, obtain that PC's hash with
`common.auth.machine_lock.get_machine_hash()`, then run `add-device` with a
descriptive name and that hash. Use `list-devices` to check it, and
`disable-device`/`enable-device` to revoke/restore access. These commands
change `devices.is_active`, the authorization flag used by the API; they do
not delete device records.

## Initial database seed

Use `seed.py` once to register one or more authorized devices and create the
first admin account. It reads `DATABASE_URL`, enables or updates each supplied
device hash, and associates the admin with the first device in the command.
The password is entered twice through hidden prompts and is hashed using the
same `_password_hash` function as the API. If the username already exists,
seeding fails rather than resetting its password.

```powershell
$env:DATABASE_URL = "postgresql://hv_app:<your-database-password>@localhost:5432/hvlabel"
python server\seed.py `
  --device "Main PC=<64-character-machine-hash>" `
  --admin-username <admin-name>
```

Repeat `--device "Name=hash"` for each authorized workstation. For example,
after replacing the placeholder with the actual hash:

```powershell
$env:DATABASE_URL = "postgresql://hv_app:<your-database-password>@localhost:5432/hvlabel"
python server\seed.py --device "Main PC=6ffd448e61c84b0f5d2eb41304eb76df0b2cfb0f79d2476a5f8ab232b6a5f0b2" --admin-username Anil
```

Do not reuse a temporary/bootstrap password as the production admin password.

## Import existing local data

After applying `schema.sql` and setting `DATABASE_URL`, run this one-time
import from the repository root:

```powershell
python server\migrate_from_files.py
```

It reads the named sheets from the three workbooks under `models\hv\data`,
imports `pack_session.json` and `common\data\users.json`, and registers
machine hashes listed in `common\auth\machine_lock.py`. Existing user salts
and password hashes are copied unchanged. Since the source files do not
identify which PC created each old scan, imported records, users, and the
serial counter are associated with the first machine hash in sorted order.
Existing device names and enabled/disabled settings are preserved.

The script creates a `migration_imports` ledger table to make each source row
idempotent and to retain per-row failures. It prints imported/skipped counts
for every source; malformed and duplicate rows are reported to stderr and do
not prevent other rows from importing. It does not modify the source files.
