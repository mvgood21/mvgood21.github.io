"""Fail image builds that would draw a blank where a character should be.

The NanumSquare files in tools/fonts map all 11,172 Hangul syllables in cmap, but 8,693 (ExtraBold) / 8,822 (Regular)
of them have empty outlines (measured 2026-10-23; same defect as the AX note hangul-blank-glyph-cmap). Pillow then
draws an empty advance instead of falling back, so a rare syllable in a figure, cover or share card silently becomes a
gap. Characters the font does not map at all print as its .notdef box (tofu). install() wraps ImageDraw.text to
record every non-space character that renders no ink or the .notdef box; report() prints them
and returns False when any were found. Used by tools/ax_figures.py and tools/og.py.
"""
from PIL import ImageDraw

_seen, _blank = {}, {}
_orig = ImageDraw.ImageDraw.text


def _sig(font, ch):
    m = font.getmask(ch)
    return m.size, bytes(m)


def _check(font, text):
    path = getattr(font, "path", None)
    for ch in str(text):
        if ch.isspace() or ch in "​ㅤ": continue
        key = (path, ch)
        if key not in _seen:
            try:
                # blank: mapped but no outline; tofu: not mapped, drawn as the font's .notdef box (e.g. U+2212 −)
                notdef = _seen.setdefault((path, "􏿽"), _sig(font, "􏿽"))
                _seen[key] = font.getmask(ch).getbbox() is not None and _sig(font, ch) != notdef
            except Exception: _seen[key] = True  # bitmap/default fonts: nothing to check
        if not _seen[key]:
            _blank.setdefault(ch, set()).add(str(text)[:40])


def _text(self, xy, text, fill=None, font=None, *args, **kwargs):
    if font is not None: _check(font, text)
    return _orig(self, xy, text, fill, font, *args, **kwargs)


def install():
    ImageDraw.ImageDraw.text = _text


def report():
    if not _blank: return True
    for ch, where in sorted(_blank.items()):
        print(f"BLANK GLYPH {ch!r} (U+{ord(ch):04X}) in: " + " | ".join(sorted(where)[:3]))
    print("Reword these (the font has no outline for them), then run again.")
    return False
