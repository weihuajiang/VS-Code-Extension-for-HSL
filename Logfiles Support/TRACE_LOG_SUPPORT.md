# HSL Trace Log Language Support

This document describes the `.trc` trace log file support added to the Hamilton HSL VS Code extension.

---

## Overview

Hamilton VENUS produces `.trc` trace log files during method execution. These files record every system event, user trace message, firmware command, and error that occurs during a run. The VS Code extension now registers `.trc` files as a first-class language (`hsl-trace`) with syntax highlighting and firmware-aware IntelliSense.

---

## Features

### Syntax Highlighting

Opening any `.trc` file in VS Code activates the HSL Trace Log grammar, which colorizes:

| Element | Example | Coloring |
|---------|---------|----------|
| Timestamps | `2025-03-11 14:23:05.123` | Comment (muted) |
| SYSTEM prefix | `SYSTEM :` | Keyword (bold/colored) |
| USER prefix | `USER :` | Function name (colored) |
| Firmware responses | `CLid0001er00/00ci...` | Multiple scopes (code, params, values) |
| Error codes (non-zero) | `er05/00` | Error (red/highlighted) |
| Step type names | `Aspirate`, `Head96TipPickUp` | Type (colored) |
| Simulator markers | `[FW CL]`, `[SIM]` | Bold/accent |
| Firmware parameters | `cp01`, `cv1281` | Parameter + numeric value |
| GUIDs / CLSIDs | `541143F5_7FA2_11D3_...` | String (quoted style) |
| File paths | `C:\...\MyMethod.hsl` | String |
| Numbers | `1281`, `32.5` | Numeric constant |

### Hover Information

Hovering over recognized tokens in a `.trc` file shows detailed documentation:

#### Firmware Response Strings

Hovering over `CLid0001er00/00` shows:

- Command name, description, SFCO ID
- Full parameter table with types, ranges, and defaults
- Response format
- Error code interpretation (if non-zero)

#### Firmware Parameter Values

Hovering over `cp01` or `cv1281` shows:

- Parameter name and description
- Type, valid range, and default value
- Warning if the value is outside the valid range

#### Error Codes

Hovering over `er05/00` shows:

- Error code number and description
- Trace information value

#### Step Type Names

Hovering over `Aspirate` or `Head96TipPickUp` shows:

- Step type identification
- Corresponding device CLSID

#### CLSIDs

Hovering over a CLSID like `541143F5_7FA2_11D3_AD85_0004ACB1DCB2` shows:

- The step type name it maps to

### Code Completion

Typing in a `.trc` file suggests all known firmware command codes with their descriptions and full documentation.

### Folding

Trace files support folding between `start` and `complete` lifecycle markers, so you can collapse executed method sections.

---

## File Structure

### Registered Files

| File | Purpose |
|------|---------|
| `firmware_commands.json` | Single source of truth for firmware command definitions |
| `syntaxes/hsl-trace.tmLanguage.json` | TextMate grammar for `.trc` syntax highlighting |
| `language-configuration-trace.json` | Editor behavior (folding, word patterns) |
| `src/traceLanguageSupport.ts` | Hover and completion providers |

### Registration in package.json

The extension registers the `hsl-trace` language:

```json
{
  "id": "hsl-trace",
  "aliases": ["HSL Trace Log", "Hamilton Trace"],
  "extensions": [".trc"],
  "configuration": "./language-configuration-trace.json"
}
```

With a dedicated TextMate grammar:

```json
{
  "language": "hsl-trace",
  "scopeName": "source.hsl-trace",
  "path": "./syntaxes/hsl-trace.tmLanguage.json"
}
```

---

## Trace File Format

Hamilton `.trc` files follow this line format:

```
<timestamp> <source> : <event_type> - <status>; <message>
```

### Example Trace Output

