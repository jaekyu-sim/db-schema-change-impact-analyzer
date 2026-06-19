from __future__ import annotations

import re


STRING_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"')
TEXT_BLOCK = re.compile(r'"""(.*?)"""', re.S)


def decode_java_strings(expression: str) -> str:
    blocks = TEXT_BLOCK.findall(expression)
    if blocks:
        return " ".join(blocks)
    parts = []
    for match in STRING_LITERAL.finditer(expression):
        raw = match.group(0)[1:-1]
        parts.append(bytes(raw, "utf-8").decode("unicode_escape"))
    return "".join(parts)


def java_assignments(content: str) -> dict[str, tuple[str, int]]:
    assignments: dict[str, tuple[str, int]] = {}
    pattern = re.compile(r"(?:String|var)\s+(\w+)\s*=\s*(.*?);", re.S)
    for match in pattern.finditer(content):
        assignments[match.group(1)] = (match.group(2).strip(), content[:match.start()].count("\n") + 1)
    return assignments

