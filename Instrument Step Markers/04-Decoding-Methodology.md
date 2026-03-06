# 04 — Decoding Methodology

This document describes how we reverse-engineered the numeric field IDs in Hamilton `.stp` files — the step-by-step process of turning opaque negative integers into meaningful pipetting parameter names.

---

## The Problem

Hamilton's `.stp` files store device step parameters using **negative integer field IDs** rather than human-readable names. A raw token stream looks like this:

```
"5-534183924"  "150"
"3-534183914"  "4"
"5-534183915"  "150"
"3-534183919"  "5"
"5-534183928"  "5"
"5-534183913"  "2"
```

There is no public documentation mapping these field IDs to parameter names. Hamilton's Method Editor handles the translation internally through COM objects. To build tooling that can read these parameters outside the Method Editor, we needed to determine what each field ID means.

---

## Approach: Cross-Reference Known Parameters with Binary Values

The core strategy was to find a method where we knew the exact parameter values (from a human-readable description or the Method Editor GUI), then parse the binary `.stp` file and match values to field IDs by elimination.

### Step 1: Find a Method with Known Parameters

We used the "Stamping Cells to Plates" method, which included a plain-text description file (`Plain Text Method.txt`) documenting every step's parameters in human-readable form:

```
Step 3: Head96Aspirate
  Sequence: ML_STAR.Cells
  Volume: 150 µL
  Liquid Class: HighVolumeFilter_96COREHead1000ul_Water_DispenseSurface_Empty
  Mix: 150 µL × 4 cycles
  Submerge Depth: 2 mm
  LLD: Capacitive, Sensitivity: 5
  Liquid Following: On
```

This gave us a **ground truth** to match against.

### Step 2: Parse the Binary .stp File

Using the existing `hxcfgfile_codec.py` Python tool (in `solutionToBlockMarkers/`), we converted the binary `.stp` file to its text representation:

```bash
python hxcfgfile_codec.py decode "Stamping Cells to Plates.stp"
```

This produced the full token stream for every step section, including the one keyed by the Head96Aspirate instance GUID `89a59053_b35c_4f52_8b2411eb1cf98914`.

### Step 3: Identify the Target Step Section

From the HSL code, we found the device step call:

```hsl
arrRetValues = ML_STAR._827392A0_B7E8_4472_9ED3_B45B71B5D27A("89a59053_b35c_4f52_8b2411eb1cf98914");
```

The CLSID `827392A0...` identified this as a `Head96Aspirate` step. The instance GUID `89a59053...` was the key into the `.stp` file.

### Step 4: Extract the Numeric Fields

Inside the `89a59053...` section, we found a group opened by `(-534183935` (the 96-head parameter group marker) containing these key-value pairs:

| Token Key | Token Value |
|---|---|
| `5-534183924` | `150` |
| `3-534183914` | `4` |
| `5-534183915` | `150` |
| `5-534183925` | `0` |
| `5-534183913` | `2` |
| `3-534183919` | `5` |
| `5-534183928` | `5` |
| `5-534183622` | `10` |
| `5-534183629` | `0` |
| `5-534183926` | `5` |
| `3-534183920` | `4` |
| `5-534183700` | `4` |

### Step 5: Match Values to Known Parameters

Using the plain text reference, we matched by value and elimination:

| Known Parameter | Known Value | Matching Field ID | Reasoning |
|---|---|---|---|
| **Aspirate Volume** | 150 µL | `-534183924` | Value `150`, float type — volume is always float |
| **Mix Volume** | 150 µL | `-534183915` | Also `150`, but different field ID — second occurrence of 150 |
| **Mix Cycles** | 4 | `-534183914` | Value `4`, integer type — cycles are always integer |
| **Submerge Depth** | 2 mm | `-534183913` | Value `2`, float type — depth is always float |
| **LLD Mode** | Capacitive | `-534183919` | Value `5`, integer type — maps to Capacitive enum |
| **LLD Sensitivity** | 5 | `-534183928` | Value `5`, float type — sensitivity scale |
| **Retract Distance** | 10 mm | `-534183622` | Value `10`, float type — only remaining distance field |
| **Side Touch** | Off | `-534183629` | Value `0` — zero means off |
| **Retract Speed** | 5 | `-534183926` | Float, remaining after matching |
| **Swap Speed** | 4 | `-534183920` | Integer, remaining after matching |
| **pLLD Sensitivity** | 4 | `-534183700` | Float, pressure LLD related |
| **Mix Position** | 0 mm | `-534183925` | Value `0`, float — position from surface |

