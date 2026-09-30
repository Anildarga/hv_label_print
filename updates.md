# Project context
Tkinter desktop app (Windows) for printing Zebra ZPL labels on a battery production line.
Multiple PCs run this app. Today each PC keeps its own Excel logs (openpyxl) and JSON files.

# Migration goal
Replace ALL local file persistence with ONE central PostgreSQL database on a LAN server,
accessed through a small FastAPI service. All authorized devices must read and write the same
data in near-realtime, with safe parallel writes.

# Architecture decisions (do not change without asking)
- Backend: FastAPI + PostgreSQL (psycopg 3, connection pool), in a new top-level `server/` folder.
- Client: existing Tkinter app calls the API through a new `common/api_client.py` (requests, with timeouts).
- Device identity = existing SHA-256 machine hash from common/auth/machine_lock.get_machine_hash().
  Authorization = a row in a `devices` table (authorized boolean), replacing the hardcoded AUTHORIZED_HASHES.
  Every request sends the machine hash in a header; server rejects unauthorized devices.
- The running serial count is global and must be allocated atomically on the server
  (single UPDATE ... RETURNING on a counter row). Never compute it client-side.
- Add UNIQUE constraints to prevent duplicate serials, module IDs and BMS IDs across devices.
- Log rows are identified by a primary key `id`, not by Excel row number.
  Admin-ack and rework updates are keyed by `id`.
- Excel becomes EXPORT ONLY (generate .xlsx from DB on button click). No more reading Excel for logic.
- Realtime = client polls the API every ~3 seconds for history views, using a background thread.
  NEVER call the network on the Tkinter main thread; use threading + root.after() to update UI.
- If the server is unreachable: block printing and show a clear error. No offline mode.

# Rules
- Keep existing function names and signatures in the session/auth modules where possible so the GUI
  code barely changes (e.g. append_scan_record, load_all_records, patch_admin_ack, patch_rework,
  authenticate_user, get_machine_hash).
- Preserve the existing serial number and QR formats exactly. Do not change nomenclature code.
- Server settings (URL, DB URL) come from a config file / env vars, never hardcoded.
- Passwords stay salted+hashed. Do not hardcode secrets.
- Add type hints and small unit tests for server logic (pytest).
- Make small, reviewable changes. Explain what you changed after each step.


In models/hv/gui/scan_history.py and the admin issue views, add background polling every 3 seconds:
a worker thread fetches the latest records and updates the UI via root.after(). Only refresh
the view if data changed, and preserve scroll position and selection.
Add an "Export to Excel" button that generates an .xlsx from the DB (same columns and
formatting as the old workbooks). Confirm nothing in the GUI still touches local Excel/JSON for logic.

Concurrency test: after Step 3, run the app on two PCs and print serials as fast as you can. The test passes if you never see a duplicate serial.
Duplicate serial limits: unique constraints will reject a duplicate outright, so the GUI needs a sensible error message for it.
Secrets in the repo: the repo contains the Excel password 06082003 and the machine hashes. The DB removes the need for both, but if this repo is on GitHub, treat that password as exposed.
Backups: set up a nightly pg_dump on the server. Once Excel is gone, the database is your only copy.
Server host: decide which PC hosts it (fixed IP, always on) before Step 1, because the server README will depend on it.