"""Tolerant parsing of timestamps and explicit time ranges typed by users (pure)."""

from __future__ import annotations

import re

_COLON = r"\d{1,2}(?::\d{1,2}){1,2}(?:[.,]\d+)?"
_UNITS = r"(?:\d+(?:[.,]\d+)?\s*h)?\s*(?:\d+(?:[.,]\d+)?\s*m(?:in)?)?\s*(?:\d+(?:[.,]\d+)?\s*s)?"
_TIME = rf"(?:{_COLON}|(?=\d)(?:\d+\s*h)?\s*(?:\d+\s*m(?:in)?)?\s*(?:\d+(?:[.,]\d+)?\s*s)?)"
_SEP = r"(?:\s*[-–—]\s*|\s+(?:to|a|hasta|until)\s+)"
_RANGE_RE = re.compile(rf"(?<![\w:.])({_TIME}){_SEP}({_TIME})(?![\w:])", re.IGNORECASE)
_UNIT_RE = re.compile(
    r"^(?:(?P<h>\d+(?:\.\d+)?)\s*h)?\s*(?:(?P<m>\d+(?:\.\d+)?)\s*m(?:in)?)?\s*(?:(?P<s>\d+(?:\.\d+)?)\s*s)?$"
)


def parse_time(text: str) -> float:
    """``10:30`` / ``1:02:03`` / ``90`` / ``90s`` / ``10m30s`` / ``1h2m3s`` -> seconds."""
    t = text.strip().lower().replace(",", ".")
    if not t:
        raise ValueError("empty time")
    if ":" in t:
        parts = t.split(":")
        if len(parts) > 3 or any(not p for p in parts):
            raise ValueError(f"invalid time '{text}'")
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            raise ValueError(f"invalid time '{text}'") from None
        if any(n < 0 for n in nums) or any(n >= 60 for n in nums[1:]):
            raise ValueError(f"invalid time '{text}'")
        total = 0.0
        for n in nums:
            total = total * 60 + n
        return total
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        return float(t)
    m = _UNIT_RE.match(t)
    if not m or not any(m.groupdict().values()):
        raise ValueError(f"invalid time '{text}'")
    return float(m["h"] or 0) * 3600 + float(m["m"] or 0) * 60 + float(m["s"] or 0)


_BOUNDS_RE = re.compile(rf"^\s*(\S.*?)(?:\s*[-–—]\s*|\s+(?:to|a|hasta|until)\s+)(\S.*?)\s*$", re.IGNORECASE)


def parse_time_range(text: str) -> tuple[float, float]:
    """Parse a single ``start-end`` range (bare numbers are seconds)."""
    m = _BOUNDS_RE.match(text)
    if not m:
        raise ValueError(f"invalid time range '{text}' (expected e.g. 10:30-11:15)")
    start, end = parse_time(m.group(1)), parse_time(m.group(2))
    if end <= start:
        raise ValueError(f"invalid time range '{text}': end must be after start")
    return start, end


def extract_ranges(text: str) -> tuple[list[tuple[float, float]], str]:
    """Find explicit ``mm:ss-mm:ss`` style ranges in free text.

    Returns the ranges in order of appearance and the text with those ranges removed.
    Bare-number pairs such as "top 10-15" are deliberately not treated as times.
    """
    ranges: list[tuple[float, float]] = []
    spans: list[tuple[int, int]] = []
    for m in _RANGE_RE.finditer(text):
        a, b = m.group(1), m.group(2)
        if not any(c in x for x in (a, b) for c in ":hms"):
            continue
        try:
            start, end = parse_time(a), parse_time(b)
        except ValueError:
            continue
        if end <= start:
            continue
        ranges.append((start, end))
        spans.append(m.span())
    rest = text
    for s, e in reversed(spans):
        rest = rest[:s] + " " + rest[e:]
    rest = re.sub(r"\s+([,.;])", r"\1", " ".join(rest.split())) if spans else text
    return ranges, rest.strip(" ,;.\t\n") if spans else rest
