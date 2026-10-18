"""SugarMount Design System (SDS) generated CSS.

Pure functions (standard library only) that RETURN the text of two generated files.
tools/build.py writes them; this module never writes site files.

  sds_apps_css(apps)      -> text of assets/sds-apps.css (per-app accent tokens, light + dark, brand spectrum)
  pretendard_css(chars)   -> text of assets/fonts/pretendard.css (self-hosted Pretendard Variable 1.3.9
                             dynamic subsets actually needed for `chars`, plus metric-adjusted fallback faces)

Used by build.py --check (sds_gates): audit(apps), accent_tokens(), resolved_tokens(); subsets_for() feeds pretendard_css().
CLI only (not part of the build gate): de00()/de00_pairs() accent-distance warnings (dE00 < 8; the spec's
new-key dE00 >= 12 rule needs a human to know which key is new). Run `python tools/sds_apps.py` to print the
contrast table and those warnings; `--check` exits 1 if any gate fails. Font byte budgets live in checks.py.

Rules (SDS spec 11, sections 3.1 and 4):
  T1  every accent token is emitted as a literal hex per [data-app] scope (never var()-derived);
  T2  text on bg-accent-weak is fg-accent-contrast;
  T3  no color-mix();
  targets are 4.6:1 so rounding and browser blending never drop below 4.5:1.
"""
import colorsys
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBSETS_JSON = os.path.join(ROOT, 'tools', 'fonts', 'pretendard-subsets.json')
FONT_URL = 'pretendard/'          # relative to assets/fonts/pretendard.css

# Neutral surfaces (site.css ref tokens)
BASEMENT, DEFAULT = '#F6F8FB', '#FFFFFF'
D_BASEMENT, D_DEFAULT, D_FLOATING = '#0F1622', '#172131', '#1D2940'
WHITE, D_INK = '#FFFFFF', '#0F1622'
TARGET = 4.6

# The nine accent tokens, in output order. site.css :root declares the same nine (T1 gate).
TOKENS = ('bg-accent-solid', 'bg-accent-solid-hover', 'fg-on-accent', 'fg-accent', 'bg-accent-weak',
          'fg-accent-contrast', 'stroke-focus-ring', 'stroke-link', 'stroke-link-hover')


# ---------- colour math ----------
def _rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c):
    return '#%02X%02X%02X' % tuple(max(0, min(255, round(v))) for v in c)


def _lin(v):
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(h):
    r, g, b = (_lin(x) for x in _rgb(h))
    return .2126 * r + .7152 * g + .0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def mix(a, b, t):
    """sRGB blend: t of a over (1-t) of b."""
    A, B = _rgb(a), _rgb(b)
    return _hex(tuple(A[i] * t + B[i] * (1 - t) for i in range(3)))


def shift_l(h, d):
    """Move HSL lightness by d (0..1 scale)."""
    r, g, b = (x / 255 for x in _rgb(h))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    return _hex([x * 255 for x in colorsys.hls_to_rgb(hh, max(0, min(1, l + d)), s)])


def _until(h, step, ok, limit=100):
    n = 0
    while not ok(h) and n < limit:
        h = shift_l(h, step)
        n += 1
    return h


def hue(h):
    r, g, b = (x / 255 for x in _rgb(h))
    return colorsys.rgb_to_hls(r, g, b)[0] * 360


def _lab(h):
    c = [_lin(x) for x in _rgb(h)]
    X = (0.4124 * c[0] + 0.3576 * c[1] + 0.1805 * c[2]) / 0.95047
    Y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    Z = (0.0193 * c[0] + 0.1192 * c[1] + 0.9505 * c[2]) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))


def de00(a, b):
    """CIEDE2000 colour distance between two hex colours."""
    L1, a1, b1 = _lab(a)
    L2, a2, b2 = _lab(b)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0
    else:
        dhp = h2p - h1p
        if dhp > 180:
            dhp -= 360
        elif dhp < -180:
            dhp += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dth = 30 * math.exp(-((hbp - 275) / 25) ** 2)
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


