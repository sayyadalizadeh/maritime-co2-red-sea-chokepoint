"""Shared figure settings: palette, fonts, sizes, time axes, a text audit and saving."""

import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.text import Text  # noqa: E402

import config as C  # noqa: E402

# Okabe-Ito colour-blind-safe palette
OI = {"black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
      "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7",
      "grey": "#999999"}

MM = 1 / 25.4
SINGLE = 90 * MM   # single-column width, inches
FULL = 190 * MM    # full width, inches

# Every text element is set at FONT points at the printed width (RS-D28). Figures are created at
# their printed width, so the size set here is the printed size.
FONT = 8
MIN_FONT = 8.0
# Mathtext sub- and superscripts are drawn at this fraction of the text size; the audit counts
# them at the reduced size. Labels therefore write CO2 with the Unicode subscript two, which is
# drawn at the full text size (the glyph comes from DejaVu Sans, as Arial has none).
MATHTEXT_SHRINK = 0.7
CO2 = "CO₂"
# Working codes that must not appear in text drawn in a figure: variable names (underscore),
# decision codes, research-question codes and dates written as YYYY-MM
CODE_PATTERN = re.compile(r"_|RS-D|RQ\d|\d{4}-\d{2}")

FIG_DIR = C.OUTPUTS / "figures"
SUPP_DIR = FIG_DIR / "supplementary"
SHOCK = pd.Timestamp(C.SHOCK_START + "-01")

# Text audit of every saved figure, filled by save(): name -> dict
AUDIT = {}


def setup():
    plt.rcParams.update({
        # an explicit family list (not the generic "sans-serif") lets glyphs missing from Arial,
        # such as the subscript two, fall back to DejaVu Sans
        "font.family": ["Arial", "DejaVu Sans"],
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": FONT, "axes.labelsize": FONT, "axes.titlesize": FONT,
        "xtick.labelsize": FONT, "ytick.labelsize": FONT, "legend.fontsize": FONT,
        "legend.title_fontsize": FONT, "figure.titlesize": FONT,
        "axes.linewidth": 0.6, "lines.linewidth": 1.0,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "pdf.fonttype": 42, "ps.fonttype": 42,
        "savefig.dpi": 300, "figure.dpi": 100,
    })


def to_dt(periods):
    """YYYY-MM strings to timestamps at the first day of the month."""
    return pd.PeriodIndex(list(periods), freq="M").to_timestamp()


def shock_line(ax):
    """Vertical line at the shock month (2023-12)."""
    ax.axvline(SHOCK, color=OI["grey"], lw=0.7, ls=(0, (3, 2)), zorder=0)


def _drawn_texts(fig):
    """Text artists that are drawn: visible, non-empty, in a visible axes; tick labels only for drawn ticks."""
    tick_labels, drawn_ticks = set(), []
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            for tick in axis.majorTicks + axis.minorTicks:
                tick_labels.update((id(tick.label1), id(tick.label2)))
            if ax.get_visible():
                for tick in axis._update_ticks():  # the ticks drawn within the view interval
                    drawn_ticks += [lab for lab in (tick.label1, tick.label2) if lab.get_visible()]
    texts = [t for t in fig.findobj(Text) if id(t) not in tick_labels] + drawn_ticks
    return [t for t in texts if t.get_visible() and t.get_text().strip()
            and (t.axes is None or t.axes.get_visible())]


def rendered_size(t):
    """Font size of the smallest glyphs of a text (mathtext sub/superscripts at the reduced size)."""
    size = float(t.get_fontsize())
    if re.search(r"\$[^$]*[_^][^$]*\$", t.get_text()):
        size *= MATHTEXT_SHRINK
    return size


def audit(fig):
    """Smallest rendered font size, texts cut at the figure edge, overlapping text pairs and
    texts containing working codes (CODE_PATTERN).

    Read from the drawn figure (before saving). Boxes are the rendered text extents in display
    units; a tolerance of 0.5 pixel (at the 100 dpi drawing resolution) is allowed.
    """
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    texts = _drawn_texts(fig)
    fb = fig.bbox
    tol = 0.5
    # Text.get_window_extent: the box of the text itself (for an annotation, without its leader line)
    boxes = [(t, Text.get_window_extent(t, r)) for t in texts]
    outside = [t.get_text() for t, b in boxes
               if b.x0 < fb.x0 - tol or b.y0 < fb.y0 - tol or b.x1 > fb.x1 + tol or b.y1 > fb.y1 + tol]
    overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a.x0 + tol < b.x1 and b.x0 + tol < a.x1 and a.y0 + tol < b.y1 and b.y0 + tol < a.y1:
                overlaps.append((boxes[i][0].get_text(), boxes[j][0].get_text()))
    sizes = [rendered_size(t) for t in texts]
    codes = [t.get_text() for t in texts if CODE_PATTERN.search(t.get_text())]
    return {"min_font": min(sizes), "n_texts": len(texts), "outside": outside, "overlaps": overlaps,
            "codes": codes}


def save(fig, name, data, supplementary=False):
    """Audit the text, then save PDF (vector), PNG (300 dpi) and the data file; return the written paths."""
    AUDIT[name] = audit(fig)
    d = SUPP_DIR if supplementary else FIG_DIR
    d.mkdir(parents=True, exist_ok=True)
    paths = [d / f"{name}.pdf", d / f"{name}.png", d / f"{name}_data.csv"]
    fig.savefig(paths[0], metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(paths[1], dpi=300)
    data.to_csv(paths[2], index=False)
    plt.close(fig)
    return paths
