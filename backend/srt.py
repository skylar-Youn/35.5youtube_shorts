from __future__ import annotations
from typing import List, Tuple


def to_srt(segments: List[Tuple[float, float, str]]) -> str:
    def fmt(t: float) -> str:
        t = max(0.0, float(t))
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines = []
    for i, (start, end, text) in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{fmt(start)} --> {fmt(end)}")
        lines.extend(str(text or "").splitlines() or [""])
        lines.append("")
    return "\n".join(lines)


def parse_srt(srt_text: str) -> List[Tuple[float, float, str]]:
    import re
    segs: List[Tuple[float, float, str]] = []
    blocks = re.split(r"\n\s*\n", srt_text.strip())
    for blk in blocks:
        lines = [l for l in blk.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        # optionally first line is index
        head = lines[0]
        if re.match(r"^\d+$", head):
            lines = lines[1:]
        if not lines:
            continue
        ts = lines[0]
        m = re.match(r"(\d\d:\d\d:\d\d,\d\d\d)\s*-->\s*(\d\d:\d\d:\d\d,\d\d\d)", ts)
        if not m:
            continue
        def parse_time(s: str) -> float:
            h, m_, rest = s.split(":")
            s_, ms = rest.split(",")
            return int(h) * 3600 + int(m_) * 60 + int(s_) + int(ms) / 1000.0
        start = parse_time(m.group(1))
        end = parse_time(m.group(2))
        text = "\n".join(lines[1:])
        segs.append((start, end, text))
    return segs