# ---------- accent derivation (spec 11 section 4.1) ----------
def accent_tokens(accent):
    """Return {'light': {token: hex}, 'dark': {token: hex}} for one app accent."""
    a = accent.upper()
    weak = mix(a, DEFAULT, .10)
    strong = _until(a, -.01, lambda x: contrast(x, weak) >= TARGET and contrast(x, BASEMENT) >= TARGET)
    d = _until(a, .01, lambda x: contrast(x, D_FLOATING) >= TARGET)
    d_weak = mix(a, D_DEFAULT, .24)
    d_strong = _until(d, .01, lambda x: contrast(x, d_weak) >= TARGET)
    light = dict(zip(TOKENS, (a, shift_l(a, -.06), WHITE, a, weak, strong, a, a, a)))
    dark = dict(zip(TOKENS, (d, shift_l(d, .06), D_INK, d, d_weak, d_strong, d, d, d)))
    return {'light': light, 'dark': dark}


def _apps(apps=None):
    if apps is None:
        with open(os.path.join(ROOT, 'data', 'apps.json'), encoding='utf-8') as f:
            apps = json.load(f)['apps']
    return [a for a in apps if a.get('accent')]


def spectrum(apps=None):
    """Hard-stop gradient of every site accent, ordered by HSL hue (spec 6.0.2)."""
    cols = sorted((a['accent'].upper() for a in _apps(apps)), key=hue)
    n = len(cols)
    stops = ','.join('%s 0 %s%%' % (c, ('%.2f' % (100 * (i + 1) / n)).rstrip('0').rstrip('.')) for i, c in enumerate(cols))
    return 'linear-gradient(90deg,%s)' % stops


# Per-app literal hex tokens. By the 4.1 rule, fg-accent, the focus ring and both link strokes always
# equal bg-accent-solid, fg-accent-contrast usually does, and fg-on-accent is a per-mode constant.
# So one shared [data-app] rule declares those as var(--sds-bg-accent-solid). That rule matches every
# [data-app] element itself, so var() resolves on that element and never freezes at :root (T1 holds:
# every [data-app] element ends up with all nine tokens; resolved_tokens() + audit() prove the values).
# fg-accent-contrast is written per app only where it differs. --sds-vt is the view-transition-name
# for that app (site.css applies it to the app-row icon and the app hero icon, motion-guarded).
# Result: 11 apps in about 3.8 KB instead of 6.8 KB.
PER_APP = ('bg-accent-solid', 'bg-accent-solid-hover', 'bg-accent-weak')
SHARED = ('fg-accent', 'fg-accent-contrast', 'stroke-focus-ring', 'stroke-link', 'stroke-link-hover')


def _decls(tok, names):
    return ';'.join('--sds-%s:%s' % (k, tok[k]) for k in names)


def sds_apps_css(apps=None):
    """Text of assets/sds-apps.css. Selectors are [data-app] only (main, list rows, tiles)."""
    apps = _apps(apps)
    shared = ';'.join('--sds-%s:var(--sds-bg-accent-solid)' % k for k in SHARED)
    out = ['/* generated by tools/build.py from data/apps.json - do not edit */',
           ':root{--sds-brand-spectrum:%s}' % spectrum(apps),
           '[data-app]{--sds-fg-on-accent:%s;%s}' % (WHITE, shared)]
    toks = [(a['id'], accent_tokens(a['accent'])) for a in apps]
    light_own = {}
    for i, t in toks:
        L = t['light']
        extra = ''
        if L['fg-accent-contrast'] != L['bg-accent-solid']:
            light_own[i] = True
            extra = ';--sds-fg-accent-contrast:' + L['fg-accent-contrast']
        out.append('[data-app=%s]{%s%s;--sds-vt:app-%s}' % (i, _decls(L, PER_APP), extra, i))
    out.append('@media (prefers-color-scheme:dark){')
    out.append('[data-app]{--sds-fg-on-accent:%s}' % D_INK)
    for i, t in toks:
        D = t['dark']
        extra = ''
        if light_own.get(i) or D['fg-accent-contrast'] != D['bg-accent-solid']:
            extra = ';--sds-fg-accent-contrast:' + D['fg-accent-contrast']
        out.append('[data-app=%s]{%s%s}' % (i, _decls(D, PER_APP), extra))
    out.append('}')
    return '\n'.join(out) + '\n'


