# HV Label Printer

A Windows desktop application built with **Python + Tkinter** for production-line scanning, validation, label generation, printing, and traceability of high-voltage battery components.

The application is designed for **Ultraviolette Automotive** production workflows and generates raw **ZPL** labels for Zebra printers.

---

## Overview

The application starts from `main.py` and opens the main **HV Label Printer** interface.

Before the application is shown, the machine is checked against an authorized machine list. Users then authenticate through the application and can access the available label-printing workflows according to their role.

### Available workflows

| Screen | Purpose |
|---|---|
| **Battery Pack Dummy ID** | Scan four module IDs (M1–M4), validate that the modules belong to the same pack configuration, generate the pack QR, print the dummy/pack QR label, and log the operation. |
| **Battery Pack ID** | Scan a pack serial/pack QR, resolve the variant and battery parameters, generate the complete battery-pack identification label, print it, and log the scan. |
| **BMB / CMB ID** | Scan a pack QR followed by BMB and CMB IDs, generate the combined BMB/CMB label, print it, and log the operation. Supports rework and reprinting of corrected BMB/CMB IDs. |
| **Dummy ID (manual)** | Scan a pack serial number and manually provide required pack details before generating and printing a dummy label. |

The main application also contains launch buttons for other label-printing applications such as LV, Shockwave, and Tesseract tools. These applications are separate executables and are configured in the HV application.

---

## Application Architecture

The application is organized into shared functionality and the HV-specific implementation:

```text
main.py
   │
   ├── Machine authorization
   │       └── common/auth/machine_lock.py
   │
   ├── User session
   │       └── common/auth/
   │
   └── models/hv/app.py
           │
           ├── GUI workflows
           │
           ├── Nomenclature / QR parsing
           │
           ├── ZPL label generation
           │
           └── Production scan logs
```

The major flow is:

```text
Scanner
   ↓
Scan classification
   ↓
Nomenclature parsing
   ↓
Production-rule validation
   ↓
GUI state / integration
   ↓
ZPL generation
   ↓
Windows RAW print spooler
   ↓
Zebra printer

                    └──→ Excel production log
```

---

# Authentication and Machine Authorization

## Machine authorization

The application uses:

```text
Windows MachineGuid
       ↓
SHA-256
       ↓
Authorized machine hash list
       ↓
Application allowed / rejected
```

The implementation is located at:

```text
common/auth/machine_lock.py
```

Only authorized machines can start the application.

## User authentication

Users are stored locally in:

```text
common/data/users.json
```

Current application roles are:

- **Admin**
- **Operator**

The session implementation is located at:

```text
common/auth/session.py
```

Administrators can access application settings and user-management functionality.

---

# Battery Pack Dummy ID

The Battery Pack Dummy workflow is the primary module-integration workflow.

## Workflow

```text
Configure pack settings
        ↓
Scan M1
        ↓
Scan M2
        ↓
Scan M3
        ↓
Scan M4
        ↓
Validate all modules
        ↓
Integration OK
        ↓
Generate Pack QR
        ↓
Generate ZPL
        ↓
Print / Save ZPL
        ↓
Write production log
```

### Module validation

When scanning M1–M4, the application checks the module nomenclature and validates:

- Module ID format
- Variant
- Plant
- Part/model number
- Duplicate module scans
- Category compatibility
- Four-module integration consistency

The remaining modules are compared against M1 so that incompatible modules are rejected.

## Pack serial handling

Pack serial state is persisted locally in:

```text
models/hv/data/pack_session.json
```

The application can load the current serial, store the serial, and increment the serial count for subsequent production operations.

---

# Battery Pack ID

The Battery Pack ID workflow is used to generate the complete identification label for a battery pack.

## Workflow

```text
Scan Pack QR / Serial
        ↓
Identify scan type
        ↓
Parse serial number
        ↓
Resolve variant
        ↓
Load battery parameters
        ↓
Generate Pack ID ZPL
        ↓
Print / Save ZPL
        ↓
Write Pack ID scan log
```

Depending on the scanned format, the application can resolve information such as:

- Variant
- Serial number
- Rated capacity
- Maximum voltage
- Model number
- TAC number
- E-marking information
- Manufacturing date
- Pack QR data

The current HV variants are:

| Variant | Model | Rated capacity | Maximum voltage |
|---|---|---:|---:|
| **12P** | VX156590 | 6 kWh | 116.2 V |
| **16P** | VX156600 | 8.1 kWh | 116.2 V |
| **24P** | VX156610 | 12.1 kWh | 116.2 V |
| **27P** | VX156620 | 13.6 kWh | 116.2 V |

