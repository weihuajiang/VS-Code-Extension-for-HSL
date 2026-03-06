import re
import html
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


# ----------------------------
# Data models
# ----------------------------
@dataclass
class ParamDoc:
    name: str
    direction: str
    type_desc: str
    description: str = ""


@dataclass
class FunctionDoc:
    name: str
    description_lines: list[str]
    return_type: str
    params: list[ParamDoc]


# ----------------------------
# Parsing helpers
# ----------------------------
TYPE_MAP_SINGULAR = {
    "variable": "Variable",
    "integer": "Integer",
    "string": "String",
    "real": "Real",
    "bool": "Boolean",
    "boolean": "Boolean",
}

TYPE_MAP_PLURAL = {
    "variable": "Variables",
    "integer": "Integers",
    "string": "Strings",
    "real": "Reals",
    "bool": "Booleans",
    "boolean": "Booleans",
}

DECORATIVE_RE = re.compile(r"^[\s\-\*=#_/\\]{6,}$")


def _safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\s]+', "_", name).strip("_") or "function"


def _extract_comment_block(lines: list[str], func_line_index: int) -> list[str]:
    """Grab contiguous // comment lines immediately above the function line."""
    block = []
    i = func_line_index - 1
    while i >= 0:
        s = lines[i].rstrip("\n")
        if s.strip() == "":
            if block:
                block.append(s)
            i -= 1
            continue

        stripped = s.lstrip()
        if stripped.startswith("//"):
            block.append(s)
            i -= 1
            continue

        if block:
            break

        i -= 1

    block.reverse()
    return block


def _clean_comment_lines(comment_block: list[str]) -> list[str]:
    cleaned = []
    for line in comment_block:
        s = line.strip()
        if not s.startswith("//"):
            if s == "":
                cleaned.append("")
            continue

        s = s[2:].strip()
        if s == "":
            cleaned.append("")
            continue

        if DECORATIVE_RE.match(s):
            continue

        cleaned.append(s)
    return cleaned


def _parse_param_descriptions_from_comments(cleaned_comment_lines: list[str]) -> dict[str, str]:
    """
    Supports:
      @param i_xxx description...
      param i_xxx description...
      i_xxx: description...
      i_xxx - description...
    """
    param_desc = {}

    atparam = re.compile(r"^(?:@param|param)\s+([A-Za-z_]\w*)\s*(.*)$", re.IGNORECASE)
    simple = re.compile(r"^([A-Za-z_]\w*)\s*[:\-]\s*(.+)$")

    for line in cleaned_comment_lines:
        m = atparam.match(line)
        if m:
            name, desc = m.group(1), m.group(2).strip()
            if desc:
                param_desc[name] = desc
            continue

        m = simple.match(line)
        if m:
            name, desc = m.group(1), m.group(2).strip()
            if name.startswith(("i_", "o_", "io_")) and desc:
                param_desc[name] = desc
            continue

    return param_desc


def _parse_description_from_comments(cleaned_comment_lines: list[str], func_name: str) -> list[str]:
    desc_lines = []
    skip_re = re.compile(rf"^\s*function\s+{re.escape(func_name)}\b", re.IGNORECASE)
    paramish_re = re.compile(r"^(?:@param|param)\s+[A-Za-z_]\w*", re.IGNORECASE)

    for line in cleaned_comment_lines:
        if line == "":
            if desc_lines and desc_lines[-1] != "":
                desc_lines.append("")
            continue

        if skip_re.match(line):
            continue
        if paramish_re.match(line):
            continue

        if re.match(r"^[A-Za-z_]\w*\s*[:\-]\s*.+$", line) and line.split()[0].startswith(("i_", "o_", "io_")):
            continue

        desc_lines.append(line)

    while desc_lines and desc_lines[-1] == "":
        desc_lines.pop()

    return desc_lines


