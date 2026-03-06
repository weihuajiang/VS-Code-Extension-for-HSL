# 03 — Field ID Mapping

This document provides the complete mapping of numeric field IDs found in `.stp` binary files to their human-readable parameter names, data types, and physical units.

---

## Field ID Encoding

Inside an `.stp` token stream, device-specific parameters are encoded using **negative integer field IDs** rather than human-readable names. A token key like `5-534183924` encodes two pieces of information:

| Component | Example | Meaning |
|---|---|---|
| **Type prefix** | `5` | Value type: `1` = string, `3` = integer, `5` = float |
| **Field ID** | `-534183924` | Parameter identifier (always negative) |

So the token pair `"5-534183924" "150"` means:
- Field ID: `-534183924`
- Type: float (prefix `5`)
- Value: `150`
- Meaning: **Aspirate Volume = 150 µL**

---

## Named String Fields

These fields use human-readable string keys (not numeric IDs) and appear as top-level tokens in each step section:

| Token Key | Type | Description | Example Value |
|---|---|---|---|
| `1StepName` | string | Step type display name | `"Aspirate"`, `"Head96Aspirate"` |
| `1CommandStepFileGuid` | string | GUID linking to step definition | `"{827392A0-...}"` |
| `1SequenceObject` | string | Target labware sequence | `"ML_STAR.Cells"` |
| `1SequenceName` | string | Sequence name (usually = SequenceObject) | `"ML_STAR.Cells"` |
| `1LiquidName` | string | Liquid class name | `"HighVolumeFilter_96COREHead..."` |
| `1ChannelPattern` | string | Per-channel enable mask | `"11111111"` (8 channels enabled) |
| `1Timestamp` | string | Last modification timestamp | `"2024-01-15 10:30:00"` |
| `3SequenceCounting` | int | Sequence position mode | `0` = Manually, `1` = Automatic |
| `3LiquidFollowing` | int | Tip follows liquid surface | `0` = Off, `1` = On |
| `3TipType` | int | Disposable tip type identifier | Numeric ID |
| `3DispenseMode` | int | Dispense behavior mode | `3` = Jet, `4` = Surface Empty, `5` = Drain Tip |
| `3UsePickUpPosition` | int | Tip eject target | `0` = Default, `1` = Pick-up position, `2` = Default waste |
| `3SameLiquid` | int | Reuse aspirate liquid class | `0` = No, `1` = Yes |
| `3TouchOffMode` | int | Touch-off behavior | Numeric code |
| `3SideTouchMode` | int | Side touch behavior | Numeric code |

---

## Numeric Field ID Table — Complete Reference

These are the negative-integer field IDs that appear inside parameter groups (`-534183935` for 96-head, `-534183936` for single-channel).

### Aspirate Parameters

| Field ID | Type Prefix | Parameter Name | Unit | Range / Values |
|---|---|---|---|---|
| `-534183924` | `5` (float) | **Aspirate Volume** | µL | 0–1000 (1000µL tips), 0–5000 (5mL tips) |
| `-534183918` | `5` (float) | **Pressure LLD Sensing** | — | Internal pressure threshold |
| `-534183933` | `3` (int) | **cLLD Sensitivity** | — | Capacitive LLD sensitivity level |

### Dispense Parameters

| Field ID | Type Prefix | Parameter Name | Unit | Range / Values |
|---|---|---|---|---|
| `-534183908` | `5` (float) | **Dispense Volume** | µL | 0–1000 or 0–5000 |
| `-534183909` | `3` (int) | **Dispense Position Above Z-Start** | mm | Distance above Z-start for dispense positioning |

### Shared Aspirate/Dispense Parameters

| Field ID | Type Prefix | Parameter Name | Unit | Range / Values |
|---|---|---|---|---|
| `-534183915` | `5` (float) | **Mix Volume** | µL | 0 to tip capacity |
| `-534183914` | `3` (int) | **Mix Cycles** | count | 0 = no mixing, typically 1–10 |
| `-534183925` | `5` (float) | **Mix Position from Liquid Surface** | mm | Offset from detected liquid surface |
| `-534183913` | `5` (float) | **Submerge Depth** | mm | Depth below liquid surface for aspiration/dispensing |
| `-534183919` | `3` (int) | **LLD Mode** | enum | `0` = Off, `1` = pLLD (Pressure), `5` = Capacitive |
| `-534183928` | `5` (float) | **LLD Sensitivity** | 1–5 scale | Higher = more sensitive |
| `-534183622` | `5` (float) | **Retract Distance from Surface** | mm | Distance to retract after liquid transfer |
| `-534183629` | `5` (float) | **Side Touch** | — | `0` = Off, non-zero = enabled |
| `-534183926` | `5` (float) | **Retract Speed** | — | Speed of tip retraction |
| `-534183920` | `3` (int) | **Swap Speed** | — | Speed for swap movement |
| `-534183700` | `5` (float) | **Pressure LLD Sensitivity** | — | Sensitivity for pressure-based LLD |
| `-534183876` | `3` (int) | **Channel Enable** | bool | `1` = channel is active, `0` = disabled |
| `-534183813` | `3` (int) | **Touch Off Distance** | mm | Distance for touch-off movement |