Variant-specific values are centralized in:

```text
models/hv/gui/constants.py
```

---

# BMB / CMB ID

The BMB/CMB workflow handles battery-management-board identification.

Supported identifiers include:

- BMB IDs
- CMB IDs
- Pack QR data
- Rework BMB/CMB IDs

## Normal workflow

```text
Scan Pack QR
      ↓
Scan BMB ID
      ↓
Scan CMB ID
      ↓
Generate combined BMB/CMB label
      ↓
Print / Save ZPL
      ↓
Write scan log
```

The workflow stores the full BMB/CMB identifiers in the production log while the label can use the required shortened identifier.

## Rework workflow

The screen provides a **Rework** mode.

When rework is enabled:

1. Scan the relevant pack QR.
2. The application searches the previous production record.
3. Scan the corrected BMB or CMB ID.
4. The existing record is patched with the corrected ID.
5. A corrected combined label is generated.
6. The corrected label is printed or saved.

---

# Dummy ID — Manual Workflow

The **Dummy ID** screen provides a manual label-generation workflow.

## Workflow

```text
Scan Pack Serial
      ↓
Parse serial
      ↓
Enter / confirm pack details
      ↓
Resolve battery parameters
      ↓
Generate Dummy Pack QR label
      ↓
Print / Save ZPL
      ↓
Write scan log
```

This workflow is useful when a label needs to be generated from an existing serial without performing the normal four-module integration workflow.

---

# Nomenclature and Scan Parsing

All scan parsing is separated from the GUI.

Main modules:

```text
models/hv/nomenclature/
├── module_id.py
├── serial_number.py
├── bms_id.py
└── scan_handler.py
```

## Unified scan classifier

`scan_handler.py` identifies incoming scanner data as one of the supported types:

```text
Input
 │
 ├── Pack / Serial Number
 ├── Module ID
 ├── BMB ID
 ├── CMB ID
 ├── BMS ID
 ├── Full BMS QR
 └── Unknown
```

This keeps QR-format recognition independent from the individual GUI screens.

---

# Supported BMS / BMB / CMB Formats

The BMB/CMB parser supports model-based formats such as:

```text
VQ150720-REV-A-S26250069
VQ150710-2v2S26250088
VQ150720_1.0X26030083
```

where:

- `VQ150720` identifies BMB
- `VQ150710` identifies CMB

The BMS parser also supports:

```text
123456789
```

and full QR formats matching the application's BMS QR pattern.

---

# Printing

Labels are generated as raw **ZPL (Zebra Programming Language)**.

The printing pipeline is:

```text
GUI
 ↓
printing/labels.py
 ↓
printing/zpl.py
 ↓
printing/spooler.py
 ↓
Windows winspool.drv
 ↓
Zebra printer
```

The application sends ZPL directly to the Windows print spooler using `ctypes` and the RAW datatype.

This avoids the normal Windows print dialog and allows the Zebra printer to interpret the ZPL directly.

## Printer configuration

Current printer constants are defined in:

```text
models/hv/printing/constants.py
```

The primary configured printer is:

```text
ZDesigner ZD421-300dpi ZPL
```

The application resolves installed printers and can perform a case-insensitive partial-name match when resolving the configured printer name.

## Print / save mode

The GUI provides:

- **print** — send raw ZPL to the configured Zebra printer
- **pdf** — save the generated label data to a file for testing/offline use

> Note: The current `pdf` mode saves ZPL/text data; it does not render the ZPL into a visual PDF.

## Zebra printer requirements

For raw ZPL printing on Windows:

1. Install the Zebra ZD421 printer.
2. Install/configure the ZDesigner ZPL driver.
3. Make sure the printer is available to Windows.
4. Configure the Windows print processor for RAW printing where required.
5. Use ZPL printer language rather than EPL2.

---

# Production Logs and Traceability

The application stores production scan information in Excel workbooks under:

```text
models/hv/data/
```

Current logs include:

```text
scan_log.xlsx
pack_id_scan_log.xlsx
bms_scan_log.xlsx
```

## HV Dummy scan log

The HV Dummy log can contain:

- Serial number
- Serial count
- Date
- Time
- Variant
- M1–M4 module IDs
- Dummy pack status
- Dummy pack QR
- Issue descriptions
- Action plan
- Remarks
- Admin acknowledgement

## Pack ID log

The Pack ID log records:

- Date
- Time
- Serial number
- Variant
- Pack QR data

## BMB/CMB log

The BMB/CMB log records:

