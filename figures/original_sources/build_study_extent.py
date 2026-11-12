"""Plot the verified retained-fire locations with Census cartographic boundaries.

This script writes only assets under its own new output directory. Source model
data, source maps, manuscript files, and prior supplementary figures are read-only.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib import patheffects
from pyproj import Transformer
from shapely.geometry import LineString, box

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE = ROOT / "outputs/08_condition_outcomes/08E_20261105T211309_533108Z_9ff65f/fire_locations_and_sizes.csv"
BOUNDARY = OUT / "boundaries/cb_2023_us_state_20m.shp"
BOUNDARY_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip"

fires = pd.read_csv(SOURCE)
assert len(fires) == fires._irwin_norm.nunique() == 381
assert int(fires.fireline_units.sum()) == 304143
assert set(fires.Year) == set(range(2020, 2025))
assert fires[["longitude", "latitude"]].notna().all().all()
expected_fires = {2020: 89, 2021: 87, 2022: 54, 2023: 47, 2024: 104}
assert fires.groupby("Year").size().to_dict() == expected_fires

states = gpd.read_file(BOUNDARY).to_crs(5070)
conus = states.loc[~states.STUSPS.isin(["AK", "HI", "PR", "VI", "GU", "MP", "AS"])].copy()
locations = gpd.GeoDataFrame(
    fires, geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs=4326
).to_crs(5070)
tf = Transformer.from_crs(4326, 5070, always_xy=True)

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 9.0, "axes.labelsize": 9, "legend.fontsize": 9,
    "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.facecolor": "white",
})
fig = plt.figure(figsize=(7.2, 6.25))
ax = fig.add_axes([0.065, 0.09, 0.715, 0.87])
xmin, xmax = -2500000.0, -570000.0
ymin, ymax = 910000.0, 3230000.0
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
ax.set_aspect("equal")
ax.set_facecolor("#f7fafc")
conus.plot(ax=ax, facecolor="#f3f2ee", edgecolor="#9a9a9a", linewidth=0.60, zorder=2)
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
frame = box(xmin, ymin, xmax, ymax)

# Graticules are projected explicitly; no longitude-latitude aspect approximation.
for lon in [-125, -120, -115, -110, -105]:
    ys = np.linspace(29, 52, 350)
    x, y = tf.transform(np.full_like(ys, lon), ys)
    ax.plot(x, y, color="#c8cbd0", lw=.45, ls=(0, (3, 3)), zorder=3)
    g = LineString(np.column_stack([x, y])).intersection(frame.boundary)
    pts = list(g.geoms) if hasattr(g, "geoms") else [g]
    pts = [p for p in pts if p.geom_type == "Point"]
    if pts:
        p = min(pts, key=lambda p:p.y)
        if abs(p.y-ymin)<1:
            ax.annotate(f"{abs(lon)}°W", (p.x,p.y), xytext=(0,-6), textcoords="offset points", ha="center", va="top", fontsize=8)
for lat in [35, 40, 45, 50]:
    xs = np.linspace(-130, -99, 350)
    x, y = tf.transform(xs, np.full_like(xs, lat))
    ax.plot(x, y, color="#c8cbd0", lw=.45, ls=(0, (3, 3)), zorder=3)
    g = LineString(np.column_stack([x,y])).intersection(frame.boundary)
    pts = list(g.geoms) if hasattr(g, "geoms") else [g]
    pts = [p for p in pts if p.geom_type == "Point"]
    if pts:
        p = min(pts, key=lambda p:p.x)
        if abs(p.x-xmin)<1:
            ax.annotate(f"{lat}°N", (p.x,p.y), xytext=(-6,0), textcoords="offset points", ha="right", va="center", fontsize=8)

# State abbreviations are geographic context, not analytical regions.
label_lonlat = {
    "WA":(-120.5,47.4), "OR":(-120.4,44.0), "CA":(-119.1,36.5),
    "NV":(-116.8,39.0), "ID":(-114.1,44.0), "MT":(-109.6,47.0),
    "WY":(-107.5,43.1), "UT":(-111.6,39.1), "CO":(-106.3,38.7),
    "AZ":(-112.1,34.0), "NM":(-106.7,33.6),
}
for label,(lon,lat) in label_lonlat.items():
    x,y=tf.transform(lon,lat)
    ax.text(x,y,label,ha="center",va="center",fontsize=9.5,color="#6f6f6f",zorder=4,
            path_effects=[patheffects.withStroke(linewidth=2.2,foreground="#f3f2ee")])

colors={2020:"#0072B2",2021:"#E69F00",2022:"#009E73",2023:"#CC79A7",2024:"#D55E00"}
# Interleave the year groups to avoid placing every point of one year above others.
order=locations.sample(frac=1,random_state=20261110)
for _, row in order.iterrows():
    ax.scatter(row.geometry.x,row.geometry.y,s=20,c=colors[int(row.Year)],
               edgecolors="white",linewidths=.35,alpha=.92,zorder=5)
example_id = "0109FB7F8227489F80E887DFCFC9C69D"
example = locations.loc[locations._irwin_norm.eq(example_id)]
assert len(example) == 1 and int(example.iloc[0].Year) == 2021
example_point = example.iloc[0].geometry
# Overlay at the existing representative coordinate; no study point is displaced.
ax.scatter(example_point.x, example_point.y, s=91, marker="*", facecolor="#222222",
           edgecolor="white", linewidth=.6, zorder=7)
assert sum((locations.Year==year).sum() for year in colors)==381
assert locations.geometry.x.between(xmin,xmax).all()
assert locations.geometry.y.between(ymin,ymax).all()
ax.set_xticks([]);ax.set_yticks([])
for spine in ax.spines.values():spine.set_color("#8b8b8b");spine.set_linewidth(.6)

locator=fig.add_axes([.800,.745,.183,.17])
conus.plot(ax=locator,facecolor="#f3f2ee",edgecolor="#b3b3b3",linewidth=.23)
locator.add_patch(Rectangle((xmin,ymin),xmax-xmin,ymax-ymin,fill=False,ec="#333333",lw=.85))
locator.set_xlim(-2520000,2340000);locator.set_ylim(200000,3280000)
locator.set_aspect("equal");locator.axis("off")
locator.text(.5,1.07,"Study region",ha="center",va="bottom",transform=locator.transAxes,fontsize=9)

handles=[Line2D([],[],marker="o",color="none",markerfacecolor=colors[y],
                markeredgecolor="white",markeredgewidth=.4,markersize=5.5,
                label=f"{y}  ({expected_fires[y]})") for y in colors]
fig.legend(handles=handles,title="Fire year (count)",loc="upper left",bbox_to_anchor=(.790,.63),
           frameon=False,handletextpad=.35,labelspacing=.85,title_fontsize=9)
example_handle=Line2D([],[],marker="*",color="none",markerfacecolor="#222222",
                      markeredgecolor="white",markeredgewidth=.4,markersize=9,
                      label="Deep Creek Canyon\n(2021 example)")
fig.legend(handles=[example_handle],loc="upper left",bbox_to_anchor=(.790,.405),
           frameon=False,handletextpad=.35,fontsize=8.4)
fig.text(.803,.33,"381 fires\n304,143 fireline units",ha="left",va="top",fontsize=8.6,linespacing=1.55)

# Metric scale in the Albers projection, located in the unobstructed ocean area.
sx,sy=xmin+100000,ymin+110000
ax.plot([sx,sx+500000],[sy,sy],color="#444444",lw=1,zorder=6)
for xx in [sx,sx+250000,sx+500000]: ax.plot([xx,xx],[sy-12000,sy+12000],color="#444444",lw=.8,zorder=6)
for xx,lab in [(sx,"0"),(sx+250000,"250"),(sx+500000,"500 km")]:
    ax.text(xx,sy-29000,lab,ha="center",va="top",fontsize=7.8,zorder=6)
fig.text(.065,.015,"State boundaries: U.S. Census Bureau (2023).  Projection: NAD83 / Conus Albers.",ha="left",fontsize=7.1,color="#555555")

fig.savefig(OUT/"fig_study_extent.pdf",bbox_inches="tight",pad_inches=.04)
fig.savefig(OUT/"fig_study_extent.png",dpi=320,bbox_inches="tight",pad_inches=.04)
plt.close(fig)

caption=(
    "Geographic coverage of the retained study dataset, 2020--2024. Each point marks the "
    "arithmetic mean longitude and latitude of the retained fireline units from one fire. "
    "All 381 fires and 304,143 fireline units are represented. Color indicates fire year, "
    "and circular marker size is constant. A star identifies Deep Creek Canyon (2021), "
    "the fire used for the illustrative fireline example. Points describe representative study locations rather "
    "than ignition locations or burned-area boundaries. The inset locates the map within "
    "the conterminous United States. State boundaries are from the U.S. Census Bureau's "
    "2023 cartographic boundary files."
)
(OUT/"caption.txt").write_text(caption,encoding="utf-8")
provenance={
    "figure":"fig_study_extent.pdf", "source_csv":str(SOURCE),
    "source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "source_notebook":"notebooks/08E_reviewer_diagnostics.ipynb",
    "source_operation":"groupby fire identifier and Year; mean longitude/latitude of retained units",
    "fire_count":381,"fireline_unit_count":304143,"fires_by_year":expected_fires,
    "marker_size_points_squared":20,"marker_meaning":"one source fire identifier",
    "does_not_show":["ignition locations","burned footprints","fire perimeter centroids","geographic holdout split"],
    "boundary_source":BOUNDARY_URL,"boundary_scale":"1:20,000,000",
    "boundary_zip_sha256":hashlib.sha256((OUT/'cb_2023_us_state_20m.zip').read_bytes()).hexdigest(),
    "display_crs":"EPSG:5070 (NAD83 / Conus Albers)","input_point_crs":"EPSG:4326",
    "display_bounds_projected_m":[xmin,ymin,xmax,ymax],
    "point_bounds_lonlat":locations.to_crs(4326).total_bounds.tolist(),
    "all_points_within_display":True,
    "illustrative_fire":{"source_fire_identifier":example_id,"name":"Deep Creek Canyon","year":2021,
                         "longitude":float(example.iloc[0].longitude),"latitude":float(example.iloc[0].latitude),
                         "marker":"black star overlaid at the existing representative coordinate; no point displacement"},
}
(OUT/"provenance.json").write_text(json.dumps(provenance,indent=2),encoding="utf-8")
print(json.dumps({"fires":381,"units":304143,"output":str(OUT)},indent=2))