### Step 6: Disambiguate Volume vs. Mix Volume

Both Aspirate Volume and Mix Volume had the value `150`. The disambiguation came from:

1. **Type prefix analysis**: Both used prefix `5` (float), so type didn't help
2. **Ordering within the .stp GUI hierarchy**: Hamilton's step dialog shows volume before mix settings
3. **Cross-referencing with a dispense step**: The corresponding dispense step had field ID `-534183908` with the dispense volume, while `-534183924` appeared only in aspirate steps — confirming `-534183924` = Aspirate Volume

### Step 7: Validate with Dispense Step

We repeated the analysis on the Head96Dispense step from the same method (GUID `26a0d83b...`):

| Known Parameter | Known Value | Field ID | Confirmed? |
|---|---|---|---|
| **Dispense Volume** | 150 µL | `-534183908` | ✓ New field ID (dispense-specific) |
| **Dispense Mode** | Surface Empty | `3DispenseMode` = `4` | ✓ Named field, not numeric ID |
| **Mix Volume** | 0 µL | `-534183915` = `0` | ✓ Same field ID as aspirate |
| **Mix Cycles** | 0 | `-534183914` = `0` | ✓ Same field ID as aspirate |
| **Submerge Depth** | 2 mm | `-534183913` = `2` | ✓ Same field ID |
| **LLD Mode** | Off | `-534183919` = `0` | ✓ Same field ID, value `0` = Off |

This confirmed the mapping was consistent across step types.

### Step 8: Cross-Validate with Single-Channel Steps

We parsed a second method (`schedulerDemo.stp`) containing single-channel Aspirate and Dispense steps. Single-channel steps use the group marker `(-534183936` instead of `(-534183935`, with per-channel sub-groups. Inside each sub-group, the same field IDs appeared:

```
(-534183936
  (3
    5-534183924   100      ← Aspirate Volume (same field ID!)
    3-534183919   1        ← LLD Mode = pLLD (same field ID!)
    3-534183876   1        ← Channel Enable (new field!)
  )
  ...
)
```

This confirmed:
- Field IDs are **shared between 96-head and single-channel** steps
- The group marker (`-534183935` vs `-534183936`) is the only structural difference
- New field `-534183876` = Channel Enable (boolean per channel)

---

## Discovery of LLD Mode Values

The LLD Mode field (`-534183919`) was decoded by observing its values across multiple steps:

| Method / Step | LLD Setting (from GUI/text) | Field Value |
|---|---|---|
| Stamping Cells / Head96Aspirate | Capacitive | `5` |
| Stamping Cells / Head96Dispense | Off | `0` |
| schedulerDemo / Aspirate | Pressure (pLLD) | `1` |

This established the enum: `0` = Off, `1` = pLLD (Pressure), `5` = Capacitive.

The gap between `1` and `5` suggests values `2`, `3`, `4` may correspond to other LLD modes or combination modes not encountered in our sample set.

---

## Discovery of Group Markers

The group markers were identified by their structural role:

- `(-534183935` — Always opens the parameter block in CO-RE 96 head steps. Contains flat key-value pairs (all channels share identical settings).
- `(-534183936` — Always opens the parameter block in single-channel steps. Contains nested sub-groups `(3`, `(1`, etc., one per channel, because each channel can have independent parameters.

The integer `3` or `1` in the sub-group opener appears to be a type indicator, not a channel number. The channel index is implicit from the sub-group's ordinal position.

---

## Remaining Unknowns

Some field IDs were observed but not fully characterized due to limited sample data:

| Field ID | Observed Values | Best Guess | Confidence |
|---|---|---|---|
| `-534183813` | `0` | Touch Off Distance | Medium — appears in contexts near retract/touch settings |
| `-534183909` | `0` | Dispense Position Above Z-Start | Medium — appears only in dispense steps |

These mappings are included in the implementation but may benefit from validation against additional methods.

---

## Reproducibility

To repeat this analysis on a new method:

1. Obtain the `.hsl`, `.stp`, and optionally the plain-text parameter reference
2. Run `python hxcfgfile_codec.py decode <file>.stp` to get the text representation
3. Identify step instance GUIDs from the HSL code's device step calls
4. Find the corresponding HxPars section in the decoded `.stp` text
5. Match known parameter values to the numeric field IDs
6. Validate by checking consistency across multiple steps in the same method and across different methods

This approach can be used to discover field IDs for step types not yet documented (e.g., TADM steps, MPH steps, or instrument-specific commands).
