"""Terrain classification, polyline clipping, hex snapping, and lens domain helpers."""

from __future__ import annotations

import math

LAND, OCEAN, COAST, LAKE = 0, 1, 2, 3
COAST_DEPTH_M = -200

WATER_TABLE = [
    {"id": LAND, "name": "Land", "rule": "Land hex within Central Asia or neighboring Eurasia."},
    {"id": OCEAN, "name": "Deep sea", "color": "#1b4266", "rule": "Caspian Sea deeper than 200 m and not next to land."},
    {"id": COAST, "name": "Shallow coast", "color": "#2d6d97", "rule": "Caspian shelf next to land or shallower than 200 m."},
    {"id": LAKE, "name": "Inland lake", "color": "#3a80b0", "rule": "Major inland lake (Aral Sea, Lake Balkhash, Issyk-Kul, Zaysan, Alakol, Aydarkul)."},
]

RELIEF_TABLE = [
    {"id": 0, "name": "Flat", "rule": "Low local elevation spread (plains, steppes, deserts, river valleys)."},
    {"id": 1, "name": "Hills", "rule": "Moderate relief (uplands, foothills, Kazakh Uplands, Ustyurt escarpment)."},
    {"id": 2, "name": "Mountains", "rule": "High relief (Tian Shan, Altai, Kopet Dag, Pamir foothills)."},
    {"id": 3, "name": "Alpine peaks", "rule": "Extreme alpine relief above 3,000 m (High Pamirs, Central Tian Shan, Khan Tengri)."},
]

COVER = [
    {"id": 1, "key": "forest_deciduous", "name": "Deciduous & walnut forest", "color": "#4f7a35", "rule": "MODIS deciduous broadleaf/needleleaf forest"},
    {"id": 2, "key": "forest_evergreen", "name": "Mountain & taiga forest", "color": "#335e2c", "rule": "MODIS evergreen forest (Altai & Tian Shan spruce)"},
    {"id": 3, "key": "forest_mixed", "name": "Mixed woodland", "color": "#446e32", "rule": "MODIS mixed forest & woody savanna"},
    {"id": 4, "key": "scrub", "name": "Semi-desert & scrub", "color": "#b89f6d", "rule": "MODIS shrubland (Betpak-Dala, Ustyurt, Kyzylkum margins)"},
    {"id": 5, "key": "grassland", "name": "Steppe grassland", "color": "#c9a865", "rule": "MODIS grassland (Great Kazakh Steppe)"},
    {"id": 6, "key": "pasture", "name": "Alpine pasture & foothills", "color": "#94ad5c", "rule": "MODIS savanna & mountain jailoo pasture"},
    {"id": 7, "key": "cropland", "name": "Cropland & irrigated oasis", "color": "#d4bc52", "rule": "MODIS cropland (Northern wheat belt, Fergana, Zarafshan & Amu Darya oases)"},
    {"id": 8, "key": "wetland", "name": "Delta & wetland", "color": "#4b7f8c", "rule": "MODIS permanent wetlands (Syr Darya, Amu Darya & Ili deltas)"},
    {"id": 9, "key": "urban", "name": "Urban & built-up", "color": "#a89f96", "rule": "MODIS urban & built-up footprint"},
    {"id": 10, "key": "barren", "name": "Desert & barren rock", "color": "#c9bca3", "rule": "MODIS barren sand desert (Karakum, Kyzylkum) & alpine rock"},
    {"id": 11, "key": "ice", "name": "Glaciers & permanent snow", "color": "#e8eff5", "rule": "MODIS snow/ice & alpine peaks above 4,000 m"},
]

DOMAIN_NOTE = "Colour range spans the 2nd–98th percentile of hexes."


def classify_relief(elevs: list[float]) -> int:
    if not elevs:
        return 0
    spread = max(elevs) - min(elevs)
    peak = max(elevs)
    mean_z = sum(elevs) / len(elevs)
    if (peak >= 3800 and spread >= 500) or mean_z >= 3500:
        return 3
    if (peak >= 2200 and spread >= 350) or spread >= 700 or mean_z >= 2100:
        return 2
    if spread >= 180 or mean_z >= 900:
        return 1
    return 0


def is_valley_floor(elevs: list[float]) -> bool:
    if len(elevs) < 4:
        return False
    s = sorted(elevs)
    low = s[: max(3, int(len(s) * 0.6))]
    return (low[-1] - low[0]) < 60 and low[-1] < 500


def clip_polyline(pts: list[tuple[float, float]], width: float, height: float) -> list[list[tuple[float, float]]]:
    segs: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for x, y in pts:
        inside = -20 <= x <= width + 20 and -20 <= y <= height + 20
        if inside:
            cur.append((x, y))
        else:
            if len(cur) >= 2:
                segs.append(cur)
            cur = []
    if len(cur) >= 2:
        segs.append(cur)
    return segs


def hex_ring(grid, cell: int, radius: int) -> list[int]:
    if radius <= 0:
        return [cell]
    visited = {cell}
    frontier = {cell}
    for _ in range(radius):
        nxt = set()
        for u in frontier:
            for v in grid.neighbours(u):
                if v not in visited:
                    visited.add(v)
                    nxt.add(v)
        frontier = nxt
    return sorted(frontier)


def nearest_land(grid, owner: list[int], cell: int, max_rings: int = 4) -> int | None:
    if 0 <= cell < len(owner) and owner[cell] >= 0:
        return cell
    for ring in range(1, max_rings + 1):
        for nb in hex_ring(grid, cell, ring):
            if owner[nb] >= 0:
                return nb
    return None


def free_cell(grid, owner: list[int], cell: int, taken: set[int], max_rings: int = 2) -> int | None:
    if cell not in taken and owner[cell] >= 0:
        return cell
    for ring in range(1, max_rings + 1):
        for nb in hex_ring(grid, cell, ring):
            if owner[nb] >= 0 and nb not in taken:
                return nb
    return None


def percentile_domain(values: list[float | None], log: bool = False) -> list[float]:
    nums = sorted(v for v in values if v is not None and (not log or v > 0))
    if not nums:
        return [0.0, 1.0]
    lo = nums[max(0, int(0.02 * (len(nums) - 1)))]
    hi = nums[min(len(nums) - 1, int(0.98 * (len(nums) - 1)))]
    if hi <= lo:
        hi = lo + (1.0 if not log else max(1.0, lo))
    return [round(float(lo), 4), round(float(hi), 4)]
