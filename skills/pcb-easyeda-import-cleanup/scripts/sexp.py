"""Locating blocks in a KiCad file (S-expression) while respecting quoted strings.

Edits are made at the text level (no full rewrite) so that the diff stays readable and KiCad re-reads the file
without surprises.
"""
import re


def block_end(s, start):
    """Index just after the closing parenthesis of the block that starts at s[start] == '('."""
    depth, i, n = 0, start, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            i += 1
            while i < n and s[i] != '"':
                i += 2 if s[i] == "\\" else 1
            if i >= n:
                raise ValueError("unclosed string")
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unclosed block")


def top_blocks(s, tag, indent="\t"):
    """Blocks `(tag …` at the given indentation level: list of (start, end); start points at '('."""
    out, i = [], 0
    pat = re.compile(r"\n" + re.escape(indent) + r"\(" + re.escape(tag) + r"[\s\n]")
    while True:
        m = pat.search(s, i)
        if not m:
            return out
        a = m.start() + 1 + len(indent)
        b = block_end(s, a)
        out.append((a, b))
        i = b


def remove_block(s, a, b):
    """Remove the block and the line it occupied (indentation and end of line included)."""
    ls = s.rfind("\n", 0, a)
    return s[:ls] + s[b:]
