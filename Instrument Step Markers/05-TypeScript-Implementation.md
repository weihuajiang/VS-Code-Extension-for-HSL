# 05 — TypeScript Implementation

This document describes the `stpHoverProvider.ts` module — the VS Code extension component that parses binary `.stp` files and displays pipetting parameters as hover tooltips over device step calls in HSL code.

---

## Architecture Overview

```
HSL Editor                stpHoverProvider.ts              .stp Binary File
┌─────────────────┐      ┌─────────────────────────┐      ┌──────────────┐
│ User hovers over │─────>│ 1. Regex match on line  │      │              │
│ ML_STAR._CLSID   │      │ 2. Extract CLSID + GUID │      │              │
│   ("guid")       │      │ 3. Look up step type    │      │              │
│                 │      │ 4. Find .stp file       │─────>│ Binary parse │
│                 │      │ 5. Parse binary          │<─────│ Token stream │
│                 │      │ 6. Extract parameters   │      │              │
│ ┌─────────────┐ │<─────│ 7. Format tooltip       │      │              │
│ │ Tooltip:    │ │      └─────────────────────────┘      └──────────────┘
│ │ Vol: 150 µL │ │
│ │ LLD: Cap:5  │ │
│ └─────────────┘ │
└─────────────────┘
```

The module is structured into five logical sections:

1. **CLSID and Field ID Maps** — Static lookup tables
2. **Binary Parser** — Port of `hxcfgfile_codec.py` to TypeScript
3. **Token Extractor** — Walks the token stream, extracts structured parameters
4. **Tooltip Formatter** — Builds human-readable Markdown from parameters
5. **VS Code Integration** — Hover provider registration and .stp file caching

---

## File Location

Source: `src/stpHoverProvider.ts`

Registered in: `src/extension.ts` via:
```typescript
import { registerStpHoverProvider } from "./stpHoverProvider";
// In activate():
registerStpHoverProvider(context);
```

---

## Static Lookup Tables

### CLSID → Step Type

```typescript
const CLSID_TO_STEP_TYPE: Record<string, string> = {
  "1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2": "Initialize",
  "541143F5_7FA2_11D3_AD85_0004ACB1DCB2": "Aspirate",
  "541143F8_7FA2_11D3_AD85_0004ACB1DCB2": "Dispense",
  "541143FA_7FA2_11D3_AD85_0004ACB1DCB2": "TipPickUp",
  "541143FC_7FA2_11D3_AD85_0004ACB1DCB2": "TipEject",
  // ... (15 entries total)
};
```

Keys are uppercase underscore-formatted CLSIDs. The lookup normalizes user input to uppercase.

### Field ID → Parameter Name

```typescript
const FIELD_NAMES: Record<string, string> = {
  "-534183924": "Aspirate Volume (µL)",
  "-534183908": "Dispense Volume (µL)",
  "-534183915": "Mix Volume (µL)",
  "-534183914": "Mix Cycles",
  // ... (17 entries total)
};
```

### Enum Label Tables

```typescript
const LLD_MODE_LABELS: Record<string, string> = {
  "0": "Off",
  "1": "pLLD (Pressure)",
  "5": "Capacitive",
};

const DISPENSE_MODE_LABELS: Record<string, string> = { ... };
const SEQUENCE_COUNTING_LABELS: Record<string, string> = { ... };
```

---

## Binary Parser

The binary parser is a direct TypeScript port of the Python `hxcfgfile_codec.py` decoder. It reads the HxCfgFile v3 format and returns an array of `StpSection` objects.

### Interface

```typescript
interface StpSection {
  key: string;      // Section key (e.g., step instance GUID)
  tokens: string[]; // Ordered list of token strings
}

function parseStpBinary(data: Buffer): StpSection[]
```

### Parsing Sequence

1. Read u16 version — bail if not `3`
2. Read u16 section type
3. Read u32 named section count, skip named sections (key-value metadata)
4. Read u8 HxPars count + 3 bytes padding
5. For each HxPars section:
   - Read short-string raw name (strip `"HxPars,"` prefix)
   - Read u16 version, u32 token count
   - Read each token as a VarString
   - Store as `{ key, tokens }`

### String Reading Functions

```typescript
function readShortString(buf: Buffer, pos: number): [string, number]
function readVarString(buf: Buffer, pos: number): [string, number]
function readU16LE(buf: Buffer, pos: number): [number, number]
function readU32LE(buf: Buffer, pos: number): [number, number]
```

All return `[value, newPosition]` tuples for sequential buffer consumption.

---

## Token Extractor

The `extractStepParams()` function walks the token array and populates a structured `StepParams` object.

### Interface

