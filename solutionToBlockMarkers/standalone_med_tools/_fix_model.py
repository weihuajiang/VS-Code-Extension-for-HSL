#!/usr/bin/env python3
"""Temporary script to update HxCfgTextModel in standalone hxcfgfile_codec.py"""
import pathlib

p = pathlib.Path(__file__).parent / "hxcfgfile_codec.py"
content = p.read_text(encoding="utf-8")

# Find the exact block to replace
start_marker = "the text parser / emitter.  It captures:"
end_marker = 'return ""'

start_idx = content.find(start_marker)
# Find the return "" after activity_document_b64 (not the first one)
search_from = content.find("activity_document_b64", start_idx)
end_idx = content.find(end_marker, search_from)
if end_idx > 0:
    end_idx += len(end_marker)

if start_idx < 0 or end_idx <= start_idx:
    print(f"FAIL: start={start_idx}, end={end_idx}")
    raise SystemExit(1)

old_block = content[start_idx:end_idx]
print(f"Found block: {start_idx} to {end_idx} ({len(old_block)} chars)")

new_block = (
    'the text parser / emitter.  It captures:\n'
    '\n'
    '    * Zero or more :class:`NamedSection` entries (one for .med/.stp files;\n'
    '      multiple for .lay files).\n'
    '    * Zero or more :class:`HxParsSection` entries with their tokens.\n'
    '    * The footer metadata line (``* $$author=... $$``).\n'
    '\n'
    '    Accepts either ``named_section`` (singular, for backward compat) or\n'
    '    ``named_sections`` (plural, for .lay files with multiple sections).\n'
    '\n'
    '    Attributes:\n'
    '        named_sections:  Ordered list of named sections.\n'
    '        hxpars_sections: Ordered list of HxPars parameter sections.\n'
    '        footer_line:     The metadata footer string (without trailing newline).\n'
    '    """\n'
    '\n'
    '    def __init__(\n'
    '        self,\n'
    '        *,\n'
    '        named_sections: List[NamedSection] | None = None,\n'
    '        named_section: NamedSection | None = None,\n'
    '        hxpars_sections: List[HxParsSection],\n'
    '        footer_line: str,\n'
    '    ):\n'
    '        if named_sections is not None:\n'
    '            self.named_sections: List[NamedSection] = named_sections\n'
    '        elif named_section is not None:\n'
    '            self.named_sections = [named_section]\n'
    '        else:\n'
    '            self.named_sections = []\n'
    '        self.hxpars_sections = hxpars_sections\n'
    '        self.footer_line = footer_line\n'
    '\n'
    '    @property\n'
    '    def named_section(self) -> NamedSection | None:\n'
    '        """Backward-compat: return the first named section, or None."""\n'
    '        return self.named_sections[0] if self.named_sections else None\n'
    '\n'
    '    @property\n'
    '    def activity_document_b64(self) -> str:\n'
    '        """Return the ActivityDocument base-64 value, or ``""`` if absent.\n'
    '\n'
    '        This is a convenience accessor for .med files.  If the named section\n'
    '        does not exist, or is not an ActivityData section, an empty string is\n'
    '        returned.\n'
    '        """\n'
    '        ns = self.named_section\n'
    '        if ns and ns.name == ACTIVITY_SECTION_NAME:\n'
    '            return ns.value\n'
    '        return ""'
)

content = content[:start_idx] + new_block + content[end_idx:]
p.write_text(content, encoding="utf-8")
print("SUCCESS: HxCfgTextModel replaced")
