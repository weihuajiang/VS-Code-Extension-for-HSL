#!/usr/bin/env python3
"""Quick test of backward compat + layout file support."""

import glob
from pathlib import Path
from hxcfgfile_codec import (
    parse_binary_med, build_binary_med, build_text_med, parse_text_med,
    HxCfgTextModel, NamedSection, HxParsSection,
)

# Test backward compat: old-style constructor with named_section= (singular)
m1 = HxCfgTextModel(
    named_section=NamedSection(name="Method,Properties", key="ReadOnly", value="0"),
    hxpars_sections=[HxParsSection(key="Method", tokens=["a", "b"])],
    footer_line="* $$author=TEST$$valid=0$$time=now$$checksum=0$$length=001$$",
)
assert m1.named_section is not None
assert m1.named_section.name == "Method,Properties"
assert m1.named_section.key == "ReadOnly"
assert m1.named_section.value == "0"
assert len(m1.named_sections) == 1
assert m1.hxpars_sections[0].key == "Method"
assert m1.hxpars_sections[0].prefix == "HxPars"
assert m1.hxpars_sections[0].version == 3
assert m1.activity_document_b64 == ""
print("Old-style constructor: PASS")

# Test new-style constructor with named_sections= (plural)
m2 = HxCfgTextModel(
    named_sections=[
        NamedSection(name="A,B", key="k1", value="v1"),
        NamedSection(name="C,D", key="k2", value="v2", field_type=5),
    ],
    hxpars_sections=[],
    footer_line="* $$author=TEST$$valid=0$$time=now$$checksum=0$$length=001$$",
)
assert m2.named_section.name == "A,B"
assert len(m2.named_sections) == 2
assert m2.named_sections[1].field_type == 5
print("New-style constructor (plural): PASS")

# Test no named section
m3 = HxCfgTextModel(
    hxpars_sections=[],
    footer_line="* $$author=TEST$$",
)
assert m3.named_section is None
assert len(m3.named_sections) == 0
print("No named section: PASS")

# Test NamedSection.all_fields with extra_fields
ns = NamedSection(name="X,Y", key="k1", value="v1", field_type=5,
                  extra_fields=[("k2", "v2"), ("k3", "v3")])
assert ns.all_fields == [("k1", "v1"), ("k2", "v2"), ("k3", "v3")]
print("all_fields: PASS")

# Test .stp roundtrip
stp_files = glob.glob(
    r"C:\Program Files (x86)\Hamilton\Methods\HSLBarcodedNTRLibrary\**\*.stp",
    recursive=True,
)
stp_pass = stp_fail = 0
for f in stp_files[:5]:
    try:
        orig = Path(f).read_bytes()
        model = parse_binary_med(orig)
        rebuilt = build_binary_med(model)
        if orig == rebuilt:
            stp_pass += 1
        else:
            stp_fail += 1
            print(f"  STP roundtrip FAIL: {Path(f).name}")
    except Exception as e:
        stp_fail += 1
        print(f"  STP error: {Path(f).name}: {e}")
print(f"STP roundtrip: {stp_pass} pass, {stp_fail} fail (of {min(5, len(stp_files))} tested)")

# Test .lay roundtrip
lay = Path(
    r"C:\Program Files (x86)\Hamilton\Methods\HSLBarcodedNTRLibrary"
    r"\2- Rack Definition and 96 with qcg in Venus"
    r"\NTR Rack Layout Example.lay"
)
if lay.exists():
    orig = lay.read_bytes()
    model = parse_binary_med(orig)
    rebuilt = build_binary_med(model)
    assert orig == rebuilt, "Binary roundtrip failed"
    text = build_text_med(model)
    model2 = parse_text_med(text)
    rebuilt2 = build_binary_med(model2)
    assert orig == rebuilt2, "Text roundtrip failed"
    print(f"LAY roundtrip: PASS ({len(model.named_sections)} named, "
          f"{len(model.hxpars_sections)} hxpars)")
else:
    print("LAY file not found, skipping")

# Test text roundtrip of old-style model (binary -> text -> binary)
bin1 = build_binary_med(m1)
model_rt = parse_binary_med(bin1)
assert model_rt.named_section.key == "ReadOnly"
text_rt = build_text_med(model_rt)
model_rt2 = parse_text_med(text_rt)
bin2 = build_binary_med(model_rt2)
assert bin1 == bin2, "Old-style model roundtrip failed"
print("Old-style model full roundtrip: PASS")

print("\nALL TESTS PASSED")