```typescript
interface StepParams {
  stepName: string;
  sequenceObject: string;
  sequenceName: string;
  liquidName: string;
  channelPattern: string;
  sequenceCounting: string;
  liquidFollowing: string;
  dispenseMode: string;
  tipType: string;
  timestamp: string;
  usePickUpPosition: string;
  touchOffMode: string;
  sameLiquid: string;
  sideTouchMode: string;
  numericFields: Map<string, string>;        // Field ID → value
  channelFields: Map<string, string>[];      // Per-channel maps (single-channel steps)
}
```

### Extraction Logic

The extractor handles several token patterns:

1. **Error/Recovery blocks** (`(Errors`, `(Recoveries`): Skipped entirely using nest counting
2. **96-head group** (`(-534183935`): Flat iteration extracting field ID key-value pairs
3. **Single-channel group** (`(-534183936`): Iterates sub-groups, builds per-channel maps
4. **Named fields**: Keys like `1StepName` are matched via regex `^[135](.+)$` and routed to `setNamedField()`
5. **Other groups**: Skipped with nest counting

For single-channel steps, if `numericFields` is empty after extraction, the first channel's fields are promoted to `numericFields` for consistent downstream access.

---

## Tooltip Formatter

The `formatStepTooltip()` function produces a `vscode.MarkdownString` with the step's parameters formatted for display.

### Step-Type Dispatch

```typescript
if (isAspirateStep(stepType))     → formatAspirateTooltip()
else if (isDispenseStep(stepType)) → formatDispenseTooltip()
else if (isTipPickUpStep(stepType)) → formatTipPickUpTooltip()
else if (isTipEjectStep(stepType))  → formatTipEjectTooltip()
else if (stepType === "Initialize") → formatInitializeTooltip()
```

### Aspirate Tooltip Example Output

```markdown
### Head96Aspirate

**Sequence:** `ML_STAR.Cells`
**Sequence Counting:** Manually

**Liquid Class:** `HighVolumeFilter_96COREHead1000ul_Water_DispenseSurface_Empty`
**Volume:** 150 µL
**Mix:** 150 µL × 4 cycles
**Submerge Depth:** 2 mm
**LLD:** Capacitive, Sensitivity: 5
**Liquid Following:** On
**Retract Distance:** 10 mm

---
*Last modified: 2024-01-15 10:30:00*
```

### Conditional Display Rules

- Mix is only shown if both `mixCycles ≠ 0` and `mixVolume ≠ 0`
- Retract distance is only shown if non-zero
- LLD shows "Off" when mode is `0`, otherwise shows mode label + sensitivity
- Dispense liquid class shows "Same as aspiration" when `sameLiquid = 1`
- Tip pick-up shows active channel count computed from `channelPattern`
- Tip eject shows position label (default / pick-up / waste)

---

## STP File Cache

To avoid re-parsing the binary file on every hover, the module maintains an in-memory cache:

```typescript
interface StpCache {
  filePath: string;
  mtimeMs: number;
  sections: StpSection[];
}

const stpCacheMap = new Map<string, StpCache>();
```

Cache invalidation is based on file modification time (`mtimeMs`). If the `.stp` file changes, the next hover will re-parse and update the cache.

Cache keys are normalized to lowercase paths.

---

## STP File Discovery

The `findStpFile()` function locates the `.stp` file for a given `.hsl` file:

1. **Direct match**: Replace `.hsl` extension with `.stp` (e.g., `Method.hsl` → `Method.stp`)
2. **Directory scan fallback**: If no direct match, search the same directory for any `.stp` file

This handles cases where the `.hsl` and `.stp` files have slightly different naming conventions.

---

## HSL Line Matching

Device step calls are identified using this regex:

```typescript
const DEVICE_STEP_PATTERN =
  /(\w+)\._([0-9A-Fa-f]{8}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{12})\s*\(\s*"([0-9a-f_]+)"\s*\)/;
```

The hover only activates when the cursor position falls within the matched range on the line.

---

## Exported API

In addition to the hover provider, the module exports a `getStepSummary()` function for programmatic access:

```typescript
export function getStepSummary(
  stpPath: string,
  stepGuid: string
): { stepType: string; summary: string } | undefined
```

This returns a plain-text summary of a step's parameters, suitable for use by other extension components or LLM context providers.

---

## Extension Registration

In `src/extension.ts`:

```typescript
import { registerStpHoverProvider } from "./stpHoverProvider";

export function activate(context: vscode.ExtensionContext): void {
  // ... other registrations ...
  registerStpHoverProvider(context);
}
```

The hover provider is registered for `{ language: "hsl", scheme: "file" }`, meaning it activates for any on-disk HSL file.
