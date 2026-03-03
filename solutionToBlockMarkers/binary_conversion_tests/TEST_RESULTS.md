# HxCfgFilConverter Binary Conversion Test Results

## Scope

These tests were run against three real Hamilton method files:

1. `Visual_NTR_library_demo.med`
2. `Global_Answer_Key_CH07.med`
3. `Global_Example_Scheduled_Method_v01.med`

Using:

- Converter: `C:\Program Files (x86)\Hamilton\Bin\HxCfgFilConverter.exe`
- Harness: `run_binary_conversion_tests.ps1`

## Key Findings

- Whole-file **simple base64** hypothesis: **False** for all 3 files.
- Converter `/t` output starts with `HxCfgFile,3;` for all files.
- `ActivityDocument` field inside converted text is valid base64.
- Binary hash after `/t -> /b` does **not** equal original binary hash.
- Converted text is **exactly identical** after `/t -> /b -> /t`.

## Result Summary (from `final_summary.json`)

| Case | BinaryRoundtripExact | ConverterTextExactAfterRoundtrip | WholeFileIsSimpleBase64 | ActivityDocumentFieldIsBase64 |
|------|----------------------|----------------------------------|-------------------------|-------------------------------|
| Visual_NTR_library_demo | false | true | false | true |
| Global_Answer_Key_CH07 | false | true | false | true |
| Global_Example_Scheduled_Method_v01 | false | true | false | true |

## Interpretation

`HxCfgFilConverter.exe` is not a base64 encoder/decoder for the whole file. It is a parser/serializer for Hamilton's `HxCfgFile` container format.

- `/t` = binary container -> canonical text representation
- `/b` = text representation -> canonical binary representation

Byte-level binary identity is not guaranteed, but text-level semantic identity is stable under round-trip.