### Group Markers

| Field ID | Type | Purpose |
|---|---|---|
| `-534183935` | group | **CO-RE 96 Head parameter group** — flat key-value pairs |
| `-534183936` | group | **Single-channel parameter group** — contains per-channel sub-groups |

---

## Enumerated Value Lookup Tables

### LLD Mode (`-534183919`)

| Value | Meaning |
|---|---|
| `0` | Off — no liquid level detection |
| `1` | pLLD — pressure-based liquid level detection |
| `5` | Capacitive — capacitive liquid level detection |

### Dispense Mode (`3DispenseMode`)

| Value | Meaning |
|---|---|
| `3` | Jet — dispense above the liquid surface with high speed |
| `4` | Surface Empty — dispense at the liquid surface until tip is empty |
| `5` | Drain Tip in Jet Mode — jet dispense followed by tip drainage |

### Sequence Counting (`3SequenceCounting`)

| Value | Meaning |
|---|---|
| `0` | Manually — positions do not auto-advance; code must manage position |
| `1` | Automatic — sequence position advances after each step execution |

### Tip Eject Position (`3UsePickUpPosition`)

| Value | Meaning |
|---|---|
| `0` | Default position |
| `1` | Return to pick-up position |
| `2` | Default waste position |

### Liquid Following (`3LiquidFollowing`)

| Value | Meaning |
|---|---|
| `0` | Off — tip stays at fixed Z position during transfer |
| `1` | On — tip follows the receding/advancing liquid surface. Requires LLD to be active. |

---

## Parameter Applicability by Step Type

Not all fields appear in every step type. This table shows which fields are relevant:

| Field | Aspirate | Dispense | TipPickUp | TipEject | Initialize |
|---|---|---|---|---|---|
| Aspirate Volume | ✓ | — | — | — | — |
| Dispense Volume | — | ✓ | — | — | — |
| Mix Volume / Cycles | ✓ | ✓ | — | — | — |
| Submerge Depth | ✓ | ✓ | — | — | — |
| LLD Mode / Sensitivity | ✓ | ✓ | — | — | — |
| Liquid Class | ✓ | ✓* | — | — | — |
| Liquid Following | ✓ | ✓ | — | — | — |
| Retract Distance | ✓ | ✓ | — | — | — |
| Channel Pattern | ✓ | ✓ | ✓ | ✓ | — |
| Sequence Object | ✓ | ✓ | ✓ | ✓ | — |
| Dispense Mode | — | ✓ | — | — | — |
| Eject Position | — | — | — | ✓ | — |
| Channel Enable | ✓ | ✓ | ✓ | ✓ | — |

*\* Dispense can inherit the aspirate step's liquid class via `3SameLiquid = 1`*

---

## Example: Decoded 96-Head Aspirate

Raw token stream from `.stp`:

```
"1StepName"          "Head96Aspirate"
"1SequenceObject"    "ML_STAR.Cells"
"1SequenceName"      "Cells"
"3SequenceCounting"  "0"
"1LiquidName"        "HighVolumeFilter_96COREHead1000ul_Water_DispenseSurface_Empty"
"(-534183935"
  "5-534183924"      "150"
  "3-534183914"      "4"
  "5-534183915"      "150"
  "5-534183925"      "0"
  "5-534183913"      "2"
  "3-534183919"      "5"
  "5-534183928"      "5"
  "5-534183622"      "10"
  "3LiquidFollowing" "1"
")"
```

Decoded:

| Parameter | Value |
|---|---|
| **Step Name** | Head96Aspirate |
| **Sequence** | ML_STAR.Cells (counting: Manually) |
| **Liquid Class** | HighVolumeFilter_96COREHead1000ul_Water_DispenseSurface_Empty |
| **Aspirate Volume** | 150 µL |
| **Mix Cycles** | 4 |
| **Mix Volume** | 150 µL |
| **Mix Position from Surface** | 0 mm |
| **Submerge Depth** | 2 mm |
| **LLD Mode** | Capacitive |
| **LLD Sensitivity** | 5 |
| **Retract Distance** | 10 mm |
| **Liquid Following** | On |