```
2025-03-11 14:23:05.100 Venus software version: 4.8.0.1234
2025-03-11 14:23:05.101 SYSTEM : Analyze method - start; Method file C:\Methods\MyMethod.hsl
2025-03-11 14:23:05.102 SYSTEM : Analyze method - complete;
2025-03-11 14:23:05.103 SYSTEM : Start method - start;
2025-03-11 14:23:05.104 SYSTEM : Start method - progress; User name: labuser
2025-03-11 14:23:05.105 SYSTEM : Start method - complete;
2025-03-11 14:23:05.200 SYSTEM : Execute method - start; Method file C:\Methods\MyMethod.hsl
2025-03-11 14:23:05.300 USER : Trace - complete; Starting pipetting sequence
2025-03-11 14:23:05.400 USER : Trace - complete; Aspirating 150 uL from plate
2025-03-11 14:23:06.500 SYSTEM : Execute method - complete;
2025-03-11 14:23:06.600 SYSTEM : End method - start;
2025-03-11 14:23:06.601 SYSTEM : End method - complete;
```

### Simulation Trace Output

The Python debugger (F5) produces traces with additional firmware markers:

```
2025-03-11 14:23:05.200 [SIM] Device step: Initialize (CLSID=1C0C0CB0_..., guid=abc123...)
2025-03-11 14:23:05.201 [FW II] Initialize Autoload -> OK (IIid0001er00/00)
2025-03-11 14:23:05.300 [SIM] Device step: LoadCarrier (CLSID=54114402_..., guid=def456...)
2025-03-11 14:23:05.301 [FW CL] Load carrier -> OK (CLid0001er00/00ci00000001)
```

---

## Firmware Definitions

All firmware command definitions are loaded from `firmware_commands.json` at the workspace root. This file is shared between:

1. **This VS Code IntelliSense provider** -- for hover documentation and completions
2. **The Python simulation runtime** (`HSL Debugger/hsl_runtime/firmware.py`) -- for command validation and simulation

See `Firmware Support/FIRMWARE_COMMANDS.md` for the full schema, currently registered commands, and instructions for adding new ones.

---

## How It Works

### TypeScript Side (VS Code Extension)

1. On activation, `src/traceLanguageSupport.ts` loads `firmware_commands.json` into a `FirmwareRegistry`
2. The registry indexes commands by code and parameters by name for fast lookup
3. A `HoverProvider` registered for the `hsl-trace` language uses regex matching to identify tokens under the cursor and returns formatted Markdown documentation
4. A `CompletionProvider` offers all known firmware command codes

### Python Side (Simulation Runtime)

1. `FirmwareCommandRegistry.__init__()` searches upward from its module directory for `firmware_commands.json`
2. If found, it parses the JSON and creates `FirmwareCommand` + `FirmwareParam` objects
3. If not found (e.g., running the simulator standalone), it falls back to hardcoded definitions
4. The `FirmwareEngine` uses these definitions for parameter validation and response generation

### TextMate Grammar

The grammar at `syntaxes/hsl-trace.tmLanguage.json` uses regex patterns to tokenize trace lines. The patterns are ordered by specificity:

1. Timestamps (most specific -- always at line start)
2. SYSTEM / USER prefixes
3. Firmware response strings (compound pattern with captures)
4. Simulator markers
5. Error codes
6. Step type names
7. Firmware command codes
8. Parameter key-value pairs
9. GUIDs
10. File paths
11. Numbers (least specific -- fallback)

---

## Expanding Support

### Adding New Firmware Commands

Edit `firmware_commands.json` only. See `Firmware Support/FIRMWARE_COMMANDS.md` for the schema and step-by-step instructions.

### Adding New Step Types

If Hamilton adds new device step types:

1. Add the CLSID mapping in `src/traceLanguageSupport.ts` (`CLSID_TO_STEP`)
2. Add the step name to the `STEP_TYPES` set in the same file
3. Add it to the `step-types` pattern in `syntaxes/hsl-trace.tmLanguage.json`
4. Add it to the `CLSID_MAP` in `HSL Debugger/hsl_runtime/firmware.py`

### Adding New Firmware Parameter Names

New parameter names are automatically picked up from `firmware_commands.json`. If a parameter appears in any command definition, the hover provider will recognize it in trace output.

To also get syntax highlighting for the new parameter name, add it to the `firmware-params` pattern in `syntaxes/hsl-trace.tmLanguage.json`.