def resolved_tokens(css, app_id, dark=False):
    """Resolve the nine tokens one [data-app=app_id] element gets from sds_apps_css() text.
    Used by --check to prove the generated file equals accent_tokens() (T1 equivalence gate)."""
    import re
    light_part, _, dark_part = css.partition('@media (prefers-color-scheme:dark){')
    vals = {}
    for part in ([light_part, dark_part] if dark else [light_part]):
        for sel, body in re.findall(r'(\[data-app(?:=[\w-]+)?\])\{([^}]*)\}', part):
            if sel in ('[data-app]', '[data-app=%s]' % app_id):
                for d in body.split(';'):
                    k, _, v = d.partition(':')
                    vals[k.strip()[6:]] = v.strip()
    for k, v in list(vals.items()):
        if v.startswith('var(--sds-'):
            vals[k] = vals[v[10:-1]]
    return {k: v for k, v in vals.items() if k in TOKENS}


def audit(apps=None):
    """Contrast gates 1-4 (spec 11 section 4.3) per app. Returns list of row dicts with 'fail' list."""
    rows = []
    for a in _apps(apps):
        t = accent_tokens(a['accent'])
        L, D = t['light'], t['dark']
        checks = {
            'white on accent': contrast(WHITE, L['bg-accent-solid']),
            'white on hover': contrast(WHITE, L['bg-accent-solid-hover']),
            'accent on basement': contrast(L['fg-accent'], BASEMENT),
            'contrast on weak': contrast(L['fg-accent-contrast'], L['bg-accent-weak']),
            'contrast on basement': contrast(L['fg-accent-contrast'], BASEMENT),
            'd-accent on default': contrast(D['fg-accent'], D_DEFAULT),
            'd-accent on floating': contrast(D['fg-accent'], D_FLOATING),
            'd-accent on basement': contrast(D['fg-accent'], D_BASEMENT),
            'ink on d-accent': contrast(D_INK, D['bg-accent-solid']),
            'ink on d-hover': contrast(D_INK, D['bg-accent-solid-hover']),
            'd-contrast on d-weak': contrast(D['fg-accent-contrast'], D['bg-accent-weak']),
        }
        rows.append({'id': a['id'], 'accent': a['accent'].upper(), 'light': L, 'dark': D, 'ratios': checks,
                     'fail': [k for k, v in checks.items() if v < 4.5]})
    return rows


def de00_pairs(colors):
    """colors: {name: hex}. Returns sorted [(dE00, a, b)] for every pair."""
    items = list(colors.items())
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            out.append((de00(items[i][1], items[j][1]), items[i][0], items[j][0]))
    return sorted(out)


# ---------- fonts (spec 11 section 5) ----------
def _subsets():
    with open(SUBSETS_JSON, encoding='utf-8') as f:
        data = json.load(f)['subsets']
    out = []
    for idx, name, ranges in data:
        spans = []
        for r in ranges.split(','):
            r = r.strip()[2:]
            lo, _, hi = r.partition('-')
            spans.append((int(lo, 16), int(hi or lo, 16)))
        out.append((idx, name, ranges, spans))
    return out


def subsets_for(chars):
    """Indices of the Pretendard subsets that cover any code point in `chars` (str or iterable of str)."""
    cps = {ord(c) for c in (chars if isinstance(chars, str) else ''.join(chars))}
    used = []
    for idx, _name, _ranges, spans in _subsets():
        if any(lo <= cp <= hi for cp in cps for lo, hi in spans):
            used.append(idx)
    return used


# Metric-adjusted fallbacks: Pretendard hhea 1950/-494 per 2048 upm, Hangul advance .8643em,
# Latin lowercase .5063em (spec 11 section 5.3, values measured from the TTF tables).
FALLBACK_FACES = (
    '@font-face{font-family:"SDS Fallback Hangul";src:local("Malgun Gothic"),local("MalgunGothic");'
    'unicode-range:U+AC00-D7A3,U+1100-11FF,U+3130-318F;'
    'size-adjust:86.43%;ascent-override:110.16%;descent-override:27.91%;line-gap-override:0%}',
    '@font-face{font-family:"SDS Fallback Hangul Android";src:local("Noto Sans KR"),local("Noto Sans CJK KR"),'
    'local("NotoSansCJKkr-Regular");unicode-range:U+AC00-D7A3,U+1100-11FF,U+3130-318F;'
    'size-adjust:93.94%;ascent-override:101.35%;descent-override:25.68%;line-gap-override:0%}',
    '@font-face{font-family:"SDS Fallback Latin";src:local("Arial"),local("ArialMT");'
    'unicode-range:U+0000-024F,U+2000-206F;'
    'size-adjust:103.43%;ascent-override:92.06%;descent-override:23.32%;line-gap-override:0%}',
)


