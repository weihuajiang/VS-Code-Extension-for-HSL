# Hamilton IDL Firmware Command Reference

This document describes the firmware command system used by the Hamilton ML STAR liquid-handling platform and how it integrates with the VS Code extension.

---

## Architecture

The firmware command definitions live in a single shared file:

```
firmware_commands.json    (workspace root)
```

This JSON file is the **single source of truth** consumed by:

1. **VS Code extension** (`src/traceLanguageSupport.ts`) -- provides IntelliSense (hover, completions) when viewing `.trc` trace log files
2. **Python simulation runtime** (`HSL Debugger/hsl_runtime/firmware.py`) -- validates and simulates firmware commands during F5 debugging

Adding or modifying firmware commands requires editing only `firmware_commands.json`. No TypeScript or Python code changes are needed.

---

## firmware_commands.json Schema

```json
{
  "errorCodes": {
    "00": "No error",
    "02": "Not initialized",
    ...
  },
  "paramTypes": {
    "INT": "Integer value",
    "FLOAT": "Floating-point value",
    "HEX": "Hexadecimal value",
    "BITFIELD": "Bit field",
    "STRING": "String value"
  },
  "commands": [
    {
      "code": "XX",
      "sfcoId": "SFCO.NNNN",
      "category": "Category Name",
      "specSection": "3.12.1",
      "description": "Human-readable description",
      "commandPoint": 1,
      "params": [
        {
          "name": "id",
          "type": "INT",
          "min": 0,
          "max": 9999,
          "default": 0,
          "width": 4,
          "description": "Parameter description"
        }
      ],
      "responseFields": ["id####", "er##/##"],
      "notes": "Optional notes"
    }
  ]
}
```

### Command Fields

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Two-letter firmware command code (e.g. `"II"`, `"CL"`) |
| `sfcoId` | string | SFCO identifier from the IDL spec (e.g. `"SFCO.0005"`) |
| `category` | string | Functional grouping (e.g. `"Autoload Carrier Handling"`) |
| `specSection` | string | Section number in the IDL Firmware specification |
| `description` | string | What the command does |
| `commandPoint` | number | CP value from the spec (0 = query, 1 = action) |
| `params` | array | Parameter definitions (see below) |
| `responseFields` | array | Response format tokens (e.g. `["id####", "er##/##"]`) |
| `notes` | string | Additional notes or caveats |

### Parameter Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Two-letter parameter mnemonic (e.g. `"cp"`, `"cv"`) |
| `type` | string | One of: `INT`, `FLOAT`, `HEX`, `BITFIELD`, `STRING` |
| `min` | number | Minimum allowed value |
| `max` | number | Maximum allowed value |
| `default` | number | Default value if not specified |
| `width` | number | Number of digits/characters in the protocol encoding |
| `description` | string | What the parameter controls |

---

## Currently Registered Commands

All commands from IDL Firmware Specification Section 3.12 (Autoload).

### 3.12.1 -- Initialization

| Code | SFCO | Description |
|------|------|-------------|
| `II` | SFCO.0005 | Initialize Autoload |
| `IV` | SFCO.0251 | Move Autoload to Z save position |

### 3.12.2 -- Carrier Handling

| Code | SFCO | Description |
|------|------|-------------|
| `CI` | SFCO.0013 | Identify carrier (read barcode) |
| `CT` | SFCO.0075 | Check presence of single carrier |
| `CA` | SFCO.0015 | Push out carrier to loading tray |
| `CR` | SFCO.0016 | Unload carrier |
| `CL` | SFCO.0014 | Load carrier |
| `CP` | SFCO.0017 | Set loading indicators (LEDs) |
| `CS` | SFCO.0018 | Check for presence of carriers on loading tray |
| `CB` | SFCO.0072 | Set barcode types and 2D reader features |
| `DB` | -- | Set code reading features for free definable carrier |
| `DR` | -- | Reset free definable carrier settings |
| `CW` | SFCO.0140 | Unload carrier finally |
| `CU` | SFCO.0146 | Set carrier monitoring |
| `CN` | SFCO.0238 | Take out carrier to identification position |

### 3.12.3 -- Queries

| Code | SFCO | Description |
|------|------|-------------|
| `RC` | SFCO.0045 | Query presence of carrier on deck |
| `QA` | SFCO.0200 | Request autoload slot position |
| `CQ` | SFCO.0341 | Request autoload module type |
| `VK` | -- | Request code data of individual labware position |
| `VL` | -- | Request code data length of all labware positions |

### 3.13 -- iSWAP Commands

These commands control the iSWAP (Internal Sample Arm for Workdeck Plate handling) -- Hamilton's robotic plate-gripping arm that sits on a horizontal rail spanning the width of the instrument.

The iSWAP has two defined park positions: **right** (home/default) and **left** (alternate). The parking maneuver slides the arm laterally along its traverse rail. This is NOT a re-home or calibration cycle -- it is a simple point-to-point move.

These firmware mnemonics are stored in STP field `-534183816` and sent to the instrument controller via the FirmwareCommand COM interface (`{1FB5DA01-3ACB-11d4-AE1F-0004ACB1DCB2}`).

| Code | SFCO | Description |
|------|------|-------------|
| `PXZI` | -- | Prepare/position iSWAP traverse axis, initialize Z-axis motors |
| `H0ZI` | -- | Home iSWAP Z-axis (retract gripper vertically) |
| `C0FY` | -- | Coordination/synchronization (settle channel arm before iSWAP moves) |
| `R0MO` | -- | Move iSWAP to Opposite side (right -> left park) |
| `R0MH` | -- | Move iSWAP to Home position (left -> right park) |

