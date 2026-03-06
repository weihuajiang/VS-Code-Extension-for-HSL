# 02 — CLSID Registry

This document is the complete registry of COM Class Identifiers (CLSIDs) used by Hamilton instrument step markers. Each CLSID identifies a **type** of device step in HSL code.

---

## How CLSIDs Appear in HSL Code

Device steps are encoded as method calls on a device object (typically `ML_STAR`):

```hsl
arrRetValues = ML_STAR._<CLSID>("stepInstanceGuid"); // StepName
```

The CLSID uses **underscores** in place of the standard GUID hyphens:

| Standard GUID format | HSL underscore format |
|---|---|
| `827392A0-B7E8-4472-9ED3-B45B71B5D27A` | `827392A0_B7E8_4472_9ED3_B45B71B5D27A` |

The CLSID is always preceded by an underscore (`._`) on the device object.

---

## CLSID Format

CLSIDs follow the standard Windows COM GUID format:

```
XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
└─ 8 ──┘ └ 4┘ └ 4┘ └ 4┘ └─── 12 ───┘
```

- 32 hexadecimal characters in 5 groups separated by hyphens
- Case-insensitive (the extension normalizes to uppercase for lookup)
- In HSL source, hyphens are replaced with underscores

---

## Complete Step Type Registry

### Single-Channel Steps (1000µL / 5mL Channels)

| CLSID | Step Type | Description |
|---|---|---|
| `1C0C0CB0-7C87-11D3-AD83-0004ACB1DCB2` | **Initialize** | Initialize the ML_STAR instrument hardware |
| `541143F5-7FA2-11D3-AD85-0004ACB1DCB2` | **Aspirate** | Aspirate liquid with individual channels |
| `541143F8-7FA2-11D3-AD85-0004ACB1DCB2` | **Dispense** | Dispense liquid with individual channels |
| `541143FA-7FA2-11D3-AD85-0004ACB1DCB2` | **TipPickUp** | Pick up disposable tips with individual channels |
| `541143FC-7FA2-11D3-AD85-0004ACB1DCB2` | **TipEject** | Eject disposable tips from individual channels |
| `54114400-7FA2-11D3-AD85-0004ACB1DCB2` | **UnloadCarrier** | Unload a carrier from the autoload rail |
| `54114402-7FA2-11D3-AD85-0004ACB1DCB2` | **LoadCarrier** | Load a carrier onto the autoload rail |
| `EA251BFB-66DE-48D1-83E5-6884B4DD8D11` | **MoveAutoLoad** | Move the autoload mechanism |
| `9FB6DFE0-4132-4D09-B502-98C722734D4C` | **GetLastLiquidLevel** | Retrieve the last detected liquid level (from LLD) |

### CO-RE 96 Head Steps

| CLSID | Step Type | Description |
|---|---|---|
| `BD0D210B-0816-4C86-A903-D6B2DF73F78B` | **Head96TipPickUp** | Pick up 96 tips simultaneously with the 96-head |
| `827392A0-B7E8-4472-9ED3-B45B71B5D27A` | **Head96Aspirate** | Aspirate with all 96 channels simultaneously |
| `A48573A5-62ED-4951-9EF9-03207EFE34FB` | **Head96Dispense** | Dispense with all 96 channels simultaneously |
| `2880E77A-3D6D-40FE-AF57-1BD1FE13960C` | **Head96TipEject** | Eject 96 tips simultaneously |

### Easy Aspirate/Dispense Steps (Simplified 96-Head)

| CLSID | Step Type | Description |
|---|---|---|
| `E294A9A7-BEFC-4000-9A4C-926B91B8DE1C` | **EasyHead96Aspirate** | Simplified 96-head aspirate (fewer configurable parameters) |
| `7DE53592-BBE5-4F1D-B657-161F1AAECA3E` | **EasyHead96Dispense** | Simplified 96-head dispense (fewer configurable parameters) |

---

## CLSID Family Patterns

The CLSIDs reveal grouping patterns in their structure:

### Early COM Registration (pre-2000)

The single-channel CLSIDs `541143Fx...` and `1C0C0CB0...` share the suffix pattern `7FA2-11D3-AD85-0004ACB1DCB2` (or similar), indicating they were registered as a batch during early Hamilton VENUS development. The sequential nature of the first segment (`F5`, `F8`, `FA`, `FC`, `00`, `02`) confirms they were registered together.

### Later COM Registration

The 96-head CLSIDs (`827392A0...`, `A48573A5...`, `BD0D210B...`, `2880E77A...`) have fully random GUIDs, indicating they were registered independently at a later date when the CO-RE 96 head was added.

### Easy Steps

The Easy Aspirate/Dispense CLSIDs (`E294A9A7...`, `7DE53592...`) are similarly random, added when Hamilton introduced the simplified step dialogs.

---

## Step Type Classification

Steps can be classified by their parameter structure:

| Category | Step Types | Parameter Group Marker |
|---|---|---|
| **Aspirate** | Aspirate, Head96Aspirate, EasyHead96Aspirate | Has aspirate volume field (`-534183924`) |
| **Dispense** | Dispense, Head96Dispense, EasyHead96Dispense | Has dispense volume field (`-534183908`) |
| **Tip Management** | TipPickUp, TipEject, Head96TipPickUp, Head96TipEject | Channel pattern and sequence only |
| **Carrier/Transport** | LoadCarrier, UnloadCarrier, MoveAutoLoad | Minimal parameter set |
| **Query** | GetLastLiquidLevel | Returns data, minimal configuration |
| **System** | Initialize | System-level initialization |

---

## How to Identify a Step in HSL Code

Given an HSL line like:

```hsl
arrRetValues = ML_STAR._541143F5_7FA2_11D3_AD85_0004ACB1DCB2("a1b2c3d4_e5f6_7890_abcdef1234567890");
```

1. **Extract the CLSID**: `541143F5_7FA2_11D3_AD85_0004ACB1DCB2`
2. **Look up the step type**: `541143F5...` → **Aspirate**
3. **Extract the instance GUID**: `a1b2c3d4_e5f6_7890_abcdef1234567890`
4. **Find the `.stp` file** with the same base name as the `.hsl` file
5. **Locate the HxPars section** keyed by the instance GUID
6. **Read the parameters** from the token stream

The trailing comment `// StepName` is inserted by the Method Editor for readability but is not authoritative — the CLSID is the source of truth for step type identification.

---

## Regex Pattern for Matching

The VS Code extension uses this regex to identify device step calls in HSL code:

```regex
(\w+)\._([0-9A-Fa-f]{8}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{12})\s*\(\s*"([0-9a-f_]+)"\s*\)
```

Capture groups:
1. Device variable name (e.g., `ML_STAR`)
2. CLSID in underscore format
3. Step instance GUID
