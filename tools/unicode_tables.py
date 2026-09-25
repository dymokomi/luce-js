#!/usr/bin/env python3
"""Generate the Unicode tables of luce_js.unicode from QuickJS's libunicode-table.h.

usage: tools/unicode_tables.py QUICKJS_SOURCE_DIR

Writes five fragments into src/luce_js/unicode/, one per section of libunicode-table.h:
case_table.lucb, normalization_table.lucb, category_table.lucb, script_table.lucb and
property_table.lucb.

Byte tables become `b"..."` literals (a literal of thousands of `u8` numbers compiles about
seven times slower); `u16` and `u32` tables stay number arrays. The general category and
script enums become `i32` constants; the property and sequence property enums, which
libunicode.c switches over, become integer-backed Luce enums. The name tables keep their
NUL-separated layout, ended by a second NUL as the C string literal is.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNICODE = ROOT / "src/luce_js/unicode"
RESERVED = set("""alloc and as asm break catch const continue defer elif else enum errdefer
export extern false for free from func goto if import in interface let local match mutating
new none not or pub recover return self static struct test true try type union var volatile
while with assert discard error trap hash print format sizeof alignof offsetof hex bin pad
bool char str unit never void fmt""".split())

# (fragment, summary, first declaration of the section in libunicode-table.h)
SECTIONS = [
    ("case_table", "Case conversion and the always-present property tables",
     "case_conv_table1"),
    ("normalization_table", "Combining classes, decompositions and compositions",
     "unicode_cc_table"),
    ("category_table", "General categories", "UnicodeGCEnum"),
    ("script_table", "Scripts and script extensions", "UnicodeScriptEnum"),
    ("property_table", "Binary and sequence properties", "unicode_prop_Hyphen_table"),
]

ARRAY = re.compile(r"static const (uint8_t|uint16_t|uint32_t) (\w+)\[(\d+)\] = \{(.*?)\};", re.S)
ENUM = re.compile(r"typedef enum \{(.*?)\} (\w+);", re.S)
NAMES = re.compile(r"static const char (\w+)\[\] =(.*?);", re.S)
POINTERS = re.compile(r"static const uint8_t \* const (\w+)\[\] = \{(.*?)\};", re.S)
LENGTHS = re.compile(r"static const uint16_t (\w+)\[\] = \{(.*?)\};", re.S)


def box(name, summary, description):
    return (
        "#" + "=" * 94 + "\n#\n"
        f"#   {name} - {summary}\n#\n"
        "#   DESCRIPTION:\n"
        + "".join(f"#       {line}\n" for line in description)
        + "#\n#" + "=" * 94 + "\n\n"
    )


def byte_literal(values):
    return "".join(chr(v) if 32 <= v < 127 and chr(v) not in '"\\' else f"\\x{v:02x}"
                   for v in values)


def numbers(body):
    return [int(v, 0) for v in re.findall(r"\b(?:0x[0-9a-fA-F]+|\d+)\b", re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.S))]


def enum_members(body):
    return [m for m in re.findall(r"(\w+)\s*,", body)]


def lower_case(name, prefix):
    rest = name[len(prefix):]
    case = rest.lower()
    return case + "_" if case in RESERVED else case


def array_decl(kind, name, count, body):
    values = numbers(body)
    assert len(values) == int(count), name
    if kind == "uint8_t":
        return f"let {name}: const u8[] = b\"{byte_literal(values)}\"\n"
    width = 4 if kind == "uint16_t" else 8
    luce = "u16" if kind == "uint16_t" else "u32"
    per_line = 12 if kind == "uint16_t" else 8
    lines = []
    for i in range(0, len(values), per_line):
        lines.append("    " + ", ".join(f"0x{v:0{width}x}" for v in values[i:i + per_line]) + ",")
    return f"let {name}: {luce}[{count}] = [\n" + "\n".join(lines) + "\n]\n"


def enum_decl(name, body):
    members = enum_members(body)
    prefix = {"UnicodeGCEnum": "UNICODE_GC_", "UnicodeScriptEnum": "UNICODE_SCRIPT_",
              "UnicodePropertyEnum": "UNICODE_PROP_",
              "UnicodeSequencePropertyEnum": "UNICODE_SEQUENCE_PROP_"}[name]
    if name in ("UnicodeGCEnum", "UnicodeScriptEnum"):
        # plain constants: C only compares and indexes with them
        prefix_luce = prefix.lower()
        out = [f"# {name}\n"]
        seen = set()
        for index, member in enumerate(members):
            luce = prefix_luce + member[len(prefix):].lower()
            assert luce not in seen, luce
            seen.add(luce)
            out.append(f"let {luce}: i32 = {index}\n")
        return "".join(out)
    # switched over in libunicode.c: an integer-backed enum
    out = [f"enum {name} as i32:\n"]
    seen = set()
    for index, member in enumerate(members):
        case = lower_case(member, prefix)
        assert case not in seen, case
        seen.add(case)
        out.append(f"    {case} = {index}\n")
    return "".join(out)


def names_decl(name, body):
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', body)
    text = "".join(parts).replace("\\0", "\0") + "\0"
    return (f"## {name}: NUL-separated entries of comma-separated aliases, ended by an empty entry.\n"
            f"let {name}: const u8[] = b\"{byte_literal(text.encode('ascii'))}\"\n")


def pointers_decl(name, body):
    entries = re.findall(r"\w+", body)
    lines = "".join(f"    {e},\n" for e in entries)
    return (f"## {name}: the run-length tables indexed by UnicodePropertyEnum; each span carries\n"
            f"## its length, which C keeps apart in unicode_prop_len_table.\n"
            f"let {name}: (const u8[])[{len(entries)}] = [\n{lines}]\n")


def generate(source):
    # split the header at each section's first declaration
    starts = []
    for fragment, summary, first in SECTIONS:
        pos = source.rfind("\n", 0, source.find(first)) + 1
        if first.endswith("Enum"):
            pos = source.rfind("typedef enum", 0, source.find("} " + first))
        starts.append(pos)
    starts.append(len(source))
    for (fragment, summary, first), begin, end in zip(SECTIONS, starts, starts[1:]):
        text = source[begin:end]
        items = []
        for m in ARRAY.finditer(text):
            items.append((m.start(), array_decl(*m.groups())))
        for m in ENUM.finditer(text):
            items.append((m.start(), enum_decl(m.group(2), m.group(1))))
        for m in NAMES.finditer(text):
            items.append((m.start(), names_decl(*m.groups())))
        for m in POINTERS.finditer(text):
            items.append((m.start(), pointers_decl(*m.groups())))
        first_line = source.count("\n", 0, begin) + 1
        last_line = source.count("\n", 0, end)
        out = [box(fragment, summary,
                   ["Generated by tools/unicode_tables.py from QuickJS libunicode-table.h",
                    f"(lines {first_line}-{last_line}); do not edit. Unicode 17.0.0.",
                    "Byte tables are `b\"...\"` literals declared `const u8[]`",
                    "(workaround: compiler-issues/byte-literal-array-type)."])]
        for _, decl in sorted(items):
            out.append(decl + "\n")
        (UNICODE / f"{fragment}.lucb").write_text("".join(out).rstrip("\n") + "\n")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    generate((Path(sys.argv[1]) / "libunicode-table.h").read_text())


if __name__ == "__main__":
    main()