- Date
- Time
- Pack QR data
- Full BMB ID
- Full CMB ID
- Rework BMB ID
- Rework CMB ID

The application also provides scan-history interfaces for reviewing stored production records.

---

# Project Structure

Current repository structure:

```text
hv_label_print/
│
├── main.py                         # Application entry point
├── hv_main.spec                    # PyInstaller build specification
├── install_fonts.py                # Font installation utility
├── test.py                         # Development/test entry point
├── updates.md                      # Project update notes
├── README.md                       # Project documentation
│
├── common/
│   ├── auth/
│   │   ├── machine_lock.py         # Machine authorization
│   │   ├── session.py              # Logged-in user session
│   │   └── user_store.py           # Local user storage/authentication
│   │
│   ├── nomenclature/               # Shared nomenclature utilities
│   ├── data/                       # Shared runtime data
│   └── paths.py                    # Common path resolution
│
└── models/
    └── hv/
        ├── app.py                  # Main HV application/navigation
        │
        ├── assets/
        │   ├── logo.png
        │   └── logo.ico
        │
        ├── data/
        │   ├── scan_log.xlsx
        │   ├── pack_id_scan_log.xlsx
        │   ├── bms_scan_log.xlsx
        │   └── pack_session.json
        │
        ├── gui/
        │   ├── battery_pack_dummy.py
        │   ├── battery_pack_id.py
        │   ├── bms_id.py
        │   ├── dummy_id.py
        │   ├── battery_parameters.py
        │   ├── category_controls.py
        │   ├── constants.py
        │   ├── layout.py
        │   ├── permissions.py
        │   ├── print_actions.py
        │   ├── scan_apply.py
        │   ├── scan_history.py
        │   └── scanner.py
        │
        ├── nomenclature/
        │   ├── module_id.py
        │   ├── serial_number.py
        │   ├── bms_id.py
        │   └── scan_handler.py
        │
        ├── printing/
        │   ├── constants.py
        │   ├── labels.py
        │   ├── spooler.py
        │   └── zpl.py
        │
        └── session/
            ├── bms_scan_log.py
            ├── pack_id_scan_log.py
            ├── pack_store.py
            ├── paths.py
            └── scan_log.py
```

---

# PyInstaller Build

The project uses:

```text
hv_main.spec
```

The entry point is:

```text
main.py
```

Build the executable with:

```bash
pyinstaller hv_main.spec
```

The spec file:

- Uses `main.py` as the entry point.
- Collects submodules from `models` and `common`.
- Includes application logo assets.
- Includes runtime data directories.
- Excludes several unused development/scientific GUI packages.
- Builds a windowed executable without a console.
- Uses `models/hv/assets/logo.ico` as the executable icon.

The executable name configured by the spec file is:

```text
HV Label Printer
```

---

# Runtime Paths

The application supports both normal Python execution and PyInstaller execution.

For frozen execution, runtime data is resolved relative to the executable and the bundled project structure.

Important runtime locations include:

```text
models/hv/data/
common/data/
models/hv/assets/
```

This allows the application to keep production data outside the Python source modules.

---

# Requirements

## Operating system

- Windows

Raw ZPL printing uses the Windows print spooler API and `winspool.drv`.

## Python

The project uses modern Python syntax and type hints. Python **3.10+** is recommended.

## Main components

- Python
- Tkinter
- openpyxl
- PyInstaller
- Zebra ZPL-compatible printer
- Hardware barcode/QR scanner

The exact Python dependencies should be kept aligned with the imports used by the current source tree.

---

# Development Notes

Before modifying production behavior, pay particular attention to:

- Serial-number generation and incrementing
- Module-ID validation
- Variant and plant matching
- Pack QR generation
- ZPL label dimensions
- Printer names
- Excel log formats
- Rework handling
- Machine authorization
- User authentication
- PyInstaller resource paths

Changes to nomenclature or label content should be tested with representative production QR values before deployment.

---

# Deployment Checklist

Before deploying the application to a production machine:

- [ ] Machine is authorized.
- [ ] Zebra ZD421 printer is installed.
- [ ] Correct ZPL printer/driver configuration is present.
- [ ] Scanner input works correctly.
- [ ] Application starts without authorization errors.
- [ ] Admin/operator authentication works.
- [ ] Required runtime data directories are writable.
- [ ] Test ZPL can be generated.
- [ ] Test label prints correctly.
- [ ] Scan logs can be written.
- [ ] Pack serial persistence works.
- [ ] Rework workflow has been tested if required.

---

## Author

**Anil D**

**HV Label Printer — Ultraviolette Automotive**