def _find_matching_paren(text: str, open_index: int) -> int:
    depth = 0
    for i in range(open_index, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _infer_return_type_from_body(body: str) -> str | None:
    """
    If ANY return(...) contains TRUE/FALSE (incl. ASWGLOBAL::BOOL::TRUE), infer Boolean.
    """
    returns = re.findall(r"\breturn\s*\(\s*(.*?)\s*\)\s*;", body, flags=re.DOTALL | re.IGNORECASE)
    if not returns:
        return None

    norm_upper = [" ".join(r.strip().split()).upper() for r in returns]
    if any(("TRUE" in r or "FALSE" in r or "BOOL::" in r) for r in norm_upper):
        return "Boolean"

    return None


# ----------------------------
# Direction prefix helpers (NEW)
# ----------------------------
def _direction_tag(direction: str) -> str:
    d = direction.strip().lower()
    if d in ("in/out", "inout", "in-out"):
        return "[in/out]"
    if d == "out":
        return "[out]"
    return "[in]"


def _apply_direction_prefix(desc: str, direction: str) -> str:
    """
    Ensures the description starts with [in]/[out]/[in/out].
    If a bracket tag already exists at the start, replace it.
    """
    tag = _direction_tag(direction)
    desc = (desc or "").strip()

    # Remove any existing leading [something] tag
    desc = re.sub(r"^\[[^\]]+\]\s*", "", desc)

    if not desc:
        return tag

    return f"{tag} {desc}"


# ----------------------------
# Context-aware parameter description
# ----------------------------
CAMEL_WORD_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")

TYPE_CODE_MAP = {
    "str": "String",
    "int": "Integer",
    "bln": "Boolean",
    "bool": "Boolean",
    "real": "Real",
    "dbl": "Double",
    "var": "Variable",
}

CONTAINER_CODE_MAP = {
    "arr": "Array",
    "tbl": "Table",
    "lst": "List",
    "map": "Map",
    "dic": "Dictionary",
    "dct": "Dictionary",
    "hdl": "Handle",
    "obj": "Object",
}


def _singular_from_type_desc(type_desc: str) -> str:
    m = re.match(r"^Array of (.+)$", type_desc.strip(), re.IGNORECASE)
    if m:
        plural = m.group(1).strip()
        # very small singularizer
        if plural.endswith("ies"):
            return plural[:-3] + "y"
        if plural.endswith("s"):
            return plural[:-1]
        return plural
    return type_desc.strip() or "Value"


def _split_words(s: str) -> list[str]:
    s = s.strip("_")
    if not s:
        return []
    return [w for w in CAMEL_WORD_RE.findall(s) if w]


def _auto_param_description(param_name: str, direction: str, type_desc: str, is_array: bool) -> str:
    if direction == "In":
        dir_word = "Input"
    elif direction == "Out":
        dir_word = "Output"
    else:
        dir_word = "Input/Output"

    base = param_name
    if base.startswith("io_"):
        base = base[3:]
    elif base.startswith("i_"):
        base = base[2:]
    elif base.startswith("o_"):
        base = base[2:]

    # Detect container code at start
    container_word = None
    base_work = base
    code3 = base_work[:3].lower()
    if code3 in CONTAINER_CODE_MAP:
        cw = CONTAINER_CODE_MAP[code3]
        if cw == "Array":
            container_word = "Array"
            base_work = base_work[3:]
        else:
            # treat non-array container as a word prefix
            base_work = cw + base_work[3:]

    # Detect type code at start (3 or 4 letters)
    type_word = None
    for n in (4, 3):
        code = base_work[:n]
        if code and code.lower() in TYPE_CODE_MAP:
            type_word = TYPE_CODE_MAP[code.lower()]
            base_work = base_work[n:]
            break

    if not type_word:
        type_word = _singular_from_type_desc(type_desc)

    remainder_words = _split_words(base_work)
    if not remainder_words:
        remainder_words = ["Value"]

    parts = []
    if is_array or container_word == "Array":
        parts.append("Array")
    parts.append(dir_word)
    parts.append("of")
    parts.append(type_word)
    parts.extend(remainder_words)

    return " ".join(parts).strip()


def _parse_params(param_str: str, param_desc_map: dict[str, str]) -> list[ParamDoc]:
    parts = [p.strip() for p in param_str.split(",") if p.strip()]
    params: list[ParamDoc] = []

    for p in parts:
        p_flat = " ".join(p.replace("\n", " ").replace("\r", " ").replace("\t", " ").split())

        m = re.match(
            r"^(?P<type>[A-Za-z_]\w*(?:&)?)(?:\s*(?P<amp>&))?\s+(?P<name>[A-Za-z_]\w*)\s*(?P<array>\[\s*\])?(?:\s*=.*)?$",
            p_flat,
        )
        if not m:
            params.append(ParamDoc(name=p_flat, direction="In", type_desc="Unknown", description=""))
            continue

        raw_type = m.group("type") or ""
        amp2 = m.group("amp") or ""
        name = m.group("name")
        is_array = bool(m.group("array"))

        amp = raw_type.endswith("&") or bool(amp2)
        base_type = raw_type.rstrip("&").lower()

        if name.startswith("io_"):
            direction = "In/Out"
        elif name.startswith("o_"):
            direction = "Out"
        elif amp:
            direction = "Out"
        else:
            direction = "In"

        singular = TYPE_MAP_SINGULAR.get(base_type, base_type.capitalize() if base_type else "Unknown")
        plural = TYPE_MAP_PLURAL.get(base_type, singular + "s")
        type_desc = f"Array of {plural}" if is_array else singular

        desc = (param_desc_map.get(name, "") or "").strip()
        if not desc:
            desc = _auto_param_description(name, direction, type_desc, is_array)

        # NEW: Always prefix with [in]/[out]/[in/out]
        desc = _apply_direction_prefix(desc, direction)

        params.append(ParamDoc(name=name, direction=direction, type_desc=type_desc, description=desc))

    return params


def parse_hsl_functions(input_text: str) -> list[FunctionDoc]:
    lines = input_text.splitlines(True)
    joined = "".join(lines)

    func_line_indices = []
    for idx, line in enumerate(lines):
        if re.match(r"^\s*function\b", line) and not line.lstrip().startswith("//"):
            func_line_indices.append(idx)

    docs: list[FunctionDoc] = []

    for line_idx in func_line_indices:
        start_char = sum(len(lines[i]) for i in range(line_idx))

        mname = re.match(r"^\s*function\s+([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)", lines[line_idx])
        if not mname:
            continue
        func_name = mname.group(1)

        name_pos = joined.find(func_name, start_char)
        paren_open = joined.find("(", name_pos)
        if paren_open < 0:
            continue
        paren_close = _find_matching_paren(joined, paren_open)
        if paren_close < 0:
            continue

        param_str = joined[paren_open + 1 : paren_close].strip()

        after = joined[paren_close + 1 :]
        mret = re.match(r"^\s*([A-Za-z_]\w*)", after)
        sig_return = (mret.group(1) if mret else "").lower()

        next_start_char = None
        idx_pos = func_line_indices.index(line_idx)
        if idx_pos != len(func_line_indices) - 1:
            next_line_idx = func_line_indices[idx_pos + 1]
            next_start_char = sum(len(lines[i]) for i in range(next_line_idx))
        body_slice = joined[start_char : next_start_char] if next_start_char else joined[start_char:]

        inferred_return = _infer_return_type_from_body(body_slice)
        if inferred_return:
            return_type_display = inferred_return
        else:
            if sig_return in ("", "void"):
                return_type_display = "No return variable"
            else:
                return_type_display = TYPE_MAP_SINGULAR.get(sig_return, sig_return.capitalize())

        comment_block = _extract_comment_block(lines, line_idx)
        cleaned = _clean_comment_lines(comment_block)
        param_desc_map = _parse_param_descriptions_from_comments(cleaned)
        desc_lines = _parse_description_from_comments(cleaned, func_name)

        params = _parse_params(param_str, param_desc_map)

        docs.append(FunctionDoc(
            name=func_name,
            description_lines=desc_lines,
            return_type=return_type_display,
            params=params,
        ))

    return docs


# ----------------------------
# HTML generation (kept aligned with your sample structure)
# ----------------------------
def _render_description_html(description_lines: list[str]) -> str:
    """
    Turns description lines into HTML.
    - Normal lines -> <p>...</p>
    - Lines that begin (after trimming left) with "- " -> <ul><li>...</li></ul>
    - Blank lines separate blocks
    """
    if not description_lines:
        return "<p></p>"

    out = []
    para_buf: list[str] = []
    list_buf: list[str] = []

    def flush_para():
        nonlocal para_buf
        if para_buf:
            text = " ".join(s.strip() for s in para_buf if s.strip())
            if text:
                out.append(f"<p>{html.escape(text)}</p>")
            para_buf = []

    def flush_list():
        nonlocal list_buf
        if list_buf:
            out.append("<ul>")
            for item in list_buf:
                out.append(f"<li>{html.escape(item)}</li>")
            out.append("</ul>")
            list_buf = []

    for line in description_lines:
        if line.strip() == "":
            flush_para()
            flush_list()
            continue

        stripped_left = line.lstrip()

        if stripped_left.startswith("- "):
            flush_para()
            item = stripped_left[2:].rstrip()
            list_buf.append(item)
        else:
            flush_list()
            para_buf.append(line.rstrip())

    flush_para()
    flush_list()

    return "\n".join(out)


def build_html(doc: FunctionDoc, footer_name: str) -> str:
    title = html.escape(doc.name)
    header = html.escape(doc.name)
    desc_html = _render_description_html(doc.description_lines)
    return_html = html.escape(doc.return_type) if doc.return_type else "No return variable"

    rows_html = "\n".join(
        "<tr>"
        f"<td style=\"width: 23.4919%;\">{html.escape(p.name)}</td>"
        f"<td style=\"width: 19.7669%;\">{html.escape(p.direction)}</td>"
        f"<td style=\"width: 32.4862%;\">{html.escape(p.type_desc)}</td>"
        f"<td style=\"width: 24.0973%;\">{html.escape(p.description or '')}</td>"
        "</tr>"
        for p in doc.params
    )

    year = datetime.now().year

    return f"""                        <html>
                        <head>
                            <title>{title}</title>
                            <link rel="stylesheet" type="text/css" href="help.css">
                        </head>
                        <body>
                         <html><head></head><body><div class="header">{header}</div>
<div class="main">
<h2>Description</h2>
{desc_html}
<h2>Return Type</h2>
<p>{return_html}</p>
<h2>List of Parameters</h2>
<table class="table table-bordered" style="width: 95.0386%; height: 105px;">
<thead>
<tr style="height: 35px;">
<th style="width: 23.4919%; height: 35px;">Name</th>
<th style="width: 19.7669%; height: 35px;">Direction</th>
<th style="width: 32.4862%; height: 35px;">Type</th>
<th style="width: 24.0973%; height: 35px;">Description</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
<div class="footer">
<p>{html.escape(footer_name)} {year}</p>
</div></body></html>
                        </body>
                        </html>
                     """


# ----------------------------
# GUI
# ----------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HSL Auto-Documentation -> HTML")
        self.geometry("1100x720")
        self.minsize(900, 600)

        self.output_path_var = tk.StringVar()
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Output Directory (each function will be saved as FunctionName.html):").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.output_path_var).grid(row=1, column=0, sticky="ew", padx=(0, 8))

        btns = ttk.Frame(top)
        btns.grid(row=1, column=1, sticky="e")
        ttk.Button(btns, text="Choose Folder…", command=self.browse_folder).pack(side="left")

        top.columnconfigure(0, weight=1)

        mid = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid.pack(fill="both", expand=True)

        ttk.Label(mid, text="Paste HSL function(s) here:").pack(anchor="w")

        text_frame = ttk.Frame(mid)
        text_frame.pack(fill="both", expand=True)

        self.text = tk.Text(text_frame, wrap="none", undo=True)
        self.text.pack(side="left", fill="both", expand=True)

        yscroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        yscroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=yscroll.set)

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left", anchor="w")
        ttk.Button(bottom, text="Create HTML", command=self.create_html).pack(side="right")

    def browse_folder(self):
        path = filedialog.askdirectory(title="Choose Output Folder")
        if path:
            self.output_path_var.set(path)

    def create_html(self):
        output_raw = self.output_path_var.get().strip()
        if not output_raw:
            messagebox.showerror("Missing Output Directory", "Please choose an output directory.")
            return

        text_in = self.text.get("1.0", "end").strip()
        if not text_in:
            messagebox.showerror("Missing Input", "Please paste an HSL function into the text box.")
            return

        docs = parse_hsl_functions(text_in)
        if not docs:
            messagebox.showerror(
                "No functions found",
                "No functions found. Ensure your function begins with: function Name(...) ... {",
            )
            return

        out_dir = Path(output_raw)
        out_dir.mkdir(parents=True, exist_ok=True)

        created_files = []
        footer_name = "Zachary Milot"

        for doc in docs:
            file_path = out_dir / f"{_safe_filename(doc.name)}.html"
            file_path.write_text(build_html(doc, footer_name), encoding="utf-8")
            created_files.append(str(file_path))

        if len(created_files) == 1:
            self.status_var.set(f"Created: {created_files[0]}")
            messagebox.showinfo("Done", f"Created HTML:\n{created_files[0]}")
        else:
            self.status_var.set(f"Created {len(created_files)} files in: {str(out_dir)}")
            messagebox.showinfo("Done", f"Created {len(created_files)} HTML files in:\n{str(out_dir)}\n\nFiles:\n" + "\n".join(Path(f).name for f in created_files))


if __name__ == "__main__":
    App().mainloop()
