"""Rebuild a real NIFC--NIROPS illustration from saved, unchanged study data.

Run with the project .venv Python. No model is fitted and no source is modified.
The root manuscript-map notebook calls main() from this helper.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
FID = "0109FB7F8227489F80E887DFCFC9C69D"
UNIT_IDS = {
    "Held": f"L::{FID}_00afef075dce8aed8ba980307ef4f6a00f1e0289_c0_s0",
    "Burned Over": f"L::{FID}_dd634dcf265875e48b382a750b9cfcc5c3c828cf_c0_s0",
}
BASE = ROOT / "data/processed/fireline_corrected_local_250m_10m"
FILES = {
    "retained": ROOT / "zenodo_upload_v1/data/retained_fireline_units.parquet",
    "units": BASE / f"units/{FID}.parquet",
    "parents": BASE / f"canonical_parent_shards/{FID}.parquet",
    "points": BASE / f"point_evidence/{FID}.parquet",
    "trajectories": BASE / f"trajectories/{FID}.npz",
    "perimeters": ROOT / "data/processed/fireline_extended_exact_approach_v3/nirops_progression_cache/nirops_dynamic_382_progression_epsg5070.parquet",
}
COLORS = {"Held": "#0072B2", "Burned Over": "#D55E00"}
FOLLOWUP = "#8064A2"
AREA = "#F0F0F0"
BAND = "#C8C8C8"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def series(geometry):
    return gpd.GeoSeries([geometry], crs=32612)


def bounds_square(bounds, pad):
    xmin, ymin, xmax, ymax = bounds
    side = max(xmax - xmin, ymax - ymin) + 2 * pad
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    return [cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2]


def configure_map(ax, bounds):
    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#8A8A8A")
        spine.set_linewidth(0.6)


def scale_and_north(ax, bounds, length, label):
    x0, y0, x1, y1 = bounds
    width, height = x1 - x0, y1 - y0
    x, y = x0 + 0.075 * width, y0 + 0.08 * height
    ax.plot([x, x + length], [y, y], color="#202020", linewidth=1.5, zorder=20)
    ax.plot([x, x], [y - 0.01 * height, y + 0.01 * height], color="#202020", linewidth=1, zorder=20)
    ax.plot([x + length, x + length], [y - 0.01 * height, y + 0.01 * height], color="#202020", linewidth=1, zorder=20)
    ax.text(x + length / 2, y + 0.025 * height, label, ha="center", va="bottom", fontsize=8,
            bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=0.8), zorder=21)
    # Geographic north projected into UTM, rather than assuming grid north.
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lon, lat = Transformer.from_crs(32612, 4326, always_xy=True).transform(cx, cy)
    nx, ny = Transformer.from_crs(4326, 32612, always_xy=True).transform(lon, lat + 0.01)
    vec = np.array([nx - cx, ny - cy]); vec /= np.linalg.norm(vec)
    tail = np.array([x1 - 0.10 * width, y0 + 0.10 * height])
    tip = tail + vec * 0.11 * height
    ax.annotate("", xy=tip, xytext=tail,
                arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#202020"), zorder=21)
    ax.text(tip[0], tip[1] + 0.012 * height, "N", ha="center", va="bottom", fontsize=8, zorder=21)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    retained = pd.read_parquet(
        FILES["retained"], filters=[("_irwin_norm", "==", FID)],
        columns=["unit_uid", "_irwin_norm", "IncidentName", "Year", "_engagement_norm",
                 "prediction_anchor_idx", "prediction_anchor_utc", "actual_line_length_m"],
    )
    units = gpd.read_parquet(FILES["units"])
    chosen = units.loc[units.unit_uid.isin(UNIT_IDS.values())].copy()
    parents = gpd.read_parquet(FILES["parents"])
    points = pd.read_parquet(FILES["points"])
    chosen_points = points.loc[points.unit_uid.isin(UNIT_IDS.values())].copy()
    perimeters = gpd.read_parquet(
        FILES["perimeters"], filters=[("_irwin_04a", "==", FID.lower())]
    ).sort_values("_time_04a").reset_index(drop=True)
    trajectories = np.load(FILES["trajectories"])
    signed = trajectories["signed"]
    # Archived field name says ns, but values are microseconds since epoch.
    times = pd.to_datetime(trajectories["times_ns"], unit="us", utc=True)
    assert np.array_equal(times.asi8, pd.to_datetime(perimeters._time_04a, utc=True).array.asi8)
    assert len(chosen) == 2 and set(chosen.unit_uid) <= set(retained.unit_uid)
    assert len(times) == 7 and times[1] - times[0] == pd.Timedelta(hours=18.5)
    assert chosen.crs.to_epsg() == 5070
    assert chosen.geometry.geom_type.eq("LineString").all()
    assert np.allclose(chosen.actual_line_length_m, 250, atol=1e-7)

    checks = {}
    for outcome, uid in UNIT_IDS.items():
        row = chosen.loc[chosen.unit_uid.eq(uid)].iloc[0]
        release_row = retained.loc[retained.unit_uid.eq(uid)].iloc[0]
        parent = parents.loc[parents._geom_hash.eq(row._geom_hash)]
        pts = chosen_points.loc[chosen_points.unit_uid.eq(uid)].copy()
        distances = signed[pts.sample_row_index.to_numpy(dtype=int), :]
        assert len(parent) == 1 and parent.iloc[0]._engagement_norm == outcome
        assert row._engagement_norm == release_row._engagement_norm == outcome
        assert release_row.prediction_anchor_idx == 0
        assert pd.to_datetime(release_row.prediction_anchor_utc, utc=True) == times[0]
        assert len(pts) == 11 and pts.point_evidence.eq("temporally_supported").all()
        assert (distances[:, 0] > 50).all()
        dominant_count = int((pts.event_start_idx.eq(0) & pts.event_end_idx.eq(1)).sum())
        assert dominant_count / len(pts) >= 0.5
        if outcome == "Held":
            assert (distances[:, 1:] >= -50).all()
            assert dominant_count == 10
        else:
            assert (distances[:, 1] < -50).all() and dominant_count == 11
        checks[outcome] = {
            "unit_uid": uid,
            "unit_row_index": int(row.unit_row_index),
            "source_index": int(row.source_index),
            "source_geometry_hash": row._geom_hash,
            "recorded_type": row.FeatureCategory,
            "inherited_source_label_verified": True,
            "retained_release_membership_verified": True,
            "analysis_crs_length_m": float(row.actual_line_length_m),
            "checked_positions": len(pts),
            "supported_positions": int(pts.point_evidence.eq("temporally_supported").sum()),
            "positions_supporting_first_interval": dominant_count,
            "prediction_anchor_idx": 0,
            "prediction_anchor_utc": times[0].isoformat(),
            "sample_row_indices": pts.sample_row_index.astype(int).tolist(),
            "saved_raster_signed_distance_ranges_m": [
                [float(distances[:, j].min()), float(distances[:, j].max())] for j in range(len(times))
            ],
            "distance_range_note": "Saved signed distances are capped at -251/+251 m; sentinel values are not exact distances.",
        }

    projected = chosen.to_crs(32612)
    parent_projected = parents.to_crs(32612)
    perimeter_projected = perimeters.to_crs(32612)
    point_geometry = gpd.GeoDataFrame(
        chosen_points,
        geometry=gpd.points_from_xy(chosen_points.x_m, chosen_points.y_m), crs=5070,
    ).to_crs(32612)
    zoom = bounds_square(projected.total_bounds, pad=165)
    context = bounds_square(perimeter_projected.total_bounds, pad=370)
    clip = box(*zoom)

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "axes.titlesize": 10, "pdf.fonttype": 42, "ps.fonttype": 42,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 3.5), gridspec_kw={"wspace": 0.11})
    fig.subplots_adjust(left=0.025, right=0.99, bottom=0.24, top=0.79)

    # Fire context: last available NIROPS observation, never a purported NIFC final perimeter.
    ax = axes[0]
    last = perimeter_projected.geometry.iloc[-1]
    series(last).plot(ax=ax, color=AREA, edgecolor="#595959", linewidth=0.7, zorder=1)
    parent_projected.plot(ax=ax, color="#B5B5B5", linewidth=0.35, zorder=2)
    for outcome, uid in UNIT_IDS.items():
        projected.loc[projected.unit_uid.eq(uid)].plot(ax=ax, color=COLORS[outcome], linewidth=2, zorder=4)
    ax.add_patch(Rectangle((zoom[0], zoom[1]), zoom[2] - zoom[0], zoom[3] - zoom[1],
                           fill=False, edgecolor="#333333", linewidth=0.9, zorder=5))
    ax.annotate("Panels (b, c)", xy=(zoom[2], zoom[3]),
                xytext=(context[0] + 0.46 * (context[2]-context[0]), context[1] + 0.20 * (context[3]-context[1])),
                arrowprops=dict(arrowstyle="-", color="#333333", lw=0.65), fontsize=8,
                ha="left", va="center", zorder=8)
    configure_map(ax, context)
    scale_and_north(ax, context, 2000, "2 km")
    ax.set_title("(a) Fire context", loc="left", pad=7, fontweight="bold")
    ax.text(0, 1.18, "Deep Creek Canyon, 2021", transform=ax.transAxes, fontsize=9, ha="left")
    ax.text(0, -0.09, "NIROPS extent: 1 July, 03:45 UTC", transform=ax.transAxes, fontsize=7.2, ha="left")

    for ax, stage in zip(axes[1:], [0, 1]):
        geometry = perimeter_projected.geometry.iloc[stage]
        series(geometry.intersection(clip)).plot(ax=ax, facecolor=AREA, edgecolor="none", zorder=1)
        band = geometry.boundary.buffer(50).intersection(clip)
        series(band).plot(ax=ax, color=BAND, edgecolor="none", zorder=2)
        series(geometry.boundary.intersection(clip)).plot(ax=ax, color="#444444", linewidth=1.05, zorder=3)
        if stage == 1:
            followup = perimeter_projected.geometry.iloc[2].boundary.intersection(clip)
            series(followup).plot(ax=ax, color=FOLLOWUP, linewidth=1.2, linestyle=(0, (3, 2)), zorder=4)
        for outcome, uid in UNIT_IDS.items():
            unit = projected.loc[projected.unit_uid.eq(uid)]
            pts = point_geometry.loc[point_geometry.unit_uid.eq(uid)]
            unit.plot(ax=ax, color=COLORS[outcome], linewidth=2.3, zorder=6)
            pts.plot(ax=ax, color=COLORS[outcome], edgecolor="white", linewidth=0.35,
                     markersize=10, zorder=7)
            center = unit.geometry.iloc[0].interpolate(0.5, normalized=True)
            offset = 100 if outcome == "Held" else -105
            ax.annotate(outcome, xy=(center.x, center.y), xytext=(center.x, center.y + offset),
                        ha="center", va="center", fontsize=8, color=COLORS[outcome],
                        bbox=dict(facecolor="white", alpha=0.9, edgecolor="none", pad=1.3),
                        arrowprops=dict(arrowstyle="-", color=COLORS[outcome], lw=0.7), zorder=15)
        configure_map(ax, zoom)
        scale_and_north(ax, zoom, 200, "200 m")
    axes[1].set_title("(b) Prediction time", loc="left", pad=7, fontweight="bold")
    axes[2].set_title("(c) Approach / crossing", loc="left", pad=7, fontweight="bold")
    axes[1].text(0, 1.18, "16 June, 05:00 UTC", transform=axes[1].transAxes, fontsize=9)
    axes[2].text(0, 1.18, "16 June, 23:30 UTC", transform=axes[2].transAxes, fontsize=9)
    axes[1].text(0, -0.09, "Both units outside the mapped fire area", transform=axes[1].transAxes, fontsize=7.2)
    axes[2].text(0, -0.09, "Follow-up: 17 June, 08:08 UTC", transform=axes[2].transAxes, fontsize=7.2)

    handles = [
        Line2D([], [], color=COLORS["Held"], lw=2.2, label="NIFC Held unit"),
        Line2D([], [], color=COLORS["Burned Over"], lw=2.2, label="NIFC Burned Over unit"),
        Line2D([], [], color="#555555", marker="o", markersize=3.5, linestyle="none", label="Checked position"),
        Patch(facecolor=AREA, edgecolor="#444444", linewidth=0.8, label="NIROPS fire area"),
        Patch(facecolor=BAND, edgecolor="none", label="50 m perimeter band"),
        Line2D([], [], color=FOLLOWUP, lw=1.2, linestyle=(0, (3, 2)), label="NIROPS follow-up perimeter"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.51, 0.025),
               ncol=3, frameon=False, fontsize=8, columnspacing=1.5,
               handlelength=2.0, handletextpad=0.6, labelspacing=0.9)
    figure_base = OUT / "nifc_nirops_observed_example"
    fig.savefig(figure_base.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.07,
                metadata={"Title": "NIFC fireline units and NIROPS timing: Deep Creek Canyon, 2021",
                          "Author": "Fireline-outcome study"})
    fig.savefig(figure_base.with_suffix(".png"), dpi=350, bbox_inches="tight", pad_inches=0.07)
    plt.close(fig)

    # Small extracts allow independent checking without reopening the entire archive.
    projected.to_crs(4326).to_file(OUT / "selected_fireline_units.geojson", driver="GeoJSON")
    perimeter_projected.to_crs(4326).to_file(OUT / "selected_fire_nirops_perimeters.geojson", driver="GeoJSON")
    point_geometry.drop(columns="geometry").to_csv(OUT / "selected_checked_positions.csv", index=False)
    per_position = []
    for _, row in chosen_points.iterrows():
        for j, timestamp in enumerate(times):
            per_position.append({"unit_uid": row.unit_uid, "sample_row_index": int(row.sample_row_index),
                                 "observation_index": j, "observation_utc": timestamp.isoformat(),
                                 "signed_distance_m_capped": float(signed[int(row.sample_row_index), j])})
    pd.DataFrame(per_position).to_csv(OUT / "checked_position_trajectories.csv", index=False)
    provenance = {
        "fire_name": "Deep Creek Canyon", "year": 2021, "normalized_fire_id": FID,
        "selection_rationale": "A compact pair of retained 250 m units with different recorded outcomes, the same prediction time, clear saved timing evidence, and readable nearby geometry; model predictions were not used for example selection.",
        "retained_fire_units": len(retained), "retained_outcomes": retained._engagement_norm.value_counts().to_dict(),
        "original_analysis_crs": "EPSG:5070", "figure_crs": "EPSG:32612", "geojson_crs": "EPSG:4326",
        "saved_checked_position_coordinate_crs": "EPSG:5070",
        "timestamp_integer_unit": "us",
        "observation_times_utc": [t.isoformat() for t in times],
        "time_note": "Recorded archive times approximate imagery collection times. The figure does not locate exact fire-contact times.",
        "depicted_observation_indices": [0, 1, 2], "context_observation_index": 6,
        "approach_crossing_interval_hours": 18.5,
        "held_subsequent_observations_checked": 5, "held_followup_boundary_shown_index": 2,
        "label_provenance": "NIFC source fireline records supply labels. NIROPS supplies compatibility and timing evidence, not independent label validation.",
        "sampling_note": "The figure uses the 11 saved checked positions on each 250 m unit, not newly generated points. Evidence used a 25 m grid. The displayed 50 m band is drawn from the vector perimeter for legibility; the saved grid distances and vector distances can differ near the threshold.",
        "context_note": "The 1 July NIROPS extent is the last available NIROPS observation for this fire, not the NIFC final fire perimeter. Thin gray context lines are NIFC source fireline records, not necessarily whole constructed firelines.",
        "units": checks,
        "sources": {name: {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                           "sha256": sha256(path)} for name, path in FILES.items()},
        "checks_passed": ["Both selected unit IDs occur in the final retained release", "NIFC source-record label inheritance matches",
                          "Each selected analysis geometry is a 250 m LineString", "Saved and vector timestamps agree",
                          "All checked positions begin more than 50 m outside the saved fire area",
                          "Held: all 11 positions supported, no checked position more than 50 m inside in any later observation",
                          "Held: 10 of 11 positions support the first interval; 1 supports the next interval",
                          "Burned Over: all 11 positions cross from more than 50 m outside to more than 50 m inside within 18.5 hours"],
    }
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps({"pdf": str(figure_base.with_suffix(".pdf")), "png": str(figure_base.with_suffix(".png")),
                      "fire": provenance["fire_name"], "retained_units": len(retained), "checks": "passed"}, indent=2))


if __name__ == "__main__":
    main()

