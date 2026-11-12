"""Portable redraw of notebook 07D. Plotting definitions are unchanged."""
import matplotlib
matplotlib.use('Agg')
from pathlib import Path
import json
import hashlib
import shutil
import zipfile
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

from figure_common import prepare_output
OUTPUT = prepare_output("Reproduce the NIFC-NIROPS methods schematic; no empirical data or model fitting.")
STEM = "fig_fireline_units_nifc_nirops"
COLORS = {
    "text": "#202830", "muted": "#5D6872", "blue": "#0072B2",
    "perimeter": "#D55E00", "fire_area": "#F9E3D3", "band": "#BFC8CE",
    "border": "#CDD4DA", "line": "#28323A",
}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8,
    "text.color": COLORS["text"], "axes.labelcolor": COLORS["text"],
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "savefig.facecolor": "white", "figure.facecolor": "white",
})
print("Figure folder:", OUTPUT)

UNIT_LENGTH_M = 250.0
SPACING_M = 25.0
TOLERANCE_M = 50.0
CHECK_POSITIONS_M = np.arange(SPACING_M / 2, UNIT_LENGTH_M, SPACING_M)
HELD_PERIMETERS_M = [-90.0, -20.0, -10.0]
BURNED_OVER_PERIMETERS_M = [-90.0, 90.0]

# Position x=0 stays fixed. The fire area is to the left of each perimeter.
assert len(CHECK_POSITIONS_M) == 10
assert np.allclose(np.diff(CHECK_POSITIONS_M), SPACING_M)
assert CHECK_POSITIONS_M[0] == 12.5 and CHECK_POSITIONS_M[-1] == 237.5
assert HELD_PERIMETERS_M[0] < -TOLERANCE_M
assert all(abs(x) <= TOLERANCE_M for x in HELD_PERIMETERS_M[1:])
assert BURNED_OVER_PERIMETERS_M[0] < -TOLERANCE_M
assert BURNED_OVER_PERIMETERS_M[1] > TOLERANCE_M

def text(ax, x, y, label, *, size=8, ha="left", va="center", color=None, **kwargs):
    return ax.text(x, y, label, fontsize=size, ha=ha, va=va,
                   color=color or COLORS["text"], **kwargs)

def dimension(ax, x1, x2, y, label, *, size=7, label_offset=0.035):
    ax.annotate("", xy=(x1, y), xytext=(x2, y),
                arrowprops=dict(arrowstyle="<->", lw=0.7, color=COLORS["muted"],
                                shrinkA=0, shrinkB=0, mutation_scale=6))
    text(ax, (x1+x2)/2, y+label_offset, label, size=size,
         ha="center", color=COLORS["muted"])

def figure_arrow(fig, x1, x2, y):
    fig.add_artist(Line2D([x1, x2], [y, y], transform=fig.transFigure,
                          lw=0.7, color=COLORS["muted"]))
    fig.add_artist(Line2D([x2-0.006, x2, x2-0.006],
                          [y+0.005, y, y-0.005], transform=fig.transFigure,
                          lw=0.7, color=COLORS["muted"]))

def time_bracket(fig, x1, x2, y):
    fig.add_artist(Line2D([x1, x1, x2, x2], [y-0.007, y, y, y-0.007],
                          transform=fig.transFigure, lw=0.7, color=COLORS["muted"]))
    fig.text((x1+x2)/2, y+0.007, r"$\leq$48 h between observations",
             ha="center", va="bottom", fontsize=7, color=COLORS["muted"])

def observation_map(fig, rect, perimeter_x):
    ax = fig.add_axes(rect)
    ax.set_xlim(-140, 140)
    ax.set_ylim(0, 100)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color(COLORS["border"])
        spine.set_linewidth(0.6)
    ax.add_patch(Rectangle((-140, 0), perimeter_x+140, 100,
                           facecolor=COLORS["fire_area"], edgecolor="none", zorder=0))
    ax.axvspan(perimeter_x-TOLERANCE_M, perimeter_x+TOLERANCE_M,
               facecolor=COLORS["band"], alpha=0.40, zorder=1)
    ax.axvline(perimeter_x, color=COLORS["perimeter"], lw=1.3,
               linestyle=(0, (3, 2)), zorder=2)
    ax.plot([0, 0], [13, 87], color=COLORS["line"], lw=1.8, zorder=3)
    ax.scatter([0], [50], s=18, facecolor=COLORS["blue"],
               edgecolor="white", linewidth=0.5, zorder=4)
    return ax

