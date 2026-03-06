# Instrument Step Markers

This directory documents **Instrument Step Markers** — the mechanism Hamilton uses to bind device commands in HSL source code to their full parameterization stored in binary `.stp` files.

---

## What Are Instrument Step Markers?

When you create a pipetting step (Aspirate, Dispense, Tip Pick-Up, etc.) in Hamilton's Method Editor, two things happen:

1. **A line of HSL code is generated** containing a device call with a COM class identifier (CLSID) and a unique instance GUID.
2. **A parameter record is written** into the companion `.stp` binary file, keyed by that same instance GUID.

The HSL line looks like this:

```hsl
arrRetValues = ML_STAR._827392A0_B7E8_4472_9ED3_B45B71B5D27A("89a59053_b35c_4f52_8b2411eb1cf98914"); // Head96Aspirate
```

The HSL source itself contains **none** of the pipetting parameters (volume, liquid class, LLD settings, mix cycles, etc.). All of those are stored in the `.stp` file in a binary token section keyed by the instance GUID `89a59053_b35c_4f52_8b2411eb1cf98914`.

This is what we call the **Instrument Step Marker** system.

---

## Why This Matters

- **The HSL code alone is incomplete.** Without the `.stp` file, you cannot know what volume is being aspirated, what liquid class is used, or any other device-step setting.
- **The `.stp` file alone is incomplete.** Without the HSL code, you cannot know in what order steps execute or what control flow surrounds them.
- **Together, they form the full picture** of a Hamilton method's device interactions.

Understanding this linkage is critical for:
- Code review and validation of pipetting protocols
- Automated method analysis and documentation generation
- Building IDE tooling (hover tooltips, diagnostics) that surfaces hidden parameters
- Migrating or debugging methods outside the Hamilton Method Editor

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [01 — Binary Format Specification](01-Binary-Format-Specification.md) | The HxCfgFile v3 binary container format used by `.stp` files, with byte-level structure |
| [02 — CLSID Registry](02-CLSID-Registry.md) | Complete registry of COM class identifiers mapping to Hamilton device step types |
| [03 — Field ID Mapping](03-Field-ID-Mapping.md) | All decoded numeric field IDs and their human-readable parameter names, types, and units |
| [04 — Decoding Methodology](04-Decoding-Methodology.md) | How we reverse-engineered the field ID mappings from binary data, step by step |
| [05 — TypeScript Implementation](05-TypeScript-Implementation.md) | The `stpHoverProvider.ts` implementation: binary parser, token extractor, tooltip formatter |

---

## Key Concepts

### The Three-Part Linkage

```
HSL Code (.hsl)          .stp Binary File           Method Editor GUI
┌──────────────────┐     ┌──────────────────────┐   ┌──────────────────┐
│ ML_STAR._<CLSID> │────>│ Section keyed by GUID │──>│ Step parameters  │
│   ("instanceGUID")│     │ - Volume: 150 µL     │   │ shown in the     │
│                  │     │ - Liquid Class: ...   │   │ step dialog      │
│                  │     │ - LLD Mode: 5         │   │                  │
│                  │     │ - Mix: 150 × 4        │   │                  │
└──────────────────┘     └──────────────────────┘   └──────────────────┘
     CLSID identifies           Parameters                Visual editor
     the step TYPE              by instance                representation
```

### CLSID (COM Class Identifier)

The CLSID embedded in the HSL function call identifies the **type** of device step. For example:
- `827392A0_B7E8_4472_9ED3_B45B71B5D27A` → CO-RE 96 Head Aspirate
- `541143F5_7FA2_11D3_AD85_0004ACB1DCB2` → Single-Channel Aspirate

### Instance GUID

The string argument to the device call is a unique identifier for that **specific step instance**. This GUID is the lookup key into the `.stp` file's HxPars sections.

### Token Pairs

Inside the `.stp` file, each step's parameters are stored as an ordered list of token strings. Tokens come in key-value pairs where:
- The key is a prefixed string like `1StepName`, `3TipType`, or `5-534183924`
- The prefix digit indicates the value type: `1` = string, `3` = integer, `5` = float
- Negative numeric field IDs (e.g., `-534183924`) encode device-specific parameters like volume, LLD mode, and submerge depth

---

## Quick Reference

For the impatient — here are the most important field IDs:

| Field ID | Parameter | Unit |
|----------|-----------|------|
| `-534183924` | Aspirate Volume | µL |
| `-534183908` | Dispense Volume | µL |
| `-534183915` | Mix Volume | µL |
| `-534183914` | Mix Cycles | count |
| `-534183919` | LLD Mode | 0=Off, 1=pLLD, 5=Capacitive |
| `-534183928` | LLD Sensitivity | 1–5 scale |
| `-534183913` | Submerge Depth | mm |
| `-534183622` | Retract Distance | mm |

See [03 — Field ID Mapping](03-Field-ID-Mapping.md) for the complete table.