**Note:** SFCO IDs for iSWAP commands are not available in the IDL spec extract included in this workspace. The command codes and behaviors were reverse-engineered from the Visual NTR Library's STP binary data using the HxCfgFile codec.

#### iSWAP Park-Left Sequence (6 steps)

Used when CO-RE grippers need to access a rear carrier position (Y > 433.8 mm) and the iSWAP is parked on the right blocking access:

1. `PXZI` -- Power up traverse motors
2. `H0ZI` -- Retract iSWAP Z-axis (raise gripper fingers)
3. MoveToPosition Y=770 mm -- Move all pipetting channels to far rear of deck, clearing the path
4. `C0FY` -- Wait for channel arm to settle
5. `R0MO` -- Slide iSWAP arm from right to left park position

#### iSWAP Park-Right Sequence (2 steps)

Used after transport is complete to restore iSWAP to its home (right) position:

1. `C0FY` -- Wait for channel arm to settle
2. `R0MH` -- Slide iSWAP arm from left back to right (home) park position

---

## Error Codes

Error codes appear in firmware response strings as `er##/##` where the first two digits are the error code and the second two are trace information.

| Code | Description |
|------|-------------|
| `00` | No error |
| `01` | Initialization error |
| `02` | Not initialized |
| `03` | Invalid parameter value |
| `04` | Carrier not found |
| `05` | Slot empty / no carrier to operate on |
| `06` | Hardware communication timeout |
| `07` | Movement blocked |
| `08` | Liquid level not detected |
| `09` | Tip already present |
| `10` | No tip present |
| `11` | Insufficient liquid volume |
| `12` | Clot detected (pressure LLD) |
| `13` | Over-aspirate detected |
| `14` | Tip lost during operation |
| `15` | Barcode read error |
| `16` | Autoload carrier jam |
| `17` | Cover open or interlock error |
| `18` | Z-drive overload |
| `19` | X-drive overload |
| `20` | Y-drive overload |
| `30` | Waste full |
| `99` | Unknown firmware command |

---

## Firmware Protocol Format

### Command String

Commands are sent to the instrument as ASCII strings:

```
<code>id<####><param1><value1><param2><value2>...
```

Example -- Initialize Autoload with ID 1:
```
IIid0001
```

Example -- Load carrier with barcode direction=vertical, 32 containers:
```
CLid0001bd0000bp0100cn0032co0150cf0100ea0000mr0000cv1281
```

### Response String

Responses follow the same pattern with an error field:

```
<code>id<####>er<##>/<##><additional_fields>
```

- `er00/00` = success (no error)
- `er05/00` = error code 5 (slot empty), trace info 0

Example -- Successful initialize:
```
IIid0001er00/00
```

Example -- Check carrier presence, carrier found:
```
CTid0001er00/00ct1
```

---

## How to Add New Firmware Commands

1. Open `firmware_commands.json` in the workspace root
2. Add a new entry to the `commands` array:

```json
{
  "code": "PA",
  "sfcoId": "SFCO.0042",
  "category": "Pipetting Channel",
  "specSection": "3.5.1",
  "description": "Aspirate with pipetting channel",
  "commandPoint": 1,
  "params": [
    {
      "name": "id",
      "type": "INT",
      "min": 0,
      "max": 9999,
      "default": 0,
      "width": 4,
      "description": "Identification number"
    },
    {
      "name": "av",
      "type": "INT",
      "min": 0,
      "max": 11500,
      "default": 0,
      "width": 5,
      "description": "Aspirate volume [0.1 uL]"
    }
  ],
  "responseFields": ["id####", "er##/##"],
  "notes": "Volume in tenths of microliters"
}
```

3. Save the file. The changes take effect:
   - **VS Code extension**: Next time a `.trc` file is opened (or on extension reload), the new command will appear in hovers and completions
   - **Python simulator**: Next simulation run will load the updated definitions

4. If the new command needs simulation behavior (beyond generic success), add a handler method in `firmware.py`:

```python
def _handle_my_new_command(self, params: dict,
                           cmd_def: FirmwareCommand) -> FirmwareResult:
    cmd_id = params["id"]
    # ... custom simulation logic ...
    return FirmwareResult(
        command_code="PA",
        command_id=cmd_id,
        success=True,
        response_string=self._ok_response("PA", cmd_id),
        description="Aspirated successfully",
    )
```

And register it in `FirmwareEngine.__init__()`:

```python
self._handlers["PA"] = self._handle_my_new_command
```

Commands without explicit handlers in `firmware.py` still work -- they return a generic success response with `er00/00`.

---

## IDL Firmware Specification

The full IDL firmware specification is in `IDL Firmware.html` in this directory. The `firmware_commands.json` definitions are derived from that specification and should be kept in sync as new sections are implemented.

### Sections Not Yet Implemented

These IDL spec sections have commands that are not yet in `firmware_commands.json`:

- 3.1 -- General system commands
- 3.2 -- X-drive commands
- 3.3 -- Y-drive commands
- 3.4 -- Z-drive commands
- 3.5 -- Pipetting channel commands
- 3.6 -- Capacitive sensor commands
- 3.7 -- Temperature controller commands
- 3.8 -- Pump commands
- 3.9 -- CO-RE 96 head commands
- 3.10 -- Wash station commands
- 3.11 -- Heater/shaker commands
- 3.14 -- Nano pipettor commands

Section 3.13 (iSWAP commands) has been partially implemented from reverse-engineered STP data. The formal IDL spec for section 3.13 is not included in the workspace -- SFCO IDs and full parameter schemas are unavailable.

To implement a new section, extract the commands from `IDL Firmware.html` and convert them to the JSON schema above.