def build_figure():
    fig = plt.figure(figsize=(7.15, 5.7))
    fig.text(0.015, 0.975, "(a)  Fireline and fireline unit", fontsize=9,
             weight="bold", va="top")
    fig.text(0.515, 0.975, "(b)  Recorded outcome: NIFC", fontsize=9,
             weight="bold", va="top")
    fig.add_artist(Line2D([0.495, 0.495], [0.651, 0.969],
                          transform=fig.transFigure, color=COLORS["border"], lw=0.65))
    fig.add_artist(Line2D([0.015, 0.985], [0.626, 0.626],
                          transform=fig.transFigure, color=COLORS["border"], lw=0.65))

    # (a) Illustrative subdivision plus an enlarged continuous 250 m example.
    ax = fig.add_axes([0.015, 0.65, 0.455, 0.285])
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    text(ax, 0.015, 0.985, "Mapped fireline", size=7.5, va="top")
    x = np.linspace(0.065, 0.94, 301)
    y = 0.785 + 0.043*np.sin((x-0.065)*2.8*np.pi)
    ax.plot(x, y, color=COLORS["muted"], lw=2.3, solid_capstyle="round")
    selected = (x >= 0.357) & (x <= 0.648)
    ax.plot(x[selected], y[selected], color=COLORS["blue"], lw=3.0)
    for boundary in [0.065, 0.357, 0.648, 0.94]:
        by = 0.785 + 0.043*np.sin((boundary-0.065)*2.8*np.pi)
        ax.plot([boundary, boundary], [by-0.035, by+0.035],
                color=COLORS["line"], lw=0.7)
    text(ax, 0.50, 0.665, r"Fireline units, each $\leq$250 m", size=7.5, ha="center")
    ax.annotate("", xy=(0.52, 0.545), xytext=(0.52, 0.615),
                arrowprops=dict(arrowstyle="->", lw=0.75, color=COLORS["muted"]))
    text(ax, 0.555, 0.553, "Enlarged example", size=7, color=COLORS["muted"])
    xpos = 0.08 + 0.84*CHECK_POSITIONS_M/UNIT_LENGTH_M
    ax.plot([0.08, 0.92], [0.33, 0.33], color=COLORS["line"], lw=2)
    ax.scatter(xpos, np.full(10, 0.33), s=16, facecolor=COLORS["blue"],
               edgecolor="white", linewidth=0.4, zorder=3)
    for end in [0.08, 0.92]:
        ax.plot([end, end], [0.29, 0.37], color=COLORS["line"], lw=0.7)
    dimension(ax, xpos[0], xpos[1], 0.46, "25 m", size=7, label_offset=0.055)
    text(ax, 0.565, 0.430, "Positions for NIROPS checks\nand vegetation / terrain sampling", size=7, ha="center")
    dimension(ax, 0.08, 0.92, 0.20, "250 m", size=7.5, label_offset=-0.067)
    text(ax, 0.5, 0.007, "Weather forecasts: interpolated at the\nfireline unit\'s geometric center", size=7, ha="center")

    # (b) Local view of the NIFC final-perimeter label assignment rule.
    ax = fig.add_axes([0.515, 0.65, 0.47, 0.285])
    ax.set(xlim=(-170, 170), ylim=(0, 180))
    ax.axis("off")
    ax.add_patch(Rectangle((-170, 41), 170, 114,
                           facecolor=COLORS["fire_area"], edgecolor="none", zorder=0))
    ax.add_patch(Rectangle((-50, 41), 100, 114,
                           facecolor=COLORS["band"], alpha=0.4, edgecolor="none", zorder=1))
    ax.plot([0, 0], [41, 155], color=COLORS["perimeter"], lw=1.35,
            linestyle=(0, (3, 2)), zorder=2)
    ax.add_patch(Rectangle((-170, 41), 340, 114, facecolor="none",
                           edgecolor=COLORS["border"], lw=0.6))
    text(ax, -112, 146, "Mapped fire area", size=7, ha="center")
    text(ax, 112, 146, "Outside fire area", size=7, ha="center")
    text(ax, 0, 177, "Final fire perimeter", size=7.5, ha="center",
         color=COLORS["perimeter"])
    ax.annotate("", xy=(0, 157), xytext=(0, 168),
                arrowprops=dict(arrowstyle="->", color=COLORS["perimeter"],
                                lw=0.65, mutation_scale=6))
    dimension(ax, -50, 0, 120, "50 m", size=6.8, label_offset=10)
    dimension(ax, 0, 50, 120, "50 m", size=6.8, label_offset=10)
    for lx in [-115, 21, 115]:
        ax.plot([lx, lx], [72, 105], color=COLORS["line"], lw=2.6,
                solid_capstyle="butt", zorder=4)
    text(ax, -115, 57, "Burned Over", size=7, ha="center", weight="bold")
    text(ax, 21, 57, "Held", size=7, ha="center", weight="bold")
    text(ax, 115, 57, "Not Engaged", size=7, ha="center", weight="bold")
    text(ax, -115, 28, ">50 m inside", size=7, ha="center")
    text(ax, 21, 28, "Within 50 m", size=7, ha="center")
    text(ax, 115, 28, ">50 m outside", size=7, ha="center")
    text(ax, 0, 8, "Distances are measured from the final fire perimeter.",
         size=6.8, ha="center", color=COLORS["muted"])

    # (c) Fixed comparison positions, with equal spatial scales in every small map.
    fig.text(0.015, 0.611, "(c)  Timing evidence: NIROPS", fontsize=9,
             weight="bold", va="top")
    fig.text(0.015, 0.577,
             "Successive maps at one fixed position; NIFC outcome labels remain unchanged.",
             fontsize=7.5, va="top", color=COLORS["muted"])
    lefts = [0.20, 0.47, 0.74]
    width = 0.225
    centers = [left+width/2 for left in lefts]
    for center, label in zip(centers,
                              ["First observation", "Next observation", "Additional observations"]):
        fig.text(center, 0.540, label, ha="center", va="center", fontsize=7.5)
    time_bracket(fig, centers[0], centers[1], 0.497)
    held_bottom = 0.383
    map_height = 0.095
    fig.text(0.018, held_bottom+map_height/2, "Recorded\nHeld",
             va="center", fontsize=8, weight="bold", linespacing=1.35)
    for left, px in zip(lefts, HELD_PERIMETERS_M):
        observation_map(fig, [left, held_bottom, width, map_height], px)
    for i in [0, 1]:
        figure_arrow(fig, lefts[i]+width+0.006, lefts[i+1]-0.006,
                     held_bottom+map_height/2)
    for center, label in zip(centers, ["90 m outside", "20 m outside", "10 m outside"]):
        fig.text(center, 0.371, label, ha="center", va="top", fontsize=7.5)
    fig.text(centers[0], 0.345, ">50 m outside", ha="center", va="top",
             fontsize=6.8, color=COLORS["muted"])
    fig.text(centers[1], 0.345, "Within 50 m: approach", ha="center", va="top",
             fontsize=6.8, color=COLORS["muted"])
    fig.text(centers[2], 0.345, "End of illustrated record", ha="center", va="top",
             fontsize=7.0, color=COLORS["muted"])
    fig.text(0.20, 0.308,
             "Held timing support requires follow-up with no observation >50 m inside; follow-up may exceed 48 h.",
             fontsize=6.9, va="center", color=COLORS["muted"])

    bo_bottom = 0.153
    fig.text(0.018, bo_bottom+map_height/2, "Recorded\nBurned Over",
             va="center", fontsize=8, weight="bold", linespacing=1.35)
    time_bracket(fig, centers[0], centers[1], 0.266)
    for left, px in zip(lefts[:2], BURNED_OVER_PERIMETERS_M):
        observation_map(fig, [left, bo_bottom, width, map_height], px)
    figure_arrow(fig, lefts[0]+width+0.006, lefts[1]-0.006,
                 bo_bottom+map_height/2)
    for center, label in zip(centers[:2], ["90 m outside", "90 m inside"]):
        fig.text(center, 0.141, label, ha="center", va="top", fontsize=7.5)
    fig.text(centers[2], bo_bottom+map_height/2,
             "Crossing interval documented\nSupporting pair shown;\nother source observations omitted",
             fontsize=7.1, ha="center", va="center", linespacing=1.5)
    fig.text(0.20, 0.101,
             "Burned Over timing support requires a change from >50 m outside to >50 m inside.",
             fontsize=6.9, va="center", color=COLORS["muted"])

    handles = [
        Line2D([0], [0], color=COLORS["line"], lw=2, label="Mapped fireline"),
        Line2D([0], [0], color=COLORS["perimeter"], lw=1.3,
               linestyle=(0, (3, 2)), label="Fire perimeter"),
        Rectangle((0, 0), 1, 1, facecolor=COLORS["fire_area"], label="Mapped fire area"),
        Rectangle((0, 0), 1, 1, facecolor=COLORS["band"], alpha=0.5,
                  label="50 m tolerance"),
        Line2D([0], [0], marker="o", markersize=3.5, linestyle="none",
               color=COLORS["blue"], label="Fixed sampling position"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.042),
               frameon=False, ncol=5, handlelength=1.5, columnspacing=1.15,
               fontsize=6.7, borderpad=0.0)
    fig.text(0.5, 0.019,
             "Schematic examples, not observed results. Additional fireline-unit selection criteria apply.",
             fontsize=6.8, ha="center", va="center", color=COLORS["muted"])
    return fig

fig = build_figure()


fig.savefig(OUTPUT/f"{STEM}.pdf", metadata={"Title":"Fireline units, NIFC labels, and NIROPS timing evidence", "Subject":"Illustrative scientific schematic; not empirical results", "Creator":"Notebook 07D using Matplotlib"})
fig.savefig(OUTPUT/f"{STEM}.png",dpi=400)
fig.savefig(OUTPUT/f"{STEM}.svg",format="svg")
plt.close(fig)
print("Saved schematic PDF, PNG, and SVG.")
