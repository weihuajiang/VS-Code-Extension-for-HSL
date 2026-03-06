# Hamilton HSL — Pipetting Step Reference

This VS Code extension supports Hamilton Standard Language (HSL) files for Hamilton liquid-handling robots. This document explains how pipetting steps are encoded in HSL code and companion `.stp` files so that an LLM can interpret, validate, and explain them.

---

## How Pipetting Steps Appear in HSL Code

Device steps appear as function calls on a device object (typically `ML_STAR`). The format is:

```
ML_STAR._<CLSID>("stepInstanceGuid"); // StepName
```

- **CLSID**: A COM class identifier (underscore-formatted GUID) that identifies the **step type** (e.g., Aspirate, Dispense).
- **stepInstanceGuid**: A unique instance identifier that maps to the step's parameters stored in the companion `.stp` file.

The HSL code itself does **not** contain the pipetting parameters (volume, liquid class, LLD settings, etc.). All parameters are stored in the binary `.stp` file, keyed by the `stepInstanceGuid`.

### Step Type CLSIDs

| CLSID (underscore format) | Step Type |
|---|---|
| `1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2` | Initialize |
| `541143F5_7FA2_11D3_AD85_0004ACB1DCB2` | Aspirate (single channel) |
| `541143F8_7FA2_11D3_AD85_0004ACB1DCB2` | Dispense (single channel) |
| `541143FA_7FA2_11D3_AD85_0004ACB1DCB2` | TipPickUp (single channel) |
| `541143FC_7FA2_11D3_AD85_0004ACB1DCB2` | TipEject (single channel) |
| `54114400_7FA2_11D3_AD85_0004ACB1DCB2` | UnloadCarrier |
| `54114402_7FA2_11D3_AD85_0004ACB1DCB2` | LoadCarrier |
| `827392A0_B7E8_4472_9ED3_B45B71B5D27A` | Head96Aspirate (CO-RE 96) |
| `A48573A5_62ED_4951_9EF9_03207EFE34FB` | Head96Dispense (CO-RE 96) |
| `BD0D210B_0816_4C86_A903_D6B2DF73F78B` | Head96TipPickUp (CO-RE 96) |
| `2880E77A_3D6D_40FE_AF57_1BD1FE13960C` | Head96TipEject (CO-RE 96) |
| `EA251BFB_66DE_48D1_83E5_6884B4DD8D11` | MoveAutoLoad |

---

## .stp File Structure

The `.stp` file is a binary HxCfgFile v3 container. Each step instance has a section keyed by its GUID containing token pairs (key, value). Parameters fall into two categories:

### Named String/Integer Fields

| Key | Type | Description |
|---|---|---|
| `1StepName` | string | Step type name (e.g., "Aspirate", "Head96Aspirate") |
| `1SequenceObject` | string | Target sequence (e.g., "ML_STAR.Cells") |
| `1SequenceName` | string | Sequence name (usually same as SequenceObject) |
| `1LiquidName` | string | Liquid class name. Empty on dispense means "same as aspirate" |
| `1ChannelPattern` | string | Channel enable mask (e.g., "11111111" for 8 channels) |
| `3SequenceCounting` | int | 0 = Manually, 1 = Automatic |
| `3LiquidFollowing` | int | 0 = Off, 1 = On (pipette tip follows liquid surface) |
| `3TipType` | int | Tip type identifier |
| `3DispenseMode` | int | 3 = Jet, 4 = Surface Empty, 5 = Drain Tip |
| `3UsePickUpPosition` | int | TipEject: 0 = Default, 1 = Pick-up position, 2 = Default waste |
| `3SameLiquid` | int | 1 = Use same liquid class as aspirate |

### Numeric Field IDs (inside parameter groups)

These fields are in a parenthesized group: `(-534183935 ...)` for CO-RE 96 head steps, or `(-534183936 ...)` for single-channel steps (repeated per channel).

| Field ID | Type | Parameter | Unit |
|---|---|---|---|
| `-534183924` | float | **Aspirate Volume** | µL |
| `-534183908` | float | **Dispense Volume** | µL |
| `-534183915` | float | **Mix Volume** | µL |
| `-534183914` | int | **Mix Cycles** | count |
| `-534183925` | float | **Mix Position from Liquid Surface** | mm |
| `-534183913` | float | **Submerge Depth** (position relative to liquid surface) | mm |
| `-534183919` | int | **LLD Mode**: 0 = Off, 1 = pLLD (Pressure), 5 = Capacitive | enum |
| `-534183928` | float | **LLD Sensitivity** | 1-5 scale |
| `-534183918` | float | **Pressure LLD Sensing** | — |
| `-534183933` | int | **cLLD Sensitivity** | — |
| `-534183622` | float | **Retract Distance from Surface** | mm |
| `-534183629` | float | **Side Touch** (0 = off) | — |
| `-534183926` | float | **Retract Speed** | — |
| `-534183920` | int | **Swap Speed** | — |
| `-534183700` | float | **pLLD Sensitivity** | — |
| `-534183876` | int | **Channel Enable** (1 = enabled) | bool |
| `-534183813` | int | **Touch Off Distance** | — |
| `-534183909` | int | **Dispense Position Above Z-Start** | — |

---

## How to Interpret a Pipetting Step

When you see a line like:
```hsl
arrRetValues = ML_STAR._827392A0_B7E8_4472_9ED3_B45B71B5D27A("89a59053_b35c_4f52_8b2411eb1cf98914"); // Head96Aspirate
```

1. **Identify the step type** from the CLSID: `827392A0...` = `Head96Aspirate`
2. **Look up the instance GUID** `89a59053...` in the `.stp` file
3. **Read the parameters**: sequence, liquid class, volume, mix settings, LLD mode, etc.

### Example Decoded Step

For the step above, the `.stp` file contains:
- **Sequence:** ML_STAR.Cells (counting: Manually)
- **Liquid Class:** HighVolumeFilter_96COREHead1000ul_Water_DispenseSurface_Empty
- **Aspirate Volume:** 150 µL
- **Mix:** 150 µL × 4 cycles
- **Submerge Depth:** 2 mm
- **LLD:** Capacitive, Sensitivity: 5
- **Liquid Following:** On

---

## Common Validation Checks

When reviewing pipetting steps, check for these potential issues:

1. **Volume out of range**: Aspirate/dispense volumes should be within the tip type's capacity (e.g., 0-1000 µL for 1000 µL tips, 0-5000 µL for 5 mL tips).
2. **Mix volume vs aspirate volume**: Mix volume should generally be ≤ the tip capacity and appropriate for the vessel.
3. **Mix cycles = 0 with non-zero mix volume**: Likely an error — mix won't execute without cycles.
4. **LLD off with submerge depth**: If LLD is off, the submerge depth is relative to container bottom, not liquid surface. Verify this is intentional.
5. **Empty liquid class on aspirate**: Aspirate steps should always have a liquid class specified.
6. **Dispense volume ≠ aspirate volume**: Unless performing partial dispenses, these should usually match within a pipetting cycle.
7. **Sequence counting mismatch**: If a sequence is set to "Manually" but inside a loop without manual position management, positions won't advance.
8. **Liquid following without LLD**: Liquid following requires LLD to detect the surface; having it on without LLD is unusual though not always wrong.