def pretendard_css(chars=None):
    """Text of assets/fonts/pretendard.css.

    chars: every character the site's pages render in the Pretendard stack (exclude text styled with
    --sds-font-system such as .sym and en-page [lang=ko] labels). None emits all 92 subsets.
    """
    want = None if chars is None else set(subsets_for(chars))
    out = ['/* generated by tools/build.py (tools/sds_apps.py). Pretendard Variable 1.3.9, SIL OFL 1.1, '
           'see pretendard/OFL.txt - do not edit */']
    for idx, name, ranges, _spans in _subsets():
        if want is not None and idx not in want:
            continue
        # font-style defaults to normal; every browser that reads unicode-range reads woff2, so no format().
        out.append('@font-face{font-family:"Pretendard Variable";font-weight:45 920;font-display:swap;'
                   'src:url(%s%s);unicode-range:%s}' % (FONT_URL, name, ranges))
    # English pages (site.css :lang(en)) use EN_FAMILY: the same two files, ranges cut to their non-Hangul code points.
    # Any other character on an /en/ page (’ → × % _ ₩ ⋮, Korean words) then falls back to the system font instead of
    # pulling a 20-35 KB subset for one glyph, which keeps every /en/ page at the 63 KB target (SDS 5.2-4/6, IA 9.1).
    for idx, name, _ranges, spans in _subsets():
        if idx in EN_SUBSETS:
            out.append('@font-face{font-family:"%s";font-weight:45 920;font-display:swap;src:url(%s%s);unicode-range:%s}'
                       % (EN_FAMILY, FONT_URL, name, _latin_ranges(spans)))
    out += FALLBACK_FACES
    return '\n'.join(out) + '\n'


EN_FAMILY = 'Pretendard Latin'
EN_SUBSETS = (88, 91)   # 91: Basic Latin, Latin-1 punctuation, – — “ ” ™; 88: & + > @ ~


def _latin_ranges(spans):
    return ','.join('U+%x' % lo if lo == hi else 'U+%x-%x' % (lo, hi) for lo, hi in spans if hi < 0x3000)


def _main(argv):
    rows = audit()
    print('| app | accent | white/acc | white/hover | acc/base | contrast/weak | d-acc | d-acc/float | ink/d-acc | ink/d-hover | d-contrast/d-weak | min |')
    bad = 0
    for r in rows:
        q = r['ratios']
        print('| %s | %s | %.2f | %.2f | %.2f | %.2f | %s | %.2f | %.2f | %.2f | %.2f | %.2f |' % (
            r['id'], r['accent'], q['white on accent'], q['white on hover'], q['accent on basement'],
            q['contrast on weak'], r['dark']['fg-accent'], q['d-accent on floating'], q['ink on d-accent'],
            q['ink on d-hover'], q['d-contrast on d-weak'], min(q.values())))
        if r['fail']:
            bad += 1
            print('  FAIL', r['id'], r['fail'])
    css = sds_apps_css()
    for a in _apps():
        want = accent_tokens(a['accent'])
        for mode in ('light', 'dark'):
            got = resolved_tokens(css, a['id'], mode == 'dark')
            if got != want[mode]:
                bad += 1
                print('  FAIL T1 equivalence', a['id'], mode)
    print('sds-apps.css %d B; pretendard.css (all subsets) %d B' % (len(css.encode()), len(pretendard_css().encode())))
    low = [p for p in de00_pairs({a['id']: a['accent'] for a in _apps()}) if p[0] < 8]
    for d, a, b in low:
        print('  warn dE00 %.1f %s ~ %s' % (d, a, b))
    if '--check' in argv and bad:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
