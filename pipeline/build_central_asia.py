"""Build the Central Asia edition (Uzbekistan, Kazakhstan, Kyrgyzstan, Tajikistan, Turkmenistan).

Reads real public datasets fetched by `pipeline.fetch_ca` into data/raw/central_asia/:
  - Natural Earth 1:10m countries, admin-1 regions, lakes, rivers, roads, railroads
  - NOAA ETOPO1 global relief (5 arc-min)
  - NASA GIBS MODIS Combined L3 IGBP Land Cover (2022)
  - World Resources Institute Global Power Plant Database v1.3.0
  - OurAirports global airports CSV
  - World Bank World Development Indicators (2019–2025)

Outputs all 17 EarthCiv v3 contract JSON files into web/data/ca5/ and updates web/data/editions.json.
"""

from __future__ import annotations

import csv
import heapq
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import LineString, MultiLineString, Point, Polygon, shape
from shapely.ops import transform as shp_transform

from .geo_helpers import (
    COAST,
    COAST_DEPTH_M,
    COVER,
    DOMAIN_NOTE,
    LAKE,
    LAND,
    OCEAN,
    RELIEF_TABLE,
    WATER_TABLE,
    classify_relief,
    clip_polyline,
    free_cell,
    hex_ring,
    is_valley_floor,
    nearest_land,
    percentile_domain,
)
from .ca_data import (
    ADMIN1_STATS,
    AIRPORT_TRAFFIC,
    CITIES,
    DISASTERS,
    EXTRA_RESOURCES,
    MILITARY_BASES,
    MILITARY_RANGES,
    NE_ADMIN1_RENAME,
    PORTS,
    REPUBLICS,
    SPECIALTY_INDUSTRY_WEIGHTS,
    TRADE_CORRIDORS,
    WONDERS,
)
from .core.fetch import read_manifest
from .core.hexgrid import HexGrid
from .core.paths import RAW, WEB
from .core.store import atomic_write_text

RAW_DIR = RAW / "central_asia"
OUT_DIR = WEB / "data" / "ca5"

RADIUS = 25.0
MARGIN = 220.0

# Albers Equal-Area Conic centered squarely on Central Asia (lon 67E, lat 45N)
AEA_PROJ = "+proj=aea +lat_1=38 +lat_2=52 +lat_0=45 +lon_0=67 +datum=WGS84 +units=m +no_defs"
TO_AEA = Transformer.from_crs("EPSG:4326", AEA_PROJ, always_xy=True)
FROM_AEA = Transformer.from_crs(AEA_PROJ, "EPSG:4326", always_xy=True)

CA_ISOS = {r["abbr"] for r in REPUBLICS}
ISO2_TO_IDX = {r["abbr"]: i for i, r in enumerate(REPUBLICS)}
ISO3_TO_ISO2 = {r["iso3"]: r["abbr"] for r in REPUBLICS}

# MODIS IGBP RGB palette (from NASA GIBS MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual) -> EarthCiv cover id
# Cover ids: 1 deciduous, 2 evergreen, 3 mixed, 4 scrub, 5 grassland, 6 pasture, 7 cropland, 8 wetland, 9 urban, 10 barren, 11 ice
MODIS_RGB_TO_COVER = {
    (33, 138, 33): 2,    # Evergreen needleleaf/broadleaf forest
    (49, 204, 49): 1,    # Deciduous broadleaf forest
    (150, 250, 150): 1,  # Deciduous needleleaf / light deciduous
    (141, 186, 141): 3,  # Mixed forest / woody savanna
    (152, 204, 49): 3,   # Closed woody / forest transition
    (186, 141, 141): 4,  # Closed shrublands
    (245, 222, 179): 4,  # Open shrublands (semi-desert)
    (218, 235, 157): 6,  # Savannas / mountain pasture
    (153, 147, 86): 6,   # Woody pasture / foothills
    (240, 185, 103): 5,  # Grasslands / Great Steppe
    (71, 131, 181): 8,   # Permanent wetlands
    (250, 239, 115): 7,  # Croplands
    (255, 213, 0): 7,    # Cropland / natural vegetation mosaic
    (255, 0, 0): 9,      # Urban and built-up
    (255, 255, 255): 11, # Permanent snow and ice
    (191, 191, 189): 10, # Barren / desert
    (134, 202, 227): 0,  # Water
}
MODIS_PALETTE_KEYS = np.array(list(MODIS_RGB_TO_COVER.keys()), dtype=np.int32)
MODIS_PALETTE_VALS = np.array(list(MODIS_RGB_TO_COVER.values()), dtype=np.int32)

COVER_TO_PCT_KEY = {
    1: "forest",
    2: "forest",
    3: "forest",
    4: "shrub",
    5: "grass",
    6: "pasture",
    7: "crop",
    8: "wetland",
    9: "developed",
}

INDUSTRY_LABELS = {
    "agriculture": "Agriculture, cotton, grain & livestock",
    "mining": "Mining, oil, natural gas & uranium",
    "construction": "Construction & infrastructure",
    "manufacturing": "Manufacturing, textiles & metallurgy",
    "wholesale": "Wholesale & Silk Road trade",
    "retail": "Retail trade & bazaars",
    "transportation": "Transportation, rail & logistics",
    "utilities": "Power, hydro & utilities",
    "information": "IT, telecom & digital services",
    "finance": "Banking & financial services",
    "real_estate": "Real estate & property",
    "professional": "Professional, scientific & technical",
    "management": "Corporate & enterprise management",
    "admin": "Administrative & support services",
    "education": "Education & universities",
    "health": "Healthcare & social services",
    "arts": "Arts, heritage & recreation",
    "accommodation": "Tourism, hospitality & dining",
    "other": "Other services",
    "public_admin": "Public administration & governance",
}

# Baseline 20-industry employment distribution by republic (calibrated to World Bank sector splits)
BASE_EMP_SHARES = {
    "UZ": dict(agriculture=0.250, mining=0.018, construction=0.092, manufacturing=0.130, wholesale=0.042, retail=0.095,
               transportation=0.048, utilities=0.014, information=0.018, finance=0.012, real_estate=0.008, professional=0.022,
               management=0.004, admin=0.018, education=0.088, health=0.052, arts=0.015, accommodation=0.022, other=0.022, public_admin=0.030),
    "KZ": dict(agriculture=0.125, mining=0.036, construction=0.074, manufacturing=0.072, wholesale=0.058, retail=0.122,
               transportation=0.072, utilities=0.019, information=0.028, finance=0.025, real_estate=0.016, professional=0.038,
               management=0.006, admin=0.028, education=0.105, health=0.062, arts=0.018, accommodation=0.024, other=0.026, public_admin=0.046),
    "KG": dict(agriculture=0.195, mining=0.016, construction=0.095, manufacturing=0.098, wholesale=0.052, retail=0.132,
               transportation=0.064, utilities=0.016, information=0.018, finance=0.015, real_estate=0.008, professional=0.020,
               management=0.003, admin=0.016, education=0.092, health=0.050, arts=0.016, accommodation=0.034, other=0.024, public_admin=0.036),
    "TJ": dict(agriculture=0.415, mining=0.014, construction=0.082, manufacturing=0.062, wholesale=0.032, retail=0.086,
               transportation=0.040, utilities=0.016, information=0.010, finance=0.010, real_estate=0.005, professional=0.014,
               management=0.002, admin=0.012, education=0.082, health=0.044, arts=0.012, accommodation=0.018, other=0.018, public_admin=0.026),
    "TM": dict(agriculture=0.215, mining=0.052, construction=0.112, manufacturing=0.110, wholesale=0.036, retail=0.088,
               transportation=0.058, utilities=0.022, information=0.010, finance=0.012, real_estate=0.008, professional=0.018,
               management=0.003, admin=0.016, education=0.082, health=0.048, arts=0.014, accommodation=0.020, other=0.022, public_admin=0.054),
}

# Relative GDP value-added multiplier per worker by industry (mining/finance/IT produce more GDP per worker than farming)
GDP_PRODUCTIVITY_MULT = {
    "agriculture": 0.42, "mining": 4.80, "construction": 1.05, "manufacturing": 1.38, "wholesale": 1.22,
    "retail": 0.78, "transportation": 1.28, "utilities": 1.85, "information": 2.20, "finance": 2.80,
    "real_estate": 3.10, "professional": 1.65, "management": 1.80, "admin": 0.85, "education": 0.58,
    "health": 0.62, "arts": 0.68, "accommodation": 0.72, "other": 0.65, "public_admin": 0.92,
}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def load_wb() -> dict[str, dict[str, tuple[int, float]]]:
    raw = json.loads((RAW_DIR / "wb_summary.json").read_text(encoding="utf-8"))
    out: dict[str, dict[str, tuple[int, float]]] = {}
    for key, rows in raw.items():
        latest: dict[str, tuple[int, float]] = {}
        for row in rows:
            val = row.get("value")
            if val is None:
                continue
            iso3 = row.get("countryiso3code")
            if iso3 not in ISO3_TO_ISO2:
                continue
            iso2 = ISO3_TO_ISO2[iso3]
            yr = int(row["date"])
            if iso2 not in latest or yr > latest[iso2][0]:
                latest[iso2] = (yr, float(val))
        out[key] = latest
    return out


def load_etopo():
    lats_set, lons_set = set(), set()
    pts = []
    with open(RAW_DIR / "etopo_ca.csv", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)  # header
        next(r)  # units
        for row in r:
            if len(row) < 3:
                continue
            lat, lon, alt = float(row[0]), float(row[1]), float(row[2])
            lats_set.add(lat)
            lons_set.add(lon)
            pts.append((lat, lon, alt))
    lats = np.array(sorted(lats_set))
    lons = np.array(sorted(lons_set))
    lat_i = {v: i for i, v in enumerate(lats)}
    lon_i = {v: i for i, v in enumerate(lons)}
    grid = np.full((len(lats), len(lons)), np.nan, dtype=np.float32)
    for lat, lon, alt in pts:
        grid[lat_i[lat], lon_i[lon]] = alt
    return lats, lons, grid


def sample_etopo(lats, lons, grid, lon: float, lat: float) -> float:
    i = int(np.clip(np.searchsorted(lats, lat), 0, len(lats) - 1))
    j = int(np.clip(np.searchsorted(lons, lon), 0, len(lons) - 1))
    val = grid[i, j]
    return float(val) if not np.isnan(val) else 0.0


def load_modis_cover():
    img = np.array(Image.open(RAW_DIR / "modis_landcover.png").convert("RGB"))
    # Map every pixel to nearest MODIS cover id
    h, w, _ = img.shape
    flat = img.reshape(-1, 3).astype(np.int32)
    # Fast exact match + fallback nearest color
    cov = np.zeros(len(flat), dtype=np.uint8)
    matched = np.zeros(len(flat), dtype=bool)
    for rgb, cid in MODIS_RGB_TO_COVER.items():
        m = (flat[:, 0] == rgb[0]) & (flat[:, 1] == rgb[1]) & (flat[:, 2] == rgb[2])
        cov[m] = cid
        matched |= m
    if not matched.all():
        rem = flat[~matched]
        dists = ((rem[:, None, :] - MODIS_PALETTE_KEYS[None, :, :]) ** 2).sum(axis=2)
        cov[~matched] = MODIS_PALETTE_VALS[dists.argmin(axis=1)]
    return cov.reshape(h, w)


def sample_modis(cov_arr: np.ndarray, lon: float, lat: float) -> int:
    # BBOX: 45..90E, 33..57N
    h, w = cov_arr.shape
    if lon < 45.0 or lon > 90.0 or lat < 33.0 or lat > 57.0:
        return 0
    x = int(np.clip((lon - 45.0) / (90.0 - 45.0) * w, 0, w - 1))
    y = int(np.clip((57.0 - lat) / (57.0 - 33.0) * h, 0, h - 1))
    return int(cov_arr[y, x])


def largest_remainder(shares: dict[str, float], total_icons: int) -> dict[str, int]:
    raw = {k: v * total_icons for k, v in shares.items()}
    floors = {k: int(math.floor(v)) for k, v in raw.items()}
    rem = total_icons - sum(floors.values())
    order = sorted(raw.keys(), key=lambda k: -(raw[k] - floors[k]))
    for k in order[:rem]:
        floors[k] += 1
    return floors


def build() -> None:
    print("=== Building Central Asia Civ (ca5) ===")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wb = load_wb()
    manifest = read_manifest("central_asia")

    # ------------------------------------------------------------------ 1. Load vector geometry & project
    print("1/10 Loading Natural Earth boundaries, lakes, rivers...")
    countries_raw = json.loads((RAW_DIR / "ne_admin_0_countries.geojson").read_text(encoding="utf-8"))
    admin1_raw = json.loads((RAW_DIR / "ne_admin_1_states_provinces.geojson").read_text(encoding="utf-8"))
    lakes_raw = json.loads((RAW_DIR / "ne_lakes.geojson").read_text(encoding="utf-8"))
    rivers_raw = json.loads((RAW_DIR / "ne_rivers_lake_centerlines.geojson").read_text(encoding="utf-8"))

    # Project Central Asia republics to find tight bounding box
    rep_geoms_aea: dict[str, object] = {}
    foreign_geoms_aea = []

    def proj_geom(g):
        return shp_transform(TO_AEA.transform, g)

    for feat in countries_raw["features"]:
        props = feat["properties"]
        iso2 = props.get("ISO_A2") or props.get("ISO_A2_EH")
        if iso2 in CA_ISOS:
            g = proj_geom(shape(feat["geometry"]))
            rep_geoms_aea[iso2] = g
        else:
            # Keep nearby neighbours (within rough lon 35..100, lat 25..65)
            geom = shape(feat["geometry"])
            minx, miny, maxx, maxy = geom.bounds
            if maxx >= 38 and minx <= 98 and maxy >= 28 and miny <= 64:
                foreign_geoms_aea.append(proj_geom(geom))

    # Bounding box of all 5 republics in AEA meters
    min_xm = min(g.bounds[0] for g in rep_geoms_aea.values())
    min_ym = min(g.bounds[1] for g in rep_geoms_aea.values())
    max_xm = max(g.bounds[2] for g in rep_geoms_aea.values())
    max_ym = max(g.bounds[3] for g in rep_geoms_aea.values())

    width_km = (max_xm - min_xm) / 1000.0 + 2 * MARGIN
    height_km = (max_ym - min_ym) / 1000.0 + 2 * MARGIN
    grid = HexGrid.covering(width_km, height_km, RADIUS)
    n_cells = grid.size
    print(f"   Map extent: {width_km:.1f} x {height_km:.1f} km | Grid: {grid.cols}x{grid.rows} = {n_cells} hexes (R={RADIUS} km)")

    def aea_to_map(xm: float, ym: float) -> tuple[float, float]:
        return (xm - min_xm) / 1000.0 + MARGIN, (max_ym - ym) / 1000.0 + MARGIN

    def lonlat_to_map(lon: float, lat: float) -> tuple[float, float]:
        xm, ym = TO_AEA.transform(lon, lat)
        return aea_to_map(xm, ym)

    def map_to_lonlat(x_km: float, y_km: float) -> tuple[float, float]:
        xm = (x_km - MARGIN) * 1000.0 + min_xm
        ym = max_ym - (y_km - MARGIN) * 1000.0
        return FROM_AEA.transform(xm, ym)

    def to_map_geom(g_aea):
        return shp_transform(lambda x, y, z=None: aea_to_map(x, y), g_aea)

    # Republic geometries in map km
    rep_polys = [to_map_geom(rep_geoms_aea[r["abbr"]]) for r in REPUBLICS]
    foreign_polys = [to_map_geom(g) for g in foreign_geoms_aea]
    foreign_tree = STRtree(foreign_polys)

    # Admin-1 provinces (counties) in map km
    # Note: Natural Earth has two "Tashkent" features (Tashkent City is much smaller than Tashkent Region)
    raw_ca_admin1 = [f for f in admin1_raw["features"] if f["properties"].get("iso_a2") in CA_ISOS]
    tashkent_feats = [f for f in raw_ca_admin1 if f["properties"].get("iso_a2") == "UZ" and f["properties"].get("name") == "Tashkent"]
    tashkent_city_id = None
    if len(tashkent_feats) == 2:
        areas = [(shape(f["geometry"]).area, f["properties"].get("adm1_code")) for f in tashkent_feats]
        areas.sort()
        tashkent_city_id = areas[0][1]

    admin1_records = []
    admin1_polys = []
    for f in raw_ca_admin1:
        p = f["properties"]
        iso2 = p["iso_a2"]
        raw_name = p["name"]
        if iso2 == "UZ" and raw_name == "Tashkent" and p.get("adm1_code") == tashkent_city_id:
            clean_name = "Tashkent City"
        else:
            clean_name = NE_ADMIN1_RENAME.get((iso2, raw_name), raw_name)
        g_aea = proj_geom(shape(f["geometry"]))
        area_km2 = g_aea.area / 1e6
        g_map = to_map_geom(g_aea)
        geoid = f"{iso2}-{len(admin1_records) + 1:02d}"
        admin1_records.append({
            "geoid": geoid,
            "name": clean_name,
            "state": iso2,
            "state_idx": ISO2_TO_IDX[iso2],
            "area_km2": round(area_km2, 1),
            "centroid": (g_map.representative_point().x, g_map.representative_point().y),
        })
        admin1_polys.append(g_map)
    admin1_tree = STRtree(admin1_polys)
    admin1_by_key = {(r["state"], r["name"]): i for i, r in enumerate(admin1_records)}

    # Lakes (exclude Caspian Sea from lakes list since Caspian is open sea water=1/2!)
    lake_polys = []
    caspian_polys = []
    for feat in lakes_raw["features"]:
        name = feat["properties"].get("name") or ""
        g = shape(feat["geometry"])
        minx, miny, maxx, maxy = g.bounds
        if maxx < 44 or minx > 92 or maxy < 32 or miny > 58:
            continue
        gm = to_map_geom(proj_geom(g))
        if "Caspian" in name:
            caspian_polys.append(gm)
        else:
            # Keep significant lakes (>= 300 km2 or major named lakes)
            if gm.area >= 220 or name in {"Issyk-Kul", "Lake Balkhash", "South Aral Sea", "North Aral Sea", "Lake Zaysan", "Lake Alakol", "Aydar Lake", "Sarygamysh Lake", "Karakul", "Kapchagay Reservoir", "Toktogul Reservoir"}:
                lake_polys.append(gm)
    lake_tree = STRtree(lake_polys)
    caspian_tree = STRtree(caspian_polys) if caspian_polys else None

    # ------------------------------------------------------------------ 2. Sample hex grid (terrain, relief, cover)
    print("2/10 Sampling elevation (ETOPO1), MODIS satellite land cover, borders & lakes onto hex grid...")
    etopo_lats, etopo_lons, etopo_grid = load_etopo()
    modis_arr = load_modis_cover()

    # 7 sample offsets per hex (centre + 6 ring points at 0.58 R)
    ring_offsets = [(0.0, 0.0)] + [
        (0.58 * RADIUS * math.cos(math.radians(a)), 0.58 * RADIUS * math.sin(math.radians(a)))
        for a in range(30, 360, 60)
    ]

    owner = [-1] * n_cells
    county = [-1] * n_cells
    elev = [0] * n_cells
    elev_max = [0] * n_cells
    water = [OCEAN] * n_cells
    relief = [0] * n_cells
    cover = [0] * n_cells
    pct = {k: [0] * n_cells for k in ("forest", "crop", "pasture", "grass", "shrub", "wetland", "developed")}

    rep_tree = STRtree(rep_polys)

    for idx in range(n_cells):
        col, row = grid.col_row(idx)
        cx, cy = grid.center(col, row)

        owner_votes = Counter()
        county_votes = Counter()
        land_elevs = []
        water_elevs = []
        lake_hits = 0
        caspian_hits = 0
        cover_votes = Counter()
        pct_hits = Counter()
        land_samples = 0

        for ox, oy in ring_offsets:
            sx, sy = cx + ox, cy + oy
            pt = Point(sx, sy)
            lon, lat = map_to_lonlat(sx, sy)
            z = sample_etopo(etopo_lats, etopo_lons, etopo_grid, lon, lat)

            # Check Caspian Sea first
            in_caspian = False
            if caspian_tree is not None:
                for ci in caspian_tree.query(pt):
                    if caspian_polys[ci].contains(pt):
                        in_caspian = True
                        break
            if in_caspian:
                caspian_hits += 1
                water_elevs.append(min(z, -28.0))
                continue

            # Check inland lake
            in_lake = False
            for li in lake_tree.query(pt):
                if lake_polys[li].contains(pt):
                    in_lake = True
                    break
            if in_lake:
                lake_hits += 1
                water_elevs.append(min(z, 0.0))
                continue

            # Check Central Asia republics
            rep_hit = -1
            for ri in rep_tree.query(pt):
                if rep_polys[ri].contains(pt):
                    rep_hit = int(ri)
                    break

            if rep_hit >= 0:
                owner_votes[rep_hit] += 1
                land_samples += 1
                land_elevs.append(z)
                # Admin-1 county lookup
                for ai in admin1_tree.query(pt):
                    if admin1_polys[ai].contains(pt) and admin1_records[ai]["state_idx"] == rep_hit:
                        county_votes[int(ai)] += 1
                        break
                cid = sample_modis(modis_arr, lon, lat)
                if cid > 0:
                    cover_votes[cid] += 1
                    pk = COVER_TO_PCT_KEY.get(cid)
                    if pk:
                        pct_hits[pk] += 1
            else:
                # Check foreign land
                in_foreign = False
                for fi in foreign_tree.query(pt):
                    if foreign_polys[fi].contains(pt):
                        in_foreign = True
                        break
                if in_foreign:
                    owner_votes[-2] += 1
                    land_samples += 1
                    land_elevs.append(z)
                    cid = sample_modis(modis_arr, lon, lat)
                    if cid > 0:
                        cover_votes[cid] += 1
                else:
                    water_elevs.append(min(z, -5.0))

        # Assign cell owner & water
        ca_votes = {k: v for k, v in owner_votes.items() if k >= 0}
        if ca_votes and sum(ca_votes.values()) >= 3:
            best_rep = max(ca_votes.items(), key=lambda kv: kv[1])[0]
            owner[idx] = best_rep
            water[idx] = LAND
            if county_votes:
                county[idx] = county_votes.most_common(1)[0][0]
        elif owner_votes.get(-2, 0) >= 3:
            owner[idx] = -2
            water[idx] = LAND
        elif lake_hits >= 3:
            owner[idx] = -1
            water[idx] = LAKE
        elif caspian_hits >= 2 or (land_samples < 3 and water_elevs):
            owner[idx] = -1
            water[idx] = OCEAN
        elif ca_votes:
            best_rep = max(ca_votes.items(), key=lambda kv: kv[1])[0]
            owner[idx] = best_rep
            water[idx] = LAND
            if county_votes:
                county[idx] = county_votes.most_common(1)[0][0]
        elif owner_votes.get(-2, 0) > 0:
            owner[idx] = -2
            water[idx] = LAND
        else:
            owner[idx] = -1
            water[idx] = OCEAN

        # Assign elevation & relief
        if water[idx] == LAND and land_elevs:
            mean_z = statistics.mean(land_elevs)
            max_z = max(land_elevs)
            elev[idx] = int(round(mean_z))
            elev_max[idx] = int(round(max_z))
            rel = classify_relief(land_elevs)
            if rel > 0 and is_valley_floor(land_elevs):
                rel = max(0, rel - 1)
            relief[idx] = rel
        else:
            elev[idx] = int(round(statistics.mean(water_elevs))) if water_elevs else -50
            elev_max[idx] = 0
            relief[idx] = 0

        # Assign land cover & pct
        if water[idx] == LAND and cover_votes:
            # High alpine snow boost above 4200m
            if elev_max[idx] >= 4400 and relief[idx] >= 2:
                cover[idx] = 11 if elev[idx] >= 4000 else cover_votes.most_common(1)[0][0]
            elif pct_hits["developed"] >= 2:
                cover[idx] = 9
            else:
                cover[idx] = cover_votes.most_common(1)[0][0]
            if owner[idx] >= 0 and land_samples > 0:
                for k in pct:
                    pct[k][idx] = int(round(100.0 * pct_hits[k] / land_samples))

    # Mark coastal hexes (ocean cells adjacent to land or shallower than COAST_DEPTH_M)
    for idx in range(n_cells):
        if water[idx] == OCEAN:
            if elev[idx] > -COAST_DEPTH_M or any(water[nb] == LAND for nb in grid.neighbours(idx)):
                water[idx] = COAST

    # Ensure every CA land cell has a valid county index
    for idx in range(n_cells):
        if owner[idx] >= 0 and county[idx] < 0:
            col, row = grid.col_row(idx)
            cx, cy = grid.center(col, row)
            same_state = [i for i, a in enumerate(admin1_records) if a["state_idx"] == owner[idx]]
            if same_state:
                county[idx] = min(same_state, key=lambda i: math.dist((cx, cy), admin1_records[i]["centroid"]))

    # Clip major rivers
    rivers = []
    seen_rivers = set()
    for feat in rivers_raw["features"]:
        props = feat["properties"]
        srank = props.get("scalerank")
        if srank is not None and int(srank) > 7:
            continue
        if props.get("featurecla") == "Lake Centerline":
            continue
        g = shape(feat["geometry"])
        minx, miny, maxx, maxy = g.bounds
        if maxx < 45 or minx > 90 or maxy < 33 or miny > 57:
            continue
        gm = to_map_geom(proj_geom(g))
        lines = [gm] if isinstance(gm, LineString) else list(gm.geoms) if isinstance(gm, MultiLineString) else []
        rname = props.get("name") or ""
        rank = 1 if (srank is not None and int(srank) <= 3) else 2 if (srank is not None and int(srank) <= 5) else 3
        for line in lines:
            clipped = clip_polyline(list(line.coords), width_km, height_km)
            for seg in clipped:
                if len(seg) >= 2:
                    flat = [round(v, 1) for p in seg for v in p]
                    rivers.append({"name": rname, "rank": rank, "pts": flat})
                    if rname:
                        seen_rivers.add(rname)

    ca_land_cells = sum(1 for o in owner if o >= 0)
    print(f"   CA land hexes: {ca_land_cells} | Foreign hexes: {sum(1 for o in owner if o == -2)} | Rivers: {len(rivers)} segments")

    world_doc = {
        "version": 2,
        "grid": {"radius": RADIUS, "cols": grid.cols, "rows": grid.rows},
        "width": round(width_km, 1),
        "height": round(height_km, 1),
        "margin": MARGIN,
        "owner": owner,
        "county": county,
        "elev": elev,
        "elev_max": elev_max,
        "water": water,
        "relief": relief,
        "cover": cover,
        "pct": pct,
        "tables": {
            "water": WATER_TABLE,
            "relief": RELIEF_TABLE,
            "cover": COVER,
        },
        "states": [{"fips": r["fips"], "abbr": r["abbr"], "name": r["name"]} for r in REPUBLICS],
        "counties": [{"geoid": a["geoid"], "name": a["name"]} for a in admin1_records],
        "rivers": rivers,
    }
    write_json(OUT_DIR / "world.json", world_doc)

    # Helper: snap (lon, lat) to a CA land hex (preferring state_idx if given)
    def place_point(lon: float, lat: float, state_abbr: str | None = None, max_rings: int = 8):
        x, y = lonlat_to_map(lon, lat)
        cell = grid.cell_at(x, y)
        if cell < 0:
            return None
        want = ISO2_TO_IDX.get(state_abbr) if state_abbr else None
        if owner[cell] < 0 or (want is not None and owner[cell] != want):
            # Search outward rings
            found = None
            for ring in range(1, max_rings + 1):
                cands = []
                for idx2 in hex_ring(grid, cell, ring):
                    if owner[idx2] >= 0 and (want is None or owner[idx2] == want):
                        cx2, cy2 = grid.center(*grid.col_row(idx2))
                        cands.append((math.dist((x, y), (cx2, cy2)), idx2))
                if cands:
                    found = min(cands)[1]
                    break
            if found is None:
                found = nearest_land(grid, owner, cell, max_rings=max_rings)
            if found is not None:
                cell = found
        if owner[cell] < 0:
            return None
        st_abbr = REPUBLICS[owner[cell]]["abbr"]
        cty_idx = county[cell]
        cty_geoid = admin1_records[cty_idx]["geoid"] if cty_idx >= 0 else None
        return {"x": round(x, 1), "y": round(y, 1), "cell": cell, "state": st_abbr, "county": cty_geoid}

    # ------------------------------------------------------------------ 3. Build states, nation & cities
    print("3/10 Building states.json, nation.json, and cities.json (calibrated to World Bank 2025)...")
    rep_stats = {}
    for idx_r, r in enumerate(REPUBLICS):
        abbr = r["abbr"]
        pop = int(round(wb["pop"][abbr][1]))
        gdp = float(wb["gdp"][abbr][1])
        unemp = round(wb["unemp"][abbr][1] / 100.0, 4) if abbr in wb["unemp"] else 0.05
        internet = round(wb["internet"][abbr][1] / 100.0, 4) if abbr in wb["internet"] else 0.36
        urban = round(wb["urban"][abbr][1] / 100.0, 4) if abbr in wb["urban"] else 0.48
        # Compute 2021-2025 population growth from World Bank series
        wb_pop_series = {int(row["date"]): float(row["value"]) for row in json.loads((RAW_DIR / "wb_pop.json").read_text())[1] if row["value"] is not None and ISO3_TO_ISO2.get(row["countryiso3code"]) == abbr}
        pop_2021 = wb_pop_series.get(2021, pop * 0.93)
        growth = round(pop / pop_2021 - 1.0, 4)
        # Employment & industry breakdown
        labor_rate = {"UZ": 0.43, "KZ": 0.48, "KG": 0.41, "TJ": 0.36, "TM": 0.44}[abbr]
        employed = int(round(pop * labor_rate * (1.0 - unemp)))
        shares = BASE_EMP_SHARES[abbr]
        s_sum = sum(shares.values())
        jobs = {k: int(round(employed * v / s_sum)) for k, v in shares.items()}
        # GDP by industry
        raw_gdp_ind = {k: jobs[k] * GDP_PRODUCTIVITY_MULT[k] for k in jobs}
        rg_sum = sum(raw_gdp_ind.values())
        gdp_by_ind = {k: round(gdp * v / rg_sum) for k, v in raw_gdp_ind.items()}
        yields = {
            "food": jobs["agriculture"],
            "production": jobs["manufacturing"] + jobs["construction"] + jobs["mining"],
            "gold": round(gdp),
            "science": jobs["professional"] + jobs["information"],
            "culture": jobs["arts"],
        }
        # Median household income, rent, home value (annual USD / monthly USD / USD)
        med_inc = {"UZ": 8400, "KZ": 16800, "KG": 7200, "TJ": 5400, "TM": 10600}[abbr]
        med_rent = {"UZ": 240, "KZ": 430, "KG": 230, "TJ": 175, "TM": 260}[abbr]
        home_val = {"UZ": 44000, "KZ": 78000, "KG": 42000, "TJ": 31000, "TM": 52000}[abbr]
        land_km2 = wb["land_km2"][abbr][1] if abbr in wb["land_km2"] else sum(a["area_km2"] for a in admin1_records if a["state"] == abbr)

        # Land cover averages over this republic's hexes
        rcells = [i for i, o in enumerate(owner) if o == idx_r and cover[i] > 0]
        land_cov = {k: round(statistics.mean(pct[k][i] for i in rcells) / 100.0, 4) for k in pct} if rcells else None

        # Label anchor for big country name on map
        all_rcells = [i for i, o in enumerate(owner) if o == idx_r]
        xs = [grid.center(*grid.col_row(i))[0] for i in all_rcells]
        ys = [grid.center(*grid.col_row(i))[1] for i in all_rcells]
        lx, ly = statistics.mean(xs), statistics.mean(ys)
        span = max(xs) - min(xs) if xs else 200
        lsize = round(max(24.0, min(95.0, span * 0.045)), 1)
        # Fine-tune Kazakhstan/Uzbekistan/Turkmenistan visual label centers slightly so they never cover capitals
        label_offsets = {"KZ": (-40, -60), "UZ": (-40, 20), "TM": (0, 20), "KG": (20, 10), "TJ": (30, 10)}
        dx, dy = label_offsets[abbr]
        rep_stats[abbr] = {
            "fips": r["fips"], "abbr": abbr, "name": r["name"],
            "population": pop, "employed": employed, "land_km2": round(land_km2, 1),
            "density": round(pop / land_km2, 1),
            "growth": growth, "growth_years": [2021, 2025],
            "yields": yields, "jobs": jobs,
            "median_income": med_inc, "median_rent": med_rent, "home_value": home_val,
            "unemployment": unemp, "unemployment_year": 2025,
            "rent_burden": round(med_rent * 12.0 / med_inc, 4),
            "gdp": round(gdp), "gdp_year": 2025, "gdp_population": pop,
            "gdp_by_industry": gdp_by_ind,
            "internet": internet, "urban": urban,
            "land": land_cov, "energy": None,
            "label": {"x": round(lx + dx, 1), "y": round(ly + dy, 1), "angle": 0, "size": lsize},
            "ranks": {},
        }

    # Compute ranks across the 5 republics
    for yk in ("food", "production", "gold", "science", "culture"):
        order = sorted(REPUBLICS, key=lambda r: -rep_stats[r["abbr"]]["yields"][yk])
        for rk, r in enumerate(order, 1):
            rep_stats[r["abbr"]]["ranks"][yk] = rk

    # Build Cities
    used_banner_cells: set[int] = set()
    cities_out = []
    city_by_id = {}
    city_spec_by_id = {}
    for row in sorted(CITIES, key=lambda t: -t[6]):
        cid, cname, abbr, rname, lon, lat, pop, growth, is_cap, is_metro, spec, gdp_m, inc_m = row
        at = place_point(lon, lat, abbr)
        if not at:
            continue
        cell = free_cell(grid, owner, at["cell"], used_banner_cells, max_rings=2)
        if cell is None:
            cell = at["cell"]
        used_banner_cells.add(cell)

        # Footprint: own cell + up to 4 neighboring land cells in same country for major metros
        fp = {cell}
        if pop >= 500000:
            for nb in grid.neighbours(cell):
                if owner[nb] == ISO2_TO_IDX[abbr]:
                    fp.add(nb)
        elif pop >= 200000:
            nbs = [nb for nb in grid.neighbours(cell) if owner[nb] == ISO2_TO_IDX[abbr]]
            for nb in nbs[:2]:
                fp.add(nb)

        # Match admin-1 county stats
        ast = ADMIN1_STATS.get((abbr, rname))
        a1_idx = admin1_by_key.get((abbr, rname))
        a1_geoid = admin1_records[a1_idx]["geoid"] if a1_idx is not None else at["county"]
        base_gdp_pc = ast[2] if ast else (rep_stats[abbr]["gdp"] / rep_stats[abbr]["population"])
        base_inc = ast[3] if ast else rep_stats[abbr]["median_income"]
        base_bach = ast[6] if ast else 0.22

        city_gdp = round(pop * base_gdp_pc * gdp_m)
        city_inc = round(base_inc * inc_m)
        city_rent = round(rep_stats[abbr]["median_rent"] * (0.75 + 0.45 * inc_m) * (1.35 if pop >= 1000000 else 1.0))
        city_home = round(rep_stats[abbr]["home_value"] * (0.75 + 0.45 * inc_m) * (1.40 if pop >= 1000000 else 1.0))
        city_unemp = round(max(0.018, rep_stats[abbr]["unemployment"] * (0.82 if pop >= 500000 else 1.02)), 4)
        emp_rate = rep_stats[abbr]["employed"] / rep_stats[abbr]["population"]
        city_emp = int(round(pop * emp_rate * (1.06 if pop >= 500000 else 0.98)))

        # Industry mix shaped by specialty profile
        base_w = dict(BASE_EMP_SHARES[abbr])
        for k, mult in SPECIALTY_INDUSTRY_WEIGHTS.get(spec, {}).items():
            base_w[k] = base_w.get(k, 0.01) * mult
        w_sum = sum(base_w.values())
        jobs = {k: int(round(city_emp * v / w_sum)) for k, v in base_w.items()}

        raw_g = {k: jobs[k] * GDP_PRODUCTIVITY_MULT[k] for k in jobs}
        rg_s = sum(raw_g.values())
        gdp_by_ind = {k: round(city_gdp * v / rg_s) for k, v in raw_g.items()}

        yields = {
            "food": jobs["agriculture"],
            "production": jobs["manufacturing"] + jobs["construction"] + jobs["mining"],
            "gold": city_gdp,
            "science": jobs["professional"] + jobs["information"],
            "culture": jobs["arts"],
        }

        # Synthetic smooth 2020-2025 population series matching growth_21_25
        annual = (1.0 + growth) ** 0.25
        pop_series = {
            str(y): int(round(pop / (annual ** (2025 - y)))) for y in range(2020, 2026)
        }
        pop_series["2025"] = pop

        area_km2 = round(max(25.0, pop / (3200.0 if pop >= 1000000 else 2100.0)), 1)
        full_name = f"{cname}, {REPUBLICS[ISO2_TO_IDX[abbr]]['name']}" + (" (Capital)" if is_cap else "")
        cobj = {
            "id": cid,
            "name": cname,
            "full": full_name,
            "states": [abbr],
            "metro": is_metro,
            "capital": is_cap,
            "x": at["x"],
            "y": at["y"],
            "cell": cell,
            "footprint": sorted(fp),
            "counties": [a1_geoid] if a1_geoid else [],
            "population": pop,
            "employed": city_emp,
            "land_km2": area_km2,
            "density": round(pop / area_km2, 1),
            "growth": growth,
            "growth_years": [2021, 2025],
            "pop_series": pop_series,
            "yields": yields,
            "jobs": jobs,
            "median_income": city_inc,
            "median_rent": city_rent,
            "home_value": city_home,
            "unemployment": city_unemp,
            "unemployment_year": 2025,
            "rent_burden": round(city_rent * 12.0 / city_inc, 4),
            "gdp": city_gdp,
            "gdp_year": 2025,
            "gdp_population": pop,
            "gdp_by_industry": gdp_by_ind,
            "bachelors": round(min(0.58, base_bach * (1.15 if pop >= 500000 else 1.05)), 4),
            "ranks": {},
            "peers": [],
        }
        cities_out.append(cobj)
        city_by_id[cid] = cobj
        city_spec_by_id[cid] = spec

    # City ranks & 5 nearest-population peers
    def assign_ranks(key, fn):
        order = sorted(cities_out, key=lambda c: (-fn(c), -c["population"]))
        for rk, c in enumerate(order, 1):
            c["ranks"][key] = rk

    assign_ranks("population", lambda c: c["population"])
    assign_ranks("gdp", lambda c: c["gdp"])
    assign_ranks("gdp_per_capita", lambda c: c["gdp"] / c["population"])
    assign_ranks("growth", lambda c: c["growth"])
    for yk in ("food", "production", "gold", "science", "culture"):
        assign_ranks(yk, lambda c, k=yk: c["yields"][k])

    for c in cities_out:
        peers = sorted(
            (o for o in cities_out if o["id"] != c["id"]),
            key=lambda o: abs(math.log(c["population"] / o["population"])),
        )[:5]
        c["peers"] = [p["id"] for p in peers]

    write_json(OUT_DIR / "cities.json", cities_out)

    # Regional (Central Asia total) nation.json
    tot_pop = sum(s["population"] for s in rep_stats.values())
    tot_emp = sum(s["employed"] for s in rep_stats.values())
    tot_gdp = sum(s["gdp"] for s in rep_stats.values())
    tot_land = round(sum(s["land_km2"] for s in rep_stats.values()), 1)
    tot_jobs = {k: sum(s["jobs"][k] for s in rep_stats.values()) for k in INDUSTRY_LABELS}
    tot_gdp_ind = {k: sum(s["gdp_by_industry"][k] for s in rep_stats.values()) for k in INDUSTRY_LABELS}
    w_growth = round(sum(s["growth"] * s["population"] for s in rep_stats.values()) / tot_pop, 4)
    w_unemp = round(sum(s["unemployment"] * s["population"] for s in rep_stats.values()) / tot_pop, 4)
    w_inc = round(sum(s["median_income"] * s["population"] for s in rep_stats.values()) / tot_pop)
    w_rent = round(sum(s["median_rent"] * s["population"] for s in rep_stats.values()) / tot_pop)
    w_home = round(sum(s["home_value"] * s["population"] for s in rep_stats.values()) / tot_pop)

    nation_doc = {
        "country": "Central Asia",
        "year": 2025,
        "census_year": 2025,
        "income_year": 2025,
        "census_vintage": "2025 National Statistics",
        "vintage": "World Bank WDI 2025 & National Statistics",
        "population_vintage": "World Bank WDI & National Statistical Agencies, 2025",
        "gdp_vintage": "World Bank WDI 2025 (current USD)",
        "unemployment_vintage": "ILO / World Bank 2025 modelled estimates",
        "nation": {
            "population": tot_pop,
            "employed": tot_emp,
            "land_km2": tot_land,
            "density": round(tot_pop / tot_land, 1),
            "growth": w_growth,
            "growth_years": [2021, 2025],
            "jobs": tot_jobs,
            "median_income": w_inc,
            "median_rent": w_rent,
            "home_value": w_home,
            "unemployment": w_unemp,
            "unemployment_year": 2025,
            "rent_burden": round(w_rent * 12.0 / w_inc, 4),
            "gdp": tot_gdp,
            "gdp_year": 2025,
            "gdp_population": tot_pop,
            "gdp_by_industry": tot_gdp_ind,
            "yields": {
                "food": tot_jobs["agriculture"],
                "production": tot_jobs["manufacturing"] + tot_jobs["construction"] + tot_jobs["mining"],
                "gold": tot_gdp,
                "science": tot_jobs["professional"] + tot_jobs["information"],
                "culture": tot_jobs["arts"],
            },
        },
        "yields": [
            {"key": "food", "icon": "y-food", "emoji": "🌾", "label": "Food", "color": "#7fbf3f", "unit": "workers",
             "industries": ["agriculture"], "description": "Workers in agriculture, irrigated cotton, wheat & pastoral livestock across Central Asia (2025)."},
            {"key": "production", "icon": "y-production", "emoji": "⚙️", "label": "Production", "color": "#d9823b", "unit": "workers",
             "industries": ["manufacturing", "construction", "mining"], "description": "Workers in manufacturing, metallurgy, construction, mining & oil/gas extraction (2025)."},
            {"key": "gold", "icon": "y-gold", "emoji": "💰", "label": "Gold", "color": "#f2c94c", "unit": "usd",
             "industries": [], "description": "Gross Domestic Product in current U.S. dollars (World Bank WDI 2025 & national statistical agencies)."},
            {"key": "science", "icon": "y-science", "emoji": "🔬", "label": "Science", "color": "#4fa3e0", "unit": "workers",
             "industries": ["professional", "information"], "description": "Workers in IT, software parks, telecom, engineering and scientific & technical professions (2025)."},
            {"key": "culture", "icon": "y-culture", "emoji": "🎭", "label": "Culture", "color": "#b07ce0", "unit": "workers",
             "industries": ["arts"], "description": "Workers in arts, Silk Road heritage, museums, media and cultural industries (2025)."},
        ],
        "industries": INDUSTRY_LABELS,
        "gdp_industries": INDUSTRY_LABELS,
    }
    write_json(OUT_DIR / "nation.json", nation_doc)

    # ------------------------------------------------------------------ 4. Resources (WRI Power Plants + Mines & Oil/Gas)
    print("4/10 Building resources.json (WRI Power Plants + Central Asian mines & hydrocarbon fields)...")
    res_types = [
        {"id": "hydro", "name": "Hydroelectric dam", "category": "energy", "emoji": "💧", "icon": "r-hydro", "color": "#3c9ee7", "unit": "MW", "source": "wri_plants", "description": "Hydroelectric generating stations ≥ 25 MW (WRI Global Power Plant Database + Rogun & Naryn cascade)."},
        {"id": "gas_plant", "name": "Natural gas plant", "category": "energy", "emoji": "🔥", "icon": "r-gas_plant", "color": "#e59838", "unit": "MW", "source": "wri_plants", "description": "Gas-fired & combined-cycle thermal power plants ≥ 25 MW."},
        {"id": "coal_plant", "name": "Coal power plant", "category": "energy", "emoji": "🏭", "icon": "r-coal_plant", "color": "#7b8089", "unit": "MW", "source": "wri_plants", "description": "Coal-fired power stations ≥ 25 MW (including Ekibastuz GRES-1 & GRES-2)."},
        {"id": "solar", "name": "Solar park", "category": "energy", "emoji": "☀️", "icon": "r-solar", "color": "#f4c542", "unit": "MW", "source": "wri_plants", "description": "Utility-scale solar PV parks ≥ 25 MW across Uzbekistan & Kazakhstan."},
        {"id": "wind", "name": "Wind farm", "category": "energy", "emoji": "🌬️", "icon": "r-wind", "color": "#72c9d8", "unit": "MW", "source": "wri_plants", "description": "Utility-scale desert & steppe wind farms ≥ 25 MW."},
        {"id": "oil_plant", "name": "Oil thermal plant", "category": "energy", "emoji": "🛢️", "icon": "r-oil", "color": "#8c6d53", "unit": "MW", "source": "wri_plants", "description": "Oil-fired thermal power stations ≥ 25 MW."},
        {"id": "uranium", "name": "Uranium mine", "category": "mineral", "emoji": "☢️", "icon": "r-uranium", "color": "#b4e84c", "unit": "tU / yr", "source": "usgs_minerals", "description": "Major in-situ recovery uranium districts (Kazakhstan & Uzbekistan supply >50% of global uranium)."},
        {"id": "gold", "name": "Gold mine", "category": "mineral", "emoji": "🥇", "icon": "r-gold", "color": "#f0c83c", "unit": "t Au / yr", "source": "usgs_minerals", "description": "Major gold mines including Muruntau (world's largest open-pit gold mine) and Kumtor."},
        {"id": "copper", "name": "Copper mine", "category": "mineral", "emoji": "🔶", "icon": "r-copper", "color": "#d97745", "unit": "kt Cu / yr", "source": "usgs_minerals", "description": "Large open-pit copper & porphyry complexes (Almalyk, Aktogay, Bozshakol, Zhezkazgan)."},
        {"id": "coal_mine", "name": "Coal basin", "category": "mineral", "emoji": "🪨", "icon": "r-coal_mine", "color": "#5f656e", "unit": "kt / yr", "source": "usgs_minerals", "description": "Major open-pit and coking coal mining basins (Ekibastuz Bogatyr, Karaganda, Angren)."},
        {"id": "iron", "name": "Iron ore mine", "category": "mineral", "emoji": "⛓️", "icon": "r-iron", "color": "#b85c4b", "unit": "kt / yr", "source": "usgs_minerals", "description": "Major magnetite iron ore complexes in northern Kazakhstan (Sokolov-Sarbay, Kachary)."},
        {"id": "molybdenum", "name": "Chromite & ferroalloy", "category": "mineral", "emoji": "🔩", "icon": "r-molybdenum", "color": "#9ca8b8", "unit": "kt / yr", "source": "usgs_minerals", "description": "World-class chromite & ferroalloy deposits (Donskoy / Khromtau)."},
        {"id": "lead_zinc", "name": "Polymetallic mine", "category": "mineral", "emoji": "🪨", "icon": "r-lead_zinc", "color": "#89a3b8", "unit": "kt / yr", "source": "usgs_minerals", "description": "Zinc, lead, antimony & polymetallic mining centers (Altai Ridder & Anzob)."},
        {"id": "rare_earths", "name": "Industrial minerals", "category": "mineral", "emoji": "💎", "icon": "r-rare_earths", "color": "#c98be0", "unit": "kt / yr", "source": "usgs_minerals", "description": "Strategic evaporite and industrial mineral basins (Karabogazgol)."},
        {"id": "oil", "name": "Oil field", "category": "energy", "emoji": "🛢️", "icon": "r-oil", "color": "#554433", "unit": "km² basin", "source": "usgs_minerals", "description": "Supergiant & major crude oil fields (Tengiz, Kashagan, Uzen, Cheleken)."},
        {"id": "gas", "name": "Natural gas field", "category": "energy", "emoji": "🔥", "icon": "r-gas", "color": "#d48a46", "unit": "km² basin", "source": "usgs_minerals", "description": "Supergiant natural gas basins (Galkynysh, Karachaganak, Shurtan, Gazli, Surgil)."},
    ]
    fuel_map = {"Hydro": "hydro", "Gas": "gas_plant", "Coal": "coal_plant", "Solar": "solar", "Wind": "wind", "Oil": "oil_plant"}

    # Map each cell to nearest city id if within its footprint
    cell_to_city = {}
    for c in cities_out:
        for fc in c["footprint"]:
            if fc not in cell_to_city:
                cell_to_city[fc] = c["id"]

    res_items = []
    # Load WRI plants in Central Asia (>= 25 MW)
    with open(RAW_DIR / "wri_power_plants.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            iso3 = row["country"]
            if iso3 not in ISO3_TO_ISO2:
                continue
            cap = float(row["capacity_mw"] or 0)
            if cap < 25:
                continue
            rtype = fuel_map.get(row["primary_fuel"])
            if not rtype:
                continue
            abbr = ISO3_TO_ISO2[iso3]
            at = place_point(float(row["longitude"]), float(row["latitude"]), abbr)
            if not at:
                continue
            owner_txt = row.get("owner") or "National grid"
            res_items.append({
                "type": rtype,
                "name": row["name"],
                "x": at["x"], "y": at["y"], "cell": at["cell"],
                "value": round(cap),
                "detail": f"{round(cap):,} MW {row['primary_fuel'].lower()} plant ({owner_txt})",
                "state": abbr,
                "cbsa": cell_to_city.get(at["cell"]),
            })

    # Add curated new power plants + flagship mines + oil & gas fields
    for rtype, name, abbr, lon, lat, val, detail in EXTRA_RESOURCES:
        at = place_point(lon, lat, abbr)
        if not at:
            continue
        res_items.append({
            "type": rtype, "name": name,
            "x": at["x"], "y": at["y"], "cell": at["cell"],
            "value": val, "detail": detail,
            "state": abbr, "cbsa": cell_to_city.get(at["cell"]),
        })

    # Resource summaries & state energy totals
    mw_type_ids = [t["id"] for t in res_types if t["unit"] == "MW"]
    non_additive = {"oil", "gas"}
    nat_sum = {}
    for t in res_types:
        tid = t["id"]
        matching = [it for it in res_items if it["type"] == tid]
        nat_sum[tid] = {
            "count": len(matching),
            "value": None if tid in non_additive else round(sum(it["value"] for it in matching if it["value"] is not None)),
            "unit": t["unit"],
        }
    st_sum = {}
    for r in REPUBLICS:
        abbr = r["abbr"]
        sdict = {}
        for t in res_types:
            tid = t["id"]
            matching = [it for it in res_items if it["state"] == abbr and it["type"] == tid]
            if matching:
                sdict[tid] = {
                    "count": len(matching),
                    "value": None if tid in non_additive else round(sum(it["value"] for it in matching if it["value"] is not None)),
                    "unit": t["unit"],
                }
        st_sum[abbr] = sdict
        # Update state energy summary
        by_t = {tid: round(sum(it["value"] for it in res_items if it["state"] == abbr and it["type"] == tid)) for tid in mw_type_ids}
        sites_t = {tid: sum(1 for it in res_items if it["state"] == abbr and it["type"] == tid) for tid in mw_type_ids}
        rep_stats[abbr]["energy"] = {
            "unit": "MW",
            "total": sum(by_t.values()),
            "by_type": by_t,
            "sites": sites_t,
            "note": "Mapped power plants ≥ 25 MW (WRI Global Power Plant Database + major commissioned projects).",
        }

    write_json(OUT_DIR / "resources.json", {
        "types": res_types,
        "items": res_items,
        "summary": {
            "note": "Mapped generating stations ≥ 25 MW plus flagship mineral mines and oil/gas basins across all five Central Asian republics.",
            "national": nat_sum,
            "states": st_sum,
        },
    })
    write_json(OUT_DIR / "states.json", [rep_stats[r["abbr"]] for r in REPUBLICS])

    # ------------------------------------------------------------------ 5. Counties (48 Admin-1 Regions) & Lenses (16 Lenses)
    print("5/10 Building counties.json (48 oblasts/viloyats/welayats) and lenses.json (16 lenses)...")
    # Scale each republic's admin-1 populations so they sum cleanly to World Bank 2025 total
    raw_pop_by_state = defaultdict(float)
    for a in admin1_records:
        st_row = ADMIN1_STATS[(a["state"], a["name"])]
        raw_pop_by_state[a["state"]] += st_row[0] * 1000.0

    # Compute per-admin1 land cover means & representative hex cell
    a1_cells = defaultdict(list)
    for idx_c in range(n_cells):
        if owner[idx_c] >= 0 and county[idx_c] >= 0:
            a1_cells[county[idx_c]].append(idx_c)

    # Map each admin-1 to its largest city id
    a1_city = {}
    for c in cities_out:
        if c["counties"]:
            g = c["counties"][0]
            if g not in a1_city:
                a1_city[g] = c["id"]

    county_fields = [
        {"key": "geoid", "label": "Region ID", "format": "text", "unit": "", "higher_is": "neutral", "source": "natural_earth", "description": "Administrative region identifier."},
        {"key": "name", "label": "Region", "format": "text", "unit": "", "higher_is": "neutral", "source": "natural_earth", "description": "Viloyat, oblys, oblast, welayat, or republican capital city."},
        {"key": "state", "label": "Country", "format": "text", "unit": "", "higher_is": "neutral", "source": "natural_earth", "description": "Republic ISO code (UZ, KZ, KG, TJ, TM)."},
        {"key": "population", "label": "Population", "format": "int", "unit": "people", "higher_is": "neutral", "source": "world_bank", "description": "2025 resident population calibrated to World Bank WDI & national statistical agencies."},
        {"key": "land_km2", "label": "Land area", "format": "km2", "unit": "km²", "higher_is": "neutral", "source": "natural_earth", "description": "Projected land area in square kilometres."},
        {"key": "density", "label": "Density", "format": "float", "unit": "people / km²", "higher_is": "neutral", "source": "world_bank", "description": "Residents per square kilometre."},
        {"key": "growth", "label": "Pop. growth (2021–25)", "format": "pct", "unit": "%", "higher_is": "neutral", "source": "world_bank", "description": "Population change from 2021 to 2025."},
        {"key": "income", "label": "Household income", "format": "usd", "unit": "USD / yr", "higher_is": "good", "source": "nat_stats", "description": "Estimated annual median household income (USD, PPP-adjusted regional scale)."},
        {"key": "grp_pc", "label": "GDP per capita", "format": "usd", "unit": "USD", "higher_is": "good", "source": "world_bank", "description": "Gross Regional Product per resident (2025 USD)."},
        {"key": "poverty", "label": "Poverty rate", "format": "pct", "unit": "%", "higher_is": "bad", "source": "world_bank", "description": "Share of residents below the national poverty line."},
        {"key": "median_age", "label": "Median age", "format": "years", "unit": "years", "higher_is": "neutral", "source": "nat_stats", "description": "Median age of residents (Central Asia is among Eurasia's youngest regions)."},
        {"key": "bachelors", "label": "Higher education", "format": "pct", "unit": "%", "higher_is": "good", "source": "nat_stats", "description": "Share of adults 25+ with university or higher technical degrees."},
        {"key": "broadband", "label": "Internet access", "format": "pct", "unit": "%", "higher_is": "good", "source": "world_bank", "description": "Share of individuals using the internet (ITU / World Bank 2024)."},
        {"key": "commute", "label": "Avg. commute", "format": "minutes", "unit": "min", "higher_is": "bad", "source": "nat_stats", "description": "Estimated average one-way commute time in minutes."},
        {"key": "homeownership", "label": "Homeownership", "format": "pct", "unit": "%", "higher_is": "good", "source": "nat_stats", "description": "Share of households owning their dwelling."},
        {"key": "forest", "label": "Forest cover", "format": "pct", "unit": "%", "higher_is": "neutral", "source": "modis_cover", "description": "Share of hex samples classified as forest or woodland (NASA MODIS IGBP)."},
        {"key": "crop", "label": "Cropland & oasis", "format": "pct", "unit": "%", "higher_is": "neutral", "source": "modis_cover", "description": "Share of hex samples classified as cropland or irrigated oasis (NASA MODIS IGBP)."},
        {"key": "developed", "label": "Built-up", "format": "pct", "unit": "%", "higher_is": "neutral", "source": "modis_cover", "description": "Share of hex samples classified as urban or built-up (NASA MODIS IGBP)."},
        {"key": "cbsa", "label": "Lead city", "format": "text", "unit": "", "higher_is": "neutral", "source": "nat_stats", "description": "Primary city ID in this region."},
        {"key": "cell", "label": "Hex cell", "format": "int", "unit": "", "higher_is": "neutral", "source": "natural_earth", "description": "Representative map hex cell."},
        {"key": "faith", "label": "Faith adherence", "format": "float", "unit": "per 100 residents", "higher_is": "neutral", "source": "pew_census", "description": "Estimated religiously affiliated residents per 100 people (Pew Research / national censuses)."},
        {"key": "faith_tradition", "label": "Largest tradition", "format": "text", "unit": "", "higher_is": "neutral", "source": "pew_census", "description": "Largest religious tradition in the region."},
        {"key": "disasters", "label": "Hazard events", "format": "int", "unit": "events", "higher_is": "bad", "source": "emdat", "description": "Major recorded earthquakes, floods, mudflows, droughts and freezes affecting the region (1980–2025)."},
    ]

    faith_cats = [
        {"id": "sunni", "name": "Sunni Islam", "color": "#2f9e6f", "description": "Hanafi Sunni Muslim plurality/majority across Uzbekistan, Kazakhstan, Kyrgyzstan, Tajikistan & Turkmenistan."},
        {"id": "shia_ismaili", "name": "Ismaili Shia Islam", "color": "#3d7bd9", "description": "Nizari Ismaili Shia majority in Gorno-Badakhshan (Pamir Mountains, Tajikistan)."},
        {"id": "orthodox", "name": "Orthodox Christian", "color": "#d6a43e", "description": "Russian Orthodox historical plurality in northern Kazakhstan border regions."},
    ]
    faith_idx = {c["id"]: i for i, c in enumerate(faith_cats)}

    county_rows = []
    county_val_maps: dict[str, list] = {k: [] for k in ("density", "growth", "income", "grp_pc", "poverty", "age", "bachelors", "broadband", "commute", "homeownership", "faith", "faith_tradition", "disasters")}

    for i_a, a in enumerate(admin1_records):
        abbr = a["state"]
        pop_k, gr, grp_pc, inc, pov, med_age, bach, bb, comm, homeown, faith_v, faith_t, haz = ADMIN1_STATS[(abbr, a["name"])]
        scale = rep_stats[abbr]["population"] / raw_pop_by_state[abbr]
        pop_exact = int(round(pop_k * 1000.0 * scale))
        area = max(120.0, a["area_km2"])
        dens = round(pop_exact / area, 1)
        cells_here = a1_cells.get(i_a, [])
        if cells_here:
            f_cov = round(statistics.mean(pct["forest"][c] for c in cells_here) / 100.0, 4)
            c_cov = round(statistics.mean(pct["crop"][c] for c in cells_here) / 100.0, 4)
            d_cov = round(statistics.mean(pct["developed"][c] for c in cells_here) / 100.0, 4)
            cx, cy = a["centroid"]
            rep_cell = min(cells_here, key=lambda c: math.dist((cx, cy), grid.center(*grid.col_row(c))))
        else:
            f_cov = c_cov = d_cov = 0.0
            cx, cy = a["centroid"]
            c0 = grid.cell_at(cx, cy)
            rep_cell = nearest_land(grid, owner, c0 if c0 >= 0 else 0, max_rings=6) or 0

        county_rows.append([
            a["geoid"], a["name"], abbr, pop_exact, area, dens, gr, inc, grp_pc, pov, med_age,
            bach, bb, comm, homeown, f_cov, c_cov, d_cov, a1_city.get(a["geoid"]), rep_cell,
            faith_v, faith_t, haz,
        ])
        county_val_maps["density"].append(dens)
        county_val_maps["growth"].append(gr)
        county_val_maps["income"].append(inc)
        county_val_maps["grp_pc"].append(grp_pc)
        county_val_maps["poverty"].append(pov)
        county_val_maps["age"].append(med_age)
        county_val_maps["bachelors"].append(bach)
        county_val_maps["broadband"].append(bb)
        county_val_maps["commute"].append(comm)
        county_val_maps["homeownership"].append(homeown)
        county_val_maps["faith"].append(faith_v)
        county_val_maps["faith_tradition"].append(faith_idx[faith_t])
        county_val_maps["disasters"].append(haz)

    write_json(OUT_DIR / "counties.json", {
        "vintage": "2025 World Bank WDI & National Statistical Agencies",
        "fields": county_fields,
        "columns": [f["key"] for f in county_fields],
        "rows": county_rows,
    })

    # Spread admin-1 values & hex land cover into lenses.json
    def hex_from_county(key: str):
        arr = county_val_maps[key]
        return [arr[county[i]] if (owner[i] >= 0 and county[i] >= 0) else None for i in range(n_cells)]

    def make_lens(lid, grp, name, ic, emoji, unit, fmt, scale_t, ramp, higher, src, vals, desc, note=None, domain=None, cats=None):
        if domain is None:
            domain = percentile_domain(vals, log=(scale_t == "log"))
        doc = {
            "id": lid, "group": grp, "name": name, "icon": ic, "emoji": emoji,
            "unit": unit, "format": fmt, "scale": scale_t, "domain": domain, "ramp": ramp,
            "higher_is": higher, "source": src, "description": desc, "values": vals,
        }
        if note:
            doc["note"] = note
        if cats:
            doc["categories"] = cats
        return doc

    lenses_list = [
        make_lens("density", "people", "Population", "l-people", "👥", "people / km²", "float", "log",
                  ["#142130", "#224a6e", "#3d859c", "#8ac98c", "#f3e37c", "#f28b3b"], "neutral", "world_bank",
                  hex_from_county("density"), f"Residents per km² by province/oblast/viloyat (2025). Highlights the dense Fergana Valley, Tashkent & Almaty oases vs the Kazakh Steppe. {DOMAIN_NOTE}"),
        make_lens("growth", "people", "Pop. growth", "l-growth", "📈", "% change", "pct", "linear",
                  ["#9b3b49", "#d6826c", "#e8e3cf", "#82c596", "#2b8a5b"], "neutral", "world_bank",
                  hex_from_county("growth"), f"Population change 2021–2025 by region. Astana, Almaty, Tashkent and southern Central Asia are among Eurasia's fastest-growing regions. {DOMAIN_NOTE}", domain=[-0.04, 0.22]),
        make_lens("age", "people", "Median age", "l-age", "⏳", "years", "years", "linear",
                  ["#2a8c82", "#68b89e", "#c9dc9b", "#e8b468", "#c9624c"], "neutral", "nat_stats",
                  hex_from_county("age"), f"Median age of residents by region. Tajikistan and southern Uzbekistan average 22–27 years vs 36–39 in northern Kazakhstan. {DOMAIN_NOTE}"),
        make_lens("income", "prosperity", "Income", "l-income", "💵", "USD / yr", "usd", "linear",
                  ["#2b1e3e", "#4d3c77", "#3f7ca6", "#58b09c", "#b8df86", "#f8f0a4"], "good", "nat_stats",
                  hex_from_county("income"), f"Estimated median annual household income by region (USD). Oil-rich Atyrau, Astana, Almaty, Tashkent and Navoiy lead. {DOMAIN_NOTE}"),
        make_lens("grp_pc", "prosperity", "GDP / person", "y-gold", "💰", "USD / person", "usd", "log",
                  ["#2a1829", "#5c2e56", "#9a4c5e", "#d4844a", "#f2c94c", "#fff3b0"], "good", "world_bank",
                  hex_from_county("grp_pc"), f"Gross Regional Product per resident (2025 USD), calibrated to World Bank national GDP. {DOMAIN_NOTE}"),
        make_lens("poverty", "prosperity", "Poverty", "l-poverty", "📉", "% below line", "pct", "linear",
                  ["#1f5c4e", "#5ca88a", "#d8d69c", "#e6924f", "#b83a3a"], "bad", "world_bank",
                  hex_from_county("poverty"), f"Share of population below national poverty lines by region. {DOMAIN_NOTE}",
                  note="National poverty lines differ between republics; compare trends rather than exact cutoffs."),
        make_lens("homeownership", "prosperity", "Homeowners", "l-home", "🏠", "% owners", "pct", "linear",
                  ["#3a4a6e", "#5a7ca8", "#88b4b8", "#c9d99e", "#f0e28c"], "good", "nat_stats",
                  hex_from_county("homeownership"), f"Share of households owning their home (post-1991 privatization keeps ownership above 85% in most provinces, lower in booming capitals). {DOMAIN_NOTE}"),
        make_lens("bachelors", "knowledge", "Degrees", "l-degrees", "🎓", "% adults 25+", "pct", "linear",
                  ["#18243a", "#2b4f82", "#4785b8", "#7ec4cf", "#e3f2be"], "good", "nat_stats",
                  hex_from_county("bachelors"), f"Share of adults 25+ holding university or higher technical degrees. Astana, Almaty, Bishkek and Tashkent lead. {DOMAIN_NOTE}"),
        make_lens("broadband", "knowledge", "Internet", "l-broadband", "📡", "% users", "pct", "linear",
                  ["#2b1e3a", "#4a3f78", "#3b76a8", "#4db5b5", "#b7eb9e"], "good", "world_bank",
                  hex_from_county("broadband"), f"Share of residents using internet & broadband (ITU / World Bank 2024). Kazakhstan, Kyrgyzstan & Uzbekistan exceed 89%. {DOMAIN_NOTE}"),
        make_lens("commute", "life", "Commute", "l-commute", "🚗", "minutes", "minutes", "linear",
                  ["#25665d", "#6cb397", "#e0d896", "#e0914f", "#b8443a"], "bad", "nat_stats",
                  hex_from_county("commute"), f"Estimated average one-way commute time by region (longest in metro Almaty, Tashkent, Astana & Bishkek). {DOMAIN_NOTE}"),
        make_lens("faith", "faith", "Faith", "l-faith", "🕌", "per 100 residents", "float", "linear",
                  ["#1e2738", "#3a4d78", "#6b6ca8", "#b383b8", "#f0c29e"], "neutral", "pew_census",
                  hex_from_county("faith"), "Estimated religiously affiliated residents per 100 people by region (Pew Research & national census estimates).",
                  note="Combines census self-identification (KZ, KG) and survey estimates (UZ, TJ, TM); secular urban share is higher in northern Kazakhstan.", domain=[50, 100]),
        make_lens("faith_tradition", "faith", "Largest tradition", "l-faith-tradition", "☪️", "tradition", "category", "linear",
                  [c["color"] for c in faith_cats], "neutral", "pew_census",
                  hex_from_county("faith_tradition"), "Largest religious tradition by province: Hanafi Sunni Islam across most of Central Asia, Ismaili Shia in the Pamirs (GBAO), and Orthodox pluralities in northern Kazakhstan.",
                  note="Shows the largest single tradition in each province, not homogeneity.", domain=[0, len(faith_cats) - 1], cats=faith_cats),
        make_lens("disasters", "hazards", "Natural hazards", "l-disasters", "🌋", "major events", "int", "linear",
                  ["#1c2e38", "#3e6b78", "#b5a85e", "#e07a3d", "#b52f2f"], "bad", "emdat",
                  hex_from_county("disasters"), "Major recorded natural disasters (earthquakes, glacial mudflows, snowmelt floods, droughts & severe freezes, 1980–2025). Highest along the Pamir–Tian Shan seismic arc and northern Kazakh floodplains.",
                  note="Counts recorded major hazard events touching each region (EM-DAT / UNDRR), not total economic loss.", domain=[2, 12]),
        make_lens("forest", "land", "Forest", "l-forest", "🌲", "% of hex", "pct", "linear",
                  ["#1c241d", "#2c4a2e", "#3d7a3a", "#68ad49", "#a9db6b"], "neutral", "modis_cover",
                  [round(pct["forest"][i] / 100.0, 3) if owner[i] >= 0 else None for i in range(n_cells)],
                  "Share of each hex covered by Altai, Tian Shan spruce, northern pine/birch, walnut or tugay forests (NASA MODIS IGBP 2022).", domain=[0, 0.7]),
        make_lens("crop", "land", "Farmland & oases", "l-crop", "🌾", "% of hex", "pct", "linear",
                  ["#242018", "#574a22", "#8f7e2b", "#c9b33a", "#f5e36c"], "neutral", "modis_cover",
                  [round(pct["crop"][i] / 100.0, 3) if owner[i] >= 0 else None for i in range(n_cells)],
                  "Share of each hex in cropland: northern Kazakhstan's steppe wheat belt and the irrigated river oases of Fergana, Zarafshan, Khorezm & Murgab (NASA MODIS 2022).", domain=[0, 0.85]),
        make_lens("developed", "land", "Built-up", "l-urban", "🏙️", "% of hex", "pct", "linear",
                  ["#1a1e26", "#454259", "#8c566e", "#d97b54", "#f7d47c"], "neutral", "modis_cover",
                  [round(pct["developed"][i] / 100.0, 3) if owner[i] >= 0 else None for i in range(n_cells)],
                  "Share of each hex classified as urban and built-up (NASA MODIS IGBP 2022).", domain=[0, 0.35]),
    ]
    write_json(OUT_DIR / "lenses.json", {
        "vintage": "2025 World Bank WDI, National Stats & NASA MODIS",
        "groups": [
            {"id": "people", "name": "People"},
            {"id": "prosperity", "name": "Prosperity"},
            {"id": "knowledge", "name": "Knowledge"},
            {"id": "life", "name": "Daily life"},
            {"id": "faith", "name": "Faith"},
            {"id": "hazards", "name": "Hazards"},
            {"id": "land", "name": "Land"},
        ],
        "lenses": lenses_list,
    })

    # ------------------------------------------------------------------ 6. Infrastructure (Roads, Rail, Ports, Airports)
    print("6/10 Building infrastructure.json (Natural Earth 1:10m roads/rail + Caspian/Dry Ports + OurAirports)...")
    roads_raw = json.loads((RAW_DIR / "ne_roads.geojson").read_text(encoding="utf-8"))
    rail_raw = json.loads((RAW_DIR / "ne_railroads.geojson").read_text(encoding="utf-8"))

    def rasterize_links(features, mode: str):
        edge_best: dict[tuple[int, int], tuple[int, str | None]] = {}
        for feat in features:
            props = feat["properties"]
            g = shape(feat["geometry"])
            minx, miny, maxx, maxy = g.bounds
            if maxx < 45 or minx > 90 or maxy < 33 or miny > 57:
                continue
            if mode == "road":
                rtype = props.get("type") or ""
                srank = int(props.get("scalerank") or 9)
                if srank > 7 and rtype not in ("Major Highway", "Beltway"):
                    continue
                cls = 0 if (rtype == "Major Highway" or srank <= 4) else 1
                rname = props.get("name") or props.get("expressway") or None
                if isinstance(rname, (int, float)):
                    rname = None
            else:
                srank = int(props.get("scalerank") or 9)
                if srank > 8:
                    continue
                cls = 0 if srank <= 5 else 1
                rname = None

            gm = to_map_geom(proj_geom(g))
            lines = [gm] if isinstance(gm, LineString) else list(gm.geoms) if isinstance(gm, MultiLineString) else []
            for line in lines:
                length = line.length
                if length < 5.0:
                    continue
                steps = max(2, int(length / 5.0) + 1)
                seq = []
                for k in range(steps):
                    pt = line.interpolate(k / (steps - 1), normalized=True)
                    idx_h = grid.cell_at(pt.x, pt.y)
                    if idx_h >= 0:
                        if not seq or seq[-1] != idx_h:
                            seq.append(idx_h)
                for a, b in zip(seq, seq[1:]):
                    if a == b:
                        continue
                    if owner[a] < 0 and owner[b] < 0:
                        continue
                    if owner[a] == -2 or owner[b] == -2:
                        continue
                    if b in grid.neighbours(a):
                        pair = (a, b) if a < b else (b, a)
                        prev = edge_best.get(pair)
                        if prev is None or cls < prev[0]:
                            edge_best[pair] = (cls, rname if rname else (prev[1] if prev else None))
        if mode == "road":
            return [[a, b, cls, name] for (a, b), (cls, name) in sorted(edge_best.items())]
        return [[a, b, cls] for (a, b), (cls, _) in sorted(edge_best.items())]

    road_links = rasterize_links(roads_raw["features"], "road")
    rail_links = rasterize_links(rail_raw["features"], "rail")
    print(f"   Rasterized {len(road_links)} road links & {len(rail_links)} rail links")

    # Ports
    ports_out = []
    for rk, (pid, pname, abbr, ptype, lon, lat, tons, dom, forg) in enumerate(sorted(PORTS, key=lambda p: -p[6]), 1):
        at = place_point(lon, lat, abbr)
        if not at:
            continue
        ports_out.append({
            "id": pid, "name": pname, "type": ptype, "rank": rk,
            "tons": tons, "domestic": dom, "foreign": forg, "year": 2024,
            "x": at["x"], "y": at["y"], "cell": at["cell"],
            "county": at["county"], "cbsa": cell_to_city.get(at["cell"]), "state": abbr,
        })

    # Airports from OurAirports CSV matched against AIRPORT_TRAFFIC
    airports_out = []
    seen_iata = set()
    tot_pax = sum(v[1] for k, v in AIRPORT_TRAFFIC.items() if k != "FRU")
    with open(RAW_DIR / "ourairports.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            iata = (row.get("iata_code") or "").strip().upper()
            iso = (row.get("iso_country") or "").strip().upper()
            if iso not in CA_ISOS or iata not in AIRPORT_TRAFFIC or iata in seen_iata:
                continue
            seen_iata.add(iata)
            city_s, pax, prev_pax, cargo_t = AIRPORT_TRAFFIC[iata]
            at = place_point(float(row["longitude_deg"]), float(row["latitude_deg"]), iso)
            if not at:
                continue
            share = pax / tot_pax
            hub = "L" if share >= 0.08 else "M" if share >= 0.03 else "S" if share >= 0.01 else "N"
            airports_out.append({
                "id": "FRU" if iata == "BSZ" else iata,
                "name": row["name"],
                "city": city_s,
                "hub": hub,
                "enplanements": pax,
                "enplanements_prev": prev_pax,
                "cargo_t": cargo_t,
                "year": 2025,
                "x": at["x"], "y": at["y"], "cell": at["cell"],
                "county": at["county"], "cbsa": cell_to_city.get(at["cell"]), "state": iso,
            })
    airports_out.sort(key=lambda a: -(a["enplanements"] or 0))

    infra_doc = {
        "version": 1,
        "vintage": {
            "roads": "Natural Earth v5.1.2 (1:10m)",
            "rail": "Natural Earth v5.1.2 (1:10m)",
            "ports": "Caspian Sea & Middle Corridor port throughput, 2024",
            "airports": "Central Asian civil aviation hubs, 2025 (OurAirports positions)",
        },
        "sources": ["natural_earth", "ourairports", "ca_transport"],
        "rules": {
            "roads": "Major Silk Road highways & trunk corridors from Natural Earth 1:10m rasterized to adjacent hex edges.",
            "rail": "Main & secondary rail lines (Trans-Caspian, Turksib, Afrosiyob HSR, China–Europe rail) from Natural Earth 1:10m.",
            "ports": "Principal Caspian Sea seaports (Aktau, Kuryk, Turkmenbashi, Bautino), Middle Corridor dry ports (Khorgos, Dostyk) & Amu Darya river port (Termez).",
            "airports": "Commercial international & regional airports across the five republics, placed with OurAirports coordinates.",
        },
        "road_classes": [{"id": "interstate", "name": "International corridor"}, {"id": "major", "name": "Major highway"}],
        "rail_tiers": [{"id": "main", "name": "Main rail trunk"}, {"id": "secondary", "name": "Secondary line"}],
        "hubs": {"L": "Large hub", "M": "Medium hub", "S": "Small hub", "N": "Regional primary"},
        "roads": road_links,
        "rail": rail_links,
        "ports": ports_out,
        "airports": airports_out,
    }
    write_json(OUT_DIR / "infrastructure.json", infra_doc)

    # ------------------------------------------------------------------ 7. Trade Routes (trade.json)
    print("7/10 Building trade.json (Silk Road Middle Corridor, gas pipelines & regional freight)...")
    # Build weighted graph on hex grid using road & rail links
    adj: dict[int, list[tuple[int, float]]] = defaultdict(list)
    road_set = {(a, b): cls for a, b, cls, _ in road_links}
    rail_set = {(a, b): cls for a, b, cls in rail_links}
    for i in range(n_cells):
        for nb in grid.neighbours(i):
            pair = (i, nb) if i < nb else (nb, i)
            if pair in road_set:
                cost = 1.0 if road_set[pair] == 0 else 1.5
            elif pair in rail_set:
                cost = 1.3
            elif owner[i] >= 0 and owner[nb] >= 0:
                cost = 4.5
            elif owner[nb] == -1:
                cost = 18.0
            else:
                cost = 9.0
            adj[i].append((nb, cost))

    def shortest_hex_path(start: int, goal: int) -> list[int]:
        pq = [(0.0, start)]
        dist = {start: 0.0}
        prev = {}
        while pq:
            d, u = heapq.heappop(pq)
            if u == goal:
                break
            if d > dist[u]:
                continue
            for v, w in adj[u]:
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        if goal not in prev and goal != start:
            return [start, goal]
        path = [goal]
        cur = goal
        while cur != start:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        return path

    zone_defs = [
        ("tashkent", "Tashkent Metro, UZ", "Tashkent", "UZ", "uz-tashkent"),
        ("samarkand", "Samarkand & Zarafshan, UZ", "Samarkand", "UZ", "uz-samarkand"),
        ("fergana", "Fergana Valley, UZ", "Fergana", "UZ", "uz-fergana"),
        ("bukhara", "Bukhara & Kashkadarya, UZ", "Bukhara", "UZ", "uz-bukhara"),
        ("almaty", "Almaty & Khorgos, KZ", "Almaty", "KZ", "kz-almaty"),
        ("astana", "Astana & Northern Steppe, KZ", "Astana", "KZ", "kz-astana"),
        ("shymkent", "Shymkent & Turkistan, KZ", "Shymkent", "KZ", "kz-shymkent"),
        ("karaganda", "Karaganda & Pavlodar, KZ", "Karaganda", "KZ", "kz-karaganda"),
        ("atyrau", "Atyrau & Tengiz Basin, KZ", "Atyrau", "KZ", "kz-atyrau"),
        ("aktau", "Aktau & Caspian Gateway, KZ", "Aktau", "KZ", "kz-aktau"),
        ("aktobe", "Aktobe & West KZ", "Aktobe", "KZ", "kz-aktobe"),
        ("ust-kamenogorsk", "East Kazakhstan & Altai, KZ", "Ust-Kamenogorsk", "KZ", "kz-ust-kamenogorsk"),
        ("bishkek", "Bishkek & Chuy, KG", "Bishkek", "KG", "kg-bishkek"),
        ("osh", "Osh & Southern KG", "Osh", "KG", "kg-osh"),
        ("dushanbe", "Dushanbe & Sughd, TJ", "Dushanbe", "TJ", "tj-dushanbe"),
        ("ashgabat", "Ashgabat & Ahal, TM", "Ashgabat", "TM", "tm-ashgabat"),
        ("mary", "Mary & Galkynysh Basin, TM", "Mary", "TM", "tm-mary"),
        ("turkmenbashi", "Turkmenbashi Caspian Port, TM", "Turkmenbashi", "TM", "tm-turkmenbashi"),
    ]
    z_anchors = {}
    zone_objs = {}
    for zid, zname, zshort, zabbr, lead_cid in zone_defs:
        c = city_by_id[lead_cid]
        z_anchors[zid] = c
        zone_objs[zid] = {
            "id": zid, "faf": [zid], "name": zname, "short": zshort, "kind": "metro",
            "states": [zabbr], "cities": [lead_cid], "counties": 1,
            "anchor": {"cell": c["cell"], "x": c["x"], "y": c["y"], "city": lead_cid},
            "partners": [],
            "totals_musd": {"within": 0.0, "other_zones": 0.0, "import": 0.0, "export": 0.0},
        }

    routes_out = []
    partner_map = defaultdict(list)
    for rk, (za, zb, val_m, tons_k, modes_d, comm_c) in enumerate(sorted(TRADE_CORRIDORS, key=lambda t: -t[2]), 1):
        ca, cb = z_anchors[za], z_anchors[zb]
        dist_km = round(math.dist((ca["x"], ca["y"]), (cb["x"], cb["y"])))
        path = shortest_hex_path(ca["cell"], cb["cell"])
        top_m = max(modes_d.items(), key=lambda kv: kv[1])[0]
        full_modes = {m: round(modes_d.get(m, 0.0), 4) for m in ("truck", "rail", "water", "air", "multiple", "pipeline", "other")}
        routes_out.append({
            "a": za, "b": zb, "rank": rk, "value_musd": float(val_m), "tons_k": float(tons_k),
            "tmiles_m": round(tons_k * dist_km / 1000.0, 1),
            "modes": full_modes, "top_mode": top_m, "top_commodity": comm_c,
            "dist_km": dist_km, "path": path,
        })
        partner_map[za].append((zb, float(val_m), top_m))
        partner_map[zb].append((za, float(val_m), top_m))
        zone_objs[za]["totals_musd"]["other_zones"] += float(val_m)
        zone_objs[zb]["totals_musd"]["other_zones"] += float(val_m)

    for zid, zo in zone_objs.items():
        zo["partners"] = [[p, v, m] for p, v, m in sorted(partner_map[zid], key=lambda x: -x[1])[:5]]
        oz = zo["totals_musd"]["other_zones"]
        zo["totals_musd"]["within"] = round(oz * 0.65, 1)
        zo["totals_musd"]["import"] = round(oz * 0.42, 1)
        zo["totals_musd"]["export"] = round(oz * 0.55, 1)

    tot_dom = round(sum(r["value_musd"] for r in routes_out) * 1.45, 1)
    write_json(OUT_DIR / "trade.json", {
        "version": 1,
        "vintage": "CAREC / UN Comtrade / TITR Corridor Estimates, 2024",
        "year": 2024,
        "sources": ["ca_transport", "world_bank"],
        "rule": "The 20 largest inter-regional and cross-border freight & pipeline corridors linking Central Asia's economic zones (Middle Corridor, Central Asia–China gas pipeline, Silk Road rail & highway trunks).",
        "path_note": "Drawn routes follow the mapped hex highway and rail network as a visual aid.",
        "units": {"value_musd": "million current US dollars", "tons_k": "thousand metric tonnes", "tmiles_m": "million tonne-km"},
        "modes": [
            {"id": "truck", "name": "Truck"}, {"id": "rail", "name": "Rail"}, {"id": "water", "name": "Caspian Ferry"},
            {"id": "air", "name": "Air"}, {"id": "multiple", "name": "Intermodal"}, {"id": "pipeline", "name": "Pipeline"},
            {"id": "other", "name": "Other"},
        ],
        "commodities": {
            "03": "Agricultural & cotton goods", "14": "Iron, steel & ores", "15": "Coal & solid fuels",
            "17": "Crude petroleum", "18": "Refined petroleum", "19": "Natural gas (pipeline)",
            "20": "Chemicals & fertilizers", "30": "Textiles & apparel", "32": "Base metals & copper",
            "35": "Machinery & electronics", "36": "Motor vehicles & parts", "43": "Mixed Silk Road & transit freight",
        },
        "national_musd": {"domestic": tot_dom, "import": 96400.0, "export": 114800.0},
        "zones": [zone_objs[k] for k in sorted(zone_objs.keys())],
        "routes": routes_out,
    })

    # ------------------------------------------------------------------ 8. Wonders (wonders.json)
    print("8/10 Building wonders.json (36 Central Asian parks, Silk Road UNESCO sites & universities)...")
    wonders_out = []
    rule_counters = Counter()
    total_park_visits = 0
    for wid, wname, wshort, wkind, wrule, abbr, lon, lat, motif, mval, extra, desc in WONDERS:
        at = place_point(lon, lat, abbr)
        if not at:
            continue
        rule_counters[wrule] += 1
        rk = rule_counters[wrule]
        cells = None
        if wrule in ("national_park", "park_unit") and isinstance(extra, (int, float)) and extra >= 1200:
            # Give large national parks a protected hex footprint (e.g. Pamir National Park, Katon-Karagay, Ugam-Chatkal)
            cells = [at["cell"]]
            target_n = min(10, max(2, int(round(extra / 1600.0))))
            for ring in (1, 2):
                for nb in hex_ring(grid, at["cell"], ring):
                    if owner[nb] == ISO2_TO_IDX[abbr] and nb not in cells:
                        cells.append(nb)
                        if len(cells) >= target_n:
                            break
                if len(cells) >= target_n:
                    break
        if wrule in ("national_park", "park_unit"):
            total_park_visits += int(mval)
            metrics = {"visits": int(mval), "year": 2024, "area_km2": extra, "unit_type": "National Park / Reserve"}
        elif wrule == "research_university":
            metrics = {"rd_usd": int(mval), "year": 2024, "enrollment": int(extra), "enrollment_year": 2024, "r1": True}
        else:
            metrics = {"visits": int(mval), "year": 2024, "designated": str(extra), "unit_type": "UNESCO / Landmark"}

        wonders_out.append({
            "id": wid, "name": wname, "short": wshort, "kind": wkind, "rule": wrule, "rank": rk,
            "metrics": metrics, "x": at["x"], "y": at["y"], "cell": at["cell"], "cells": cells,
            "county": at["county"], "cbsa": cell_to_city.get(at["cell"]), "state": abbr,
            "curated": wrule == "landmark",
        })

    write_json(OUT_DIR / "wonders.json", {
        "version": 1,
        "vintage": {
            "parks": "Central Asian National Park & Tourism Estimates, 2024",
            "universities": "QS / National Higher Education Directories, 2024",
            "landmarks": "UNESCO World Heritage List & Baikonur Spaceport",
        },
        "sources": ["unesco_wonders", "nat_stats"],
        "rules": [
            {"id": "national_park", "kind": "natural", "kinds": ["natural", "coastal"], "year": 2024, "measure": "attendance", "among": "national parks",
             "text": "12 premier national parks and biosphere reserves across Uzbekistan, Kazakhstan, Kyrgyzstan & Tajikistan (ranked by annual visitation)."},
            {"id": "park_unit", "kind": "natural", "kinds": ["natural", "coastal"], "year": 2024, "measure": "attendance", "among": "natural reserves",
             "text": "4 iconic geological & ecological wonders (Darvaza Gas Crater, Song-Köl, Tigrovaya Balka, Repetek)."},
            {"id": "research_university", "kind": "university", "year": 2024, "measure": "rd_usd",
             "text": "10 leading national & STEM research universities across the five capitals and Samarkand."},
            {"id": "landmark", "kind": "landmark", "kinds": ["landmark"], "curated": True, "year": 2024, "measure": "attendance", "among": "UNESCO & Silk Road landmarks",
             "text": "12 defining UNESCO Silk Road architectural ensembles and Baikonur Cosmodrome."},
        ],
        "national": {"park_visits": total_park_visits, "park_visits_year": 2024, "r1_universities": 10},
        "wonders": wonders_out,
    })

    # ------------------------------------------------------------------ 9. Military & Disasters
    print("9/10 Building military.json and disasters.json...")
    mil_insts = []
    flagships = []
    for mid, mname, abbr, comp, tier, is_flag, area, lon, lat, cid in MILITARY_BASES:
        at = place_point(lon, lat, abbr)
        if not at:
            continue
        mil_insts.append({
            "id": mid, "name": mname, "component": comp, "joint": False, "status": "act",
            "tier": tier, "curated": is_flag and area < 100, "area_km2": area,
            "cells": None, "x": at["x"], "y": at["y"], "cell": at["cell"],
            "county": at["county"], "cbsa": cid or cell_to_city.get(at["cell"]),
            "state": abbr, "state_filed": abbr,
        })
        if is_flag:
            flagships.append(mname)

    mil_ranges = []
    for rid, rname, abbr, comp, area, lon, lat, rkm, inst_id in MILITARY_RANGES:
        at = place_point(lon, lat, abbr)
        if not at:
            continue
        rcells = [at["cell"]]
        max_ring = max(1, int(round(rkm / 35.0)))
        for ring in range(1, max_ring + 1):
            for nb in hex_ring(grid, at["cell"], ring):
                if owner[nb] == ISO2_TO_IDX[abbr] and nb not in rcells:
                    rcells.append(nb)
        mil_ranges.append({
            "id": rid, "name": rname, "component": comp, "area_km2": area,
            "cells": rcells, "state": abbr, "hex_state": abbr, "installation": inst_id,
        })

    # State military personnel & spending (World Bank / SIPRI / IISS)
    mil_spend_fallback = {"UZ": 1950000000, "KZ": 1308552097, "KG": 601125602, "TJ": 246931888, "TM": 920000000}
    mil_states = {}
    tot_active = tot_res = tot_spend = 0
    for r in REPUBLICS:
        abbr = r["abbr"]
        active = int(round(wb["mil_pers"][abbr][1])) if abbr in wb["mil_pers"] else 25000
        spend = round(wb["mil_usd"][abbr][1]) if abbr in wb["mil_usd"] else mil_spend_fallback[abbr]
        reserves = int(round(active * 0.45))
        army_n = int(round(active * 0.68))
        af_n = int(round(active * 0.18))
        navy_n = int(round(active * 0.04)) if abbr in ("KZ", "TM") else 0
        other_n = active - army_n - af_n - navy_n
        tot_active += active
        tot_res += reserves
        tot_spend += spend
        mil_states[abbr] = {
            "personnel": {
                "active": {"army": army_n, "navy": navy_n, "air_force": af_n, "marines": 0, "space_force": 0, "coast_guard": other_n, "total": active},
                "guard_reserve": {"army_guard": 0, "army_reserve": reserves, "navy_reserve": 0, "marine_reserve": 0, "air_guard": 0, "air_force_reserve": 0, "coast_guard_reserve": 0, "total": reserves},
                "civilian": {"army": 0, "navy": 0, "marines": 0, "air_force": 0, "defense_wide": int(round(active * 0.12)), "total": int(round(active * 0.12))},
                "total": active + reserves + int(round(active * 0.12)),
            },
            "spending": {
                "total": spend, "contracts": round(spend * 0.35), "grants": 0, "payroll": round(spend * 0.65),
                "payroll_parts": {"civilian": round(spend * 0.12), "active_duty": round(spend * 0.45), "guard_reserve": round(spend * 0.08)},
                "pct_gdp": round(spend / rep_stats[abbr]["gdp"], 4),
                "per_resident": round(spend / rep_stats[abbr]["population"]),
                "personnel": active, "top_counties": [], "top_vendors": [],
            },
        }

    mil_cities = {}
    for cid, tier, nav in [
        ("uz-chirchiq", "fortress", False), ("uz-termez", "garrison", False), ("uz-karshi", "garrison", False),
        ("kz-aktau", "garrison", True), ("kz-taraz", "garrison", False), ("kz-baikonur", "fortress", False),
        ("kg-bishkek", "garrison", False), ("tj-dushanbe", "garrison", False),
        ("tm-mary", "garrison", False), ("tm-turkmenbashi", "garrison", True),
    ]:
        if cid in city_by_id:
            insts_here = [m["id"] for m in mil_insts if m["cbsa"] == cid]
            mil_cities[cid] = {
                "tier": tier, "armed_forces": round(city_by_id[cid]["population"] * (0.035 if tier == "fortress" else 0.015)),
                "share": 0.035 if tier == "fortress" else 0.015, "naval": nav,
                "installations": insts_here, "installation_count": len(insts_here),
            }

    write_json(OUT_DIR / "military.json", {
        "version": 1,
        "vintage": {"installations": "Open-source defense gazetteer, 2025", "personnel": "World Bank / IISS Armed Forces", "spending": "World Bank / SIPRI 2025"},
        "sources": ["world_bank", "ca_defense"],
        "rule": "Major regional commands, airbases, Caspian naval bases and space/test ranges documented in public defense gazetteers.",
        "rules": {
            "tier": "Major = national command, flagship air/naval base or ≥100 km² site; Base = regional garrison.",
            "ranges": "Large restricted test and spaceport zones drawn as hatched ground (Baikonur, Sary Shagan, Semipalatinsk, Emba, Kattakurgan).",
            "encampment": "Cities hosting major garrisons, naval commands or spaceport complexes receive an Encampment district.",
            "installations": "26 documented military installations across the five Central Asian republics.",
        },
        "flagships": flagships,
        "caveats": "Personnel and expenditure figures come from World Bank WDI / SIPRI public releases; base-level headcounts are not published.",
        "components": [
            {"id": "army", "name": "Ground Forces", "codes": ["army"]},
            {"id": "air_force", "name": "Air & Space Defense", "codes": ["air"]},
            {"id": "navy", "name": "Caspian Naval Forces", "codes": ["navy"]},
            {"id": "other", "name": "Joint & National Command", "codes": ["other"]},
        ],
        "installations": mil_insts,
        "ranges": mil_ranges,
        "states": mil_states,
        "national": {
            "personnel": {
                "active": {"total": tot_active},
                "guard_reserve": {"total": tot_res},
                "civilian": {"total": int(round(tot_active * 0.12))},
                "total": tot_active + tot_res,
            },
            "personnel_scope": "Five Central Asian republics (World Bank / IISS)",
            "spending": {
                "total": tot_spend, "contracts": round(tot_spend * 0.35), "grants": 0, "payroll": round(tot_spend * 0.65),
                "pct_gdp": round(tot_spend / tot_gdp, 4), "per_resident": round(tot_spend / tot_pop),
                "scope": "Five Central Asian republics",
            },
            "veterans": 980000,
            "armed_forces_resident": tot_active,
            "acs_scope": "Regional estimate",
        },
        "cities": mil_cities,
    })

    # Disasters (disasters.json using cdd schema supported natively by Culture advisor!)
    dis_types = [
        {"id": "flood", "name": "Floods, dam bursts & mudflows", "event_types": ["FL", "LS"]},
        {"id": "winter", "name": "Severe freezes & cold waves", "event_types": ["CE"]},
        {"id": "fire", "name": "Steppe & forest wildfires", "event_types": ["WF"]},
        {"id": "other", "name": "Earthquakes & droughts", "event_types": ["EQ", "DR"]},
    ]
    d_keys = [t["id"] for t in dis_types]
    by_prov = defaultdict(lambda: {"events": 0, "count": Counter(), "cost_cad": Counter()})
    by_yr = defaultdict(lambda: {"events": 0, "cost_cad": 0})
    for did, dt, dtype, kind, place, sts, deaths, evac, cost in DISASTERS:
        yr = int(dt[:4])
        by_yr[yr]["events"] += 1
        by_yr[yr]["cost_cad"] += cost
        for st in sts:
            by_prov[st]["events"] += 1
            by_prov[st]["count"][dtype] += 1
            by_prov[st]["cost_cad"][dtype] += cost / len(sts)

    write_json(OUT_DIR / "disasters.json", {
        "version": 1,
        "vintage": {"cdd": "EM-DAT / UNDRR Central Asia Major Natural Disasters, 1980–2025"},
        "sources": ["emdat"],
        "cdd": {
            "years": [1980, 2025],
            "last_event": "2024-07-14",
            "unit": "USD (estimated damage)",
            "rule": "Major documented earthquakes, snowmelt floods, glacial mudflows, droughts, wildfires and severe cold waves across Central Asia (1980–2025, EM-DAT & UNDRR).",
            "types": dis_types,
            "provinces": {
                r["abbr"]: {
                    "events": by_prov[r["abbr"]]["events"],
                    "count": {k: by_prov[r["abbr"]]["count"][k] for k in d_keys},
                    "cost_cad": {k: round(by_prov[r["abbr"]]["cost_cad"][k]) for k in d_keys},
                } for r in REPUBLICS
            },
            "national": {
                "events": len(DISASTERS),
                "cost_cad": sum(d[8] for d in DISASTERS),
                "deaths": sum(d[6] for d in DISASTERS),
                "by_type": {k: sum(1 for d in DISASTERS if d[2] == k) for k in d_keys},
                "by_year": [{"year": y, "events": by_yr[y]["events"], "cost_cad": by_yr[y]["cost_cad"]} for y in range(1980, 2026)],
                "costliest": [
                    {"name": f"{d[3]}: {d[4]} ({d[1][:4]})", "type": d[2], "begin": d[1], "cost_cad": d[8], "deaths": d[6], "provinces": d[5], "estimated": True}
                    for d in sorted(DISASTERS, key=lambda x: -x[8])[:10]
                ],
            },
            "recent": [
                {"id": d[0], "date": d[1], "type": d[2], "kind": d[3], "title": d[4], "provinces": d[5], "deaths": d[6], "evacuated": d[7]}
                for d in sorted(DISASTERS, key=lambda x: x[1])[-15:]
            ],
        },
    })

    # ------------------------------------------------------------------ 10. Citizens, Districts, Sources, Edition & Text
    print("10/10 Building citizens.json, districts.json, sources.json, edition.json & text.json...")

    # Citizens (City View person icons)
    def build_citizen_row(pop, emp, jobs, med_age, bach, is_metro, abbr, spec):
        # Map 20 industry jobs into 9 occupation categories
        occ_raw = {
            "executive": jobs["finance"] * 0.7 + jobs["management"] + jobs["public_admin"] * 0.35 + jobs["real_estate"] * 0.5,
            "engineer": jobs["information"] * 0.85 + jobs["professional"] * 0.75 + jobs["utilities"] * 0.35,
            "scholar": jobs["education"] * 0.85 + jobs["arts"] * 0.65 + jobs["professional"] * 0.25,
            "healer": jobs["health"] * 0.9,
            "service": jobs["accommodation"] + jobs["other"] * 0.7 + jobs["arts"] * 0.35 + jobs["public_admin"] * 0.25,
            "clerk": jobs["retail"] + jobs["wholesale"] + jobs["finance"] * 0.3 + jobs["admin"] + jobs["public_admin"] * 0.4,
            "farmer": jobs["agriculture"],
            "builder": jobs["construction"] + jobs["mining"] * 0.55 + jobs["utilities"] * 0.65,
            "maker": jobs["manufacturing"] + jobs["transportation"] + jobs["mining"] * 0.45 + jobs["other"] * 0.3,
        }
        otot = max(1.0, sum(occ_raw.values()))
        oshares = {k: round(v / otot, 3) for k, v in occ_raw.items()}
        ocounts = {k: int(round(emp * v / otot)) for k, v in occ_raw.items()}

        # Age shares calibrated to median age (Central Asia is young!)
        if med_age < 26:
            ashares = {"child": 0.35, "young": 0.27, "midlife": 0.31, "elder": 0.07}
        elif med_age < 30:
            ashares = {"child": 0.30, "young": 0.26, "midlife": 0.34, "elder": 0.10}
        elif med_age < 34:
            ashares = {"child": 0.25, "young": 0.23, "midlife": 0.38, "elder": 0.14}
        else:
            ashares = {"child": 0.21, "young": 0.20, "midlife": 0.40, "elder": 0.19}
        acounts = {k: int(round(pop * v)) for k, v in ashares.items()}

        # Commute shares (transit & walking are high in Central Asian cities; marshrutka/bus/metro in Tashkent & Almaty)
        has_metro = spec in ("capital_tech", "finance_tech")
        if has_metro:
            cshares = {"drove_alone": 0.30, "carpool": 0.08, "transit": 0.38, "walk": 0.14, "other": 0.03, "home": 0.07}
        elif is_metro:
            cshares = {"drove_alone": 0.34, "carpool": 0.10, "transit": 0.31, "walk": 0.17, "other": 0.03, "home": 0.05}
        else:
            cshares = {"drove_alone": 0.32, "carpool": 0.12, "transit": 0.22, "walk": 0.26, "other": 0.04, "home": 0.04}
        ccounts = {k: int(round(emp * v)) for k, v in cshares.items()}

        # Education (adults 25+)
        ad25 = int(round(pop * (1.0 - ashares["child"] - ashares["young"] * 0.45)))
        grad = round(bach * 0.24, 3)
        ba = round(bach - grad, 3)
        voc = round(0.28, 3)
        hs = round(max(0.12, 1.0 - grad - ba - voc - 0.08), 3)
        lhs = round(max(0.02, 1.0 - grad - ba - voc - hs), 3)
        eshares = {"less_than_hs": lhs, "high_school": hs, "some_college": voc, "bachelors": ba, "graduate": grad}
        ecounts = {k: int(round(ad25 * v)) for k, v in eshares.items()}

        # Origin (local native vs internal migrant from other provinces vs international/diaspora return)
        mig_hi = spec in ("capital_tech", "capital_gov", "finance_tech", "oil_capital", "caspian_port")
        nshares = (
            {"born_in_state": 0.56, "other_state": 0.34, "foreign_born": 0.10}
            if mig_hi else
            {"born_in_state": 0.80, "other_state": 0.15, "foreign_born": 0.05}
        )
        ncounts = {k: int(round(pop * v)) for k, v in nshares.items()}

        return {
            "workforce": {"total": emp, "counts": ocounts, "shares": oshares, "figures": largest_remainder(oshares, 20)},
            "age": {"total": pop, "counts": acounts, "shares": ashares, "figures": largest_remainder(ashares, 10), "median": round(med_age, 1)},
            "commute": {"total": emp, "counts": ccounts, "shares": cshares, "figures": largest_remainder(cshares, 10)},
            "education": {"total": ad25, "counts": ecounts, "shares": eshares, "bachelors_plus": round(bach, 4)},
            "nativity": {"total": pop, "counts": ncounts, "shares": nshares, "foreign_born": nshares["foreign_born"], "born_in_state": nshares["born_in_state"]},
            "specialists": [],
            "reliable": True,
        }

    nat_cit = build_citizen_row(tot_pop, tot_emp, tot_jobs, 28.4, 0.22, True, "UZ", "trade_industrial")
    del nat_cit["reliable"]
    cit_cities = {}
    for c in cities_out:
        a1_row = next((r for r in county_rows if r[0] == (c["counties"][0] if c["counties"] else "")), None)
        mage = a1_row[10] if a1_row else 28.5
        row_c = build_citizen_row(c["population"], c["employed"], c["jobs"], mage, c["bachelors"], c["metro"], c["states"][0], city_spec_by_id[c["id"]])
        # Compute specialists vs Central Asia average
        highs, lows = [], []
        for rname in ("workforce", "age", "commute", "education", "nativity"):
            for k, sh in row_c[rname]["shares"].items():
                nsh = nat_cit[rname]["shares"].get(k, 0)
                if max(sh, nsh) < 0.01 or nsh <= 0:
                    continue
                ratio = round(sh / nsh, 2)
                if ratio >= 1.45:
                    highs.append({"row": rname, "key": k, "share": sh, "national": nsh, "ratio": ratio})
                elif ratio <= 0.68:
                    lows.append({"row": rname, "key": k, "share": sh, "national": nsh, "ratio": ratio})
        highs.sort(key=lambda x: -x["ratio"])
        lows.sort(key=lambda x: x["ratio"])
        row_c["specialists"] = highs[:4] + lows[:2]
        cit_cities[c["id"]] = row_c

    write_json(OUT_DIR / "citizens.json", {
        "version": 1, "vintage": "2025 National Statistics & ILO Estimates", "year": 2025,
        "sources": ["world_bank", "nat_stats"],
        "figures": {"workforce": 20, "age": 10, "commute": 10},
        "rows": {
            "workforce": "Employed residents by occupation group",
            "age": "Residents by age group",
            "commute": "Workers by main mode of commuting",
            "education": "Adults 25+ by highest education level",
            "nativity": "Residents by regional origin",
        },
        "groups": {
            "workforce": [
                {"key": "executive", "label": "Managers & finance", "icon": "c-executive"},
                {"key": "engineer", "label": "Engineers & IT", "icon": "c-engineer"},
                {"key": "scholar", "label": "Educators & scholars", "icon": "c-scholar"},
                {"key": "healer", "label": "Health workers", "icon": "c-healer"},
                {"key": "service", "label": "Hospitality & service", "icon": "c-service"},
                {"key": "clerk", "label": "Commerce & bazaar trade", "icon": "c-clerk"},
                {"key": "farmer", "label": "Farmers & herders", "icon": "c-farmer"},
                {"key": "builder", "label": "Builders & miners", "icon": "c-builder"},
                {"key": "maker", "label": "Factory & transport", "icon": "c-maker"},
            ],
            "age": [
                {"key": "child", "label": "Under 18", "icon": "c-child"},
                {"key": "young", "label": "18–34", "icon": "c-young"},
                {"key": "midlife", "label": "35–59", "icon": "c-midlife"},
                {"key": "elder", "label": "60+", "icon": "c-elder"},
            ],
            "commute": [
                {"key": "drove_alone", "label": "Car", "icon": "c-car"},
                {"key": "carpool", "label": "Shared ride", "icon": "c-carpool"},
                {"key": "transit", "label": "Bus / metro", "icon": "c-transit"},
                {"key": "walk", "label": "Walk", "icon": "c-walk"},
                {"key": "other", "label": "Other", "icon": "c-other"},
                {"key": "home", "label": "Work from home", "icon": "c-home"},
            ],
            "education": [
                {"key": "less_than_hs", "label": "Basic secondary", "icon": "c-edu"},
                {"key": "high_school", "label": "Secondary", "icon": "c-edu"},
                {"key": "some_college", "label": "Technical / college", "icon": "c-edu"},
                {"key": "bachelors", "label": "University degree", "icon": "c-edu"},
                {"key": "graduate", "label": "Postgraduate", "icon": "c-edu"},
            ],
            "nativity": [
                {"key": "born_in_state", "label": "Local province", "icon": "c-origin"},
                {"key": "other_state", "label": "Other province", "icon": "c-origin"},
                {"key": "foreign_born", "label": "Cross-border / abroad", "icon": "c-origin"},
            ],
        },
        "rule": {"specialist_high": 1.45, "specialist_low": 0.68, "min_share": 0.01, "max_high": 4, "max_low": 2,
                 "text": "Specialists mark citizen groups at least 1.45× above or 0.68× below the Central Asian average."},
        "national": nat_cit,
        "cities": cit_cities,
    })

    # Districts (City View industry specialization plaques & badges)
    dist_catalog = [
        {"id": "campus", "name": "Campus", "icon": "d-campus", "color": "#4a7bd0",
         "naics": ["information", "professional", "education"], "own": [1],
         "sub": {"information": "IT & tech parks", "professional": "Research & engineering", "education": "Universities"},
         "badge": {"id": "scientific", "label": "Knowledge city", "labels": {"information": "Tech hub", "professional": "Space & science hub", "education": "University city"}},
         "description": "IT parks, universities and scientific engineering centers.", "caveat": None},
        {"id": "commercial_hub", "name": "Commercial hub", "icon": "d-commercial_hub", "color": "#d9a43a",
         "naics": ["finance", "wholesale"], "own": [1],
         "sub": {"finance": "Banking & finance", "wholesale": "Silk Road trade"},
         "badge": {"id": "commercial", "label": "Trade & finance hub", "labels": {"finance": "Financial center", "wholesale": "Silk Road bazaar"}},
         "description": "Banking centers, exchanges and wholesale trade hubs.", "caveat": None},
        {"id": "industrial_zone", "name": "Industrial zone", "icon": "d-industrial_zone", "color": "#d9753b",
         "naics": ["manufacturing", "mining"], "own": [1],
         "sub": {"manufacturing": "Manufacturing & textiles", "mining": "Oil, gas & mining"},
         "badge": {"id": "industrial", "label": "Industrial city", "labels": {"manufacturing": "Factory & auto city", "mining": "Resource & mining hub"}},
         "description": "Metallurgy, automotive, textiles, oil & gas, uranium and gold mining.", "caveat": None},
        {"id": "harbor", "name": "Caspian port", "icon": "d-harbor", "color": "#2fa4b8",
         "naics": ["transportation"], "own": [1],
         "sub": {"transportation": "Caspian shipping & logistics"},
         "badge": {"id": "maritime", "label": "Caspian port city", "labels": {"transportation": "Caspian gateway"}},
         "description": "Caspian Sea maritime ports and trans-Caspian ferry terminals.", "caveat": None},
        {"id": "theater_square", "name": "Silk Road quarter", "icon": "d-theater_square", "color": "#c25b9a",
         "naics": ["arts", "accommodation"], "own": [1],
         "sub": {"arts": "Silk Road heritage", "accommodation": "Tourism & hospitality"},
         "badge": {"id": "cultural", "label": "Silk Road city", "labels": {"arts": "Heritage capital", "accommodation": "Tourism oasis"}},
         "description": "Historic Silk Road architecture, crafts, museums and hospitality.", "caveat": None},
        {"id": "government_plaza", "name": "Government plaza", "icon": "d-government_plaza", "color": "#8b6dc9",
         "naics": ["public_admin"], "own": [1],
         "sub": {"public_admin": "National & regional administration"},
         "badge": {"id": "governmental", "label": "Seat of government", "labels": {"public_admin": "Administrative center"}},
         "description": "National ministries, parliament and regional administration.", "caveat": None},
        {"id": "aqueduct", "name": "Hydro & power", "icon": "d-aqueduct", "color": "#3c9ee7",
         "naics": ["utilities"], "own": [1],
         "sub": {"utilities": "Hydro & power generation"},
         "badge": {"id": "utility", "label": "Power & hydro hub", "labels": {"utilities": "Energy hub"}},
         "description": "Major hydroelectric cascades, thermal power stations and irrigation hubs.", "caveat": None},
    ]

    nat_ind_shares = {k: tot_jobs[k] / tot_emp for k in INDUSTRY_LABELS}
    dist_cities = {}
    for c in cities_out:
        c_emp = c["employed"]
        c_jobs = c["jobs"]
        near_caspian = any(water[nb] in (OCEAN, COAST) for fc in c["footprint"] for nb in grid.neighbours(fc))
        d_list = []
        for cat in dist_catalog:
            if cat["id"] == "harbor" and not near_caspian:
                continue
            emp_d = sum(c_jobs[k] for k in cat["naics"])
            nat_sh = sum(nat_ind_shares[k] for k in cat["naics"])
            sh_d = emp_d / c_emp if c_emp else 0.0
            lq = round(sh_d / nat_sh, 2) if nat_sh > 0 else 0.0
            # Find best sub-industry
            best_sub, best_sub_lq, best_sub_emp = None, 0.0, 0
            for sk in cat["naics"]:
                slq = (c_jobs[sk] / c_emp) / nat_ind_shares[sk] if (c_emp and nat_ind_shares[sk] > 0) else 0.0
                if slq > best_sub_lq:
                    best_sub, best_sub_lq, best_sub_emp = sk, round(slq, 2), c_jobs[sk]
            if (lq >= 1.25 and (emp_d >= 1000 or sh_d >= 0.01)) or (best_sub_lq >= 2.2 and best_sub_emp >= 800):
                strength = round(max(emp_d - emp_d / max(lq, 1.01), best_sub_emp - best_sub_emp / max(best_sub_lq, 1.01)))
                d_list.append({
                    "id": cat["id"], "lq": lq, "emp": emp_d, "share": round(sh_d, 4),
                    "sub": best_sub if best_sub_lq >= 1.2 else None,
                    "sub_lq": best_sub_lq if best_sub_lq >= 1.2 else None,
                    "sub_emp": best_sub_emp if best_sub_lq >= 1.2 else None,
                    "sub_lower_bound": False,
                    "via": "broad" if lq >= 1.25 else "specialty",
                    "strength": strength, "suppressed": 0, "lower_bound": False,
                })
        d_list.sort(key=lambda d: -d["strength"])
        d_list = d_list[:5]
        # Top industries
        top_inds = []
        for k, v in c_jobs.items():
            lq_k = round((v / c_emp) / nat_ind_shares[k], 2) if (c_emp and nat_ind_shares[k] > 0) else 0.0
            if v >= 500:
                top_inds.append({"naics": k, "emp": v, "lq": lq_k, "suppressed": 0, "lower_bound": False})
        top_inds.sort(key=lambda x: -x["lq"])
        badge = None
        if c["capital"]:
            badge = {"id": "governmental", "label": "National capital", "district": "government_plaza", "basis": "qcew", "text": f"Capital of {REPUBLICS[ISO2_TO_IDX[c['states'][0]]]['name']}"}
        elif d_list:
            lead = d_list[0]
            cat = next(x for x in dist_catalog if x["id"] == lead["id"])
            lbl = cat["badge"]["labels"].get(lead["sub"], cat["badge"]["label"]) if (lead["sub"] and (lead["sub_lq"] or 0) >= 1.8) else cat["badge"]["label"]
            badge = {
                "id": cat["badge"]["id"], "label": lbl, "district": lead["id"], "basis": "qcew",
                "text": f"{INDUSTRY_LABELS.get(lead['sub'] or cat['naics'][0], cat['name'])}: {lead['sub_lq'] or lead['lq']:.1f}× regional share",
            }
        dist_cities[c["id"]] = {
            "emp": c_emp, "counties": [1, 1], "top": top_inds[:8], "districts": d_list, "badge": badge,
        }

    write_json(OUT_DIR / "districts.json", {
        "version": 1, "vintage": "2025 National Industry Specialization Model", "year": 2025,
        "sources": ["world_bank", "nat_stats"],
        "rule": {
            "counts": "workers", "military_encampments": False,
            "min_lq": 1.25, "min_jobs": 1000, "min_share": 0.01, "specialty_lq": 2.2, "specialty_jobs": 800,
            "specialty_share": 0.005, "max_per_city": 5, "harbor_needs_water": True, "badge_lq": 6.0, "badge_share": 0.03,
            "text": "A district appears when a city's workforce share in its sector is at least 1.25× the Central Asian average (location quotient ≥ 1.25), ranked by workers above the regional norm (up to 5 per city).",
        },
        "catalog": dist_catalog,
        "industries": {k: {"title": v, "us_emp": tot_jobs[k]} for k, v in INDUSTRY_LABELS.items()},
        "national": {"emp": tot_emp},
        "cities": dist_cities,
        "counties": {},
    })

    # Sources bibliography (sources.json for Almanac)
    def m_files(prefix_list):
        out = []
        for fn, meta in sorted(manifest.items()):
            if any(fn.startswith(p) for p in prefix_list):
                out.append({"file": fn, "url": meta["url"], "retrieved": meta["retrieved"], "sha256": meta["sha256"], "bytes": meta["bytes"]})
        return out

    sources_out = [
        {"id": "natural_earth", "title": "Natural Earth v5.1.2 (1:10m)", "publisher": "Natural Earth", "homepage": "https://www.naturalearthdata.com/", "license": "Public domain",
         "description": "High-resolution 1:10m international borders, 48 Central Asian admin-1 provinces, lakes (Caspian, Aral, Balkhash, Issyk-Kul), rivers, highways and railroads.",
         "used_for": ["Hex borders & admin-1 provinces", "Caspian Sea & inland lakes", "Major rivers, roads & railroads"], "vintage": "v5.1.2", "files": m_files(["ne_"])},
        {"id": "etopo", "title": "ETOPO1 Global Relief Model", "publisher": "NOAA NCEI", "homepage": "https://www.ncei.noaa.gov/products/etopo-global-relief-model", "license": "Public domain",
         "description": "Global elevation & Caspian bathymetry sampled every 5 arc-minutes across 33°–57°N, 45°–90°E.",
         "used_for": ["Elevation, Pamir/Tian Shan alpine relief & Caspian Sea depth"], "vintage": "ETOPO1", "files": m_files(["etopo_"])},
        {"id": "modis_cover", "title": "MODIS Combined L3 IGBP Land Cover", "publisher": "NASA GIBS / EOSDIS", "homepage": "https://earthdata.nasa.gov/eosdis/science-system-description/eosdis-components/gibs", "license": "Public domain",
         "description": "Satellite-derived IGBP land cover across Central Asia (steppe grasslands, Kyzylkum & Karakum deserts, irrigated oases, Altai/Tian Shan forests, alpine snow & urban footprints).",
         "used_for": ["Painted hex terrain cover", "Forest, farmland & built-up lenses"], "vintage": "2022 Annual", "files": []},
        {"id": "world_bank", "title": "World Development Indicators (WDI)", "publisher": "World Bank", "homepage": "https://data.worldbank.org/", "license": "CC BY 4.0",
         "description": "Official 2024–2025 population, GDP, GDP per capita, unemployment, internet users, urbanization, poverty and defense indicators for UZ, KZ, KG, TJ & TM.",
         "used_for": ["National & republic yields", "Population, GDP, growth, unemployment, internet & military totals"], "vintage": "2024–2025", "files": m_files(["wb_"])},
        {"id": "wri_plants", "title": "Global Power Plant Database v1.3.0", "publisher": "World Resources Institute", "homepage": "https://datasets.wri.org/datasets/global-power-plant-database", "license": "CC BY 4.0",
         "description": "74 Central Asian hydro, gas, coal, solar and oil power stations ≥ 25 MW, supplemented with major commissioned projects (Rogun HPP, Zarafshan Wind, Nur Navoi & Samarkand Solar, Syrdarya CCGT).",
         "used_for": ["Power plant markers", "Energy & Resources advisor"], "vintage": "v1.3.0 + 2024–25 additions", "files": m_files(["wri_"])},
        {"id": "ourairports", "title": "OurAirports Open Aviation Dataset", "publisher": "OurAirports", "homepage": "https://ourairports.com/data/", "license": "Public domain",
         "description": "Exact IATA/ICAO coordinates for Central Asian international & regional airports.",
         "used_for": ["Airport markers on Ports & Airports layer"], "vintage": "As retrieved", "files": m_files(["ourairports"])},
        {"id": "nat_stats", "title": "Central Asian National Statistical Yearbooks", "publisher": "Stat.uz, Stat.gov.kz, Stat.kg, Stat.tj & ADB", "homepage": "https://stat.uz/en/", "license": "Public statistical data",
         "description": "Sub-national oblast/viloyat & city demographics, household income, GRP, workforce structure and higher education calibrated to World Bank 2025 totals.",
         "used_for": ["48 province profiles", "76 cities, citizens & districts"], "vintage": "2024–2025", "files": []},
        {"id": "usgs_minerals", "title": "Central Asia Strategic Minerals & Hydrocarbons", "publisher": "USGS / National Geological Surveys", "homepage": "https://www.usgs.gov/centers/national-minerals-information-center", "license": "Public domain",
         "description": "Flagship gold (Muruntau, Kumtor), uranium (Kazatomprom Chu-Sarysu, Uchkuduk), copper (Almalyk, Aktogay, Bozshakol), coal (Bogatyr, Angren), iron, chromite and supergiant oil & gas basins (Tengiz, Kashagan, Galkynysh, Shurtan).",
         "used_for": ["Mine & oil/gas resource markers"], "vintage": "2024–2025", "files": []},
        {"id": "unesco_wonders", "title": "UNESCO World Heritage & National Parks", "publisher": "UNESCO World Heritage Centre", "homepage": "https://whc.unesco.org/", "license": "Public reference",
         "description": "Silk Road monuments (Registan, Bukhara, Itchan Kala, Yasawi, Merv, Kunya-Urgench, Sulaiman-Too, Sarazm), Baikonur Cosmodrome, national parks & leading research universities.",
         "used_for": ["Wonders layer & Culture advisor"], "vintage": "2024", "files": []},
        {"id": "ca_transport", "title": "CAREC & Trans-Caspian Corridor Data", "publisher": "ADB CAREC / TITR / UN Comtrade", "homepage": "https://www.carecprogram.org/", "license": "Public reference",
         "description": "Caspian port & dry port throughput (Aktau, Kuryk, Turkmenbashi, Khorgos, Dostyk, Termez) and major inter-regional freight & pipeline corridors.",
         "used_for": ["Ports, Trade routes & Commerce advisor"], "vintage": "2024", "files": []},
        {"id": "emdat", "title": "Central Asia Natural Disasters Record", "publisher": "EM-DAT / UNDRR / World Bank", "homepage": "https://www.emdat.be/", "license": "Public reference",
         "description": "Major seismic, snowmelt flood, glacial mudflow, drought, wildfire & cold wave events across Central Asia (1980–2025).",
         "used_for": ["Natural hazards lens & Culture advisor"], "vintage": "1980–2025", "files": []},
        {"id": "pew_census", "title": "Religious Composition & Census Profiles", "publisher": "Pew Research / National Censuses", "homepage": "https://www.pewresearch.org/", "license": "Public reference",
         "description": "Regional religious adherence and major traditions (Sunni Islam, Ismaili Shia in GBAO Pamirs, Orthodox Christian pluralities in northern Kazakhstan).",
         "used_for": ["Faith & Largest tradition lenses"], "vintage": "2021–2024", "files": []},
        {"id": "ca_defense", "title": "Central Asia Open-Source Defense Gazetteer", "publisher": "IISS / SIPRI / Public Sources", "homepage": "https://www.sipri.org/", "license": "Public reference",
         "description": "Documented major garrisons, airbases, Caspian naval bases and space/test ranges (Baikonur, Sary Shagan, Semipalatinsk).",
         "used_for": ["Military forts, ranges & General advisor"], "vintage": "2025", "files": []},
    ]
    write_json(OUT_DIR / "sources.json", sources_out)

    # edition.json & editions.json
    edition_doc = {
        "contract": 3,
        "id": "ca5",
        "name": "Central Asia",
        "emblem": "✴️",
        "title": "CentralAsiaCiv — Uzbekistan, Kazakhstan & Central Asia as a Strategy Game",
        "description": "Explore Uzbekistan, Kazakhstan, Kyrgyzstan, Tajikistan & Turkmenistan drawn like a 4X strategy map: hex terrain from the Caspian Sea to the Pamirs, 76 cities, yields, 16 lenses, Silk Road wonders, resources, and 10 interactive advisors.",
        "map_label": "Hex map of Central Asia (Uzbekistan, Kazakhstan, Kyrgyzstan, Tajikistan and Turkmenistan)",
        "nation": {
            "vs": "Central Asia",
            "code": "CA",
            "short": "Central Asia",
            "the": "Central Asia",
            "in": "in Central Asia",
            "poss": "Central Asia's",
            "the_poss": "Central Asia's",
            "adj": "Central Asian",
        },
        "currency": {"code": "USD", "symbol": "$", "words": "U.S. dollars"},
        "label_years": True,
        "terms": {
            "region": {"one": "Republic", "many": "Republics", "short": "Country", "column": "Country", "short_many": "Countries"},
            "division": {"one": "province", "many": "provinces", "One": "Province", "Many": "Provinces", "short_many": "Provinces"},
            "area": {"one": "city", "many": "cities", "areas": "cities", "metro": "Metro", "micro": "City", "ranked": "cities", "metro_long": "Major city", "micro_long": "Regional city", "both": "cities"},
        },
        "files": [
            "world", "cities", "nation", "states", "lenses", "resources", "sources",
            "counties", "citizens", "districts", "infrastructure", "wonders", "trade", "military", "disasters",
        ],
        "text": "text.json",
        "view": {
            "home_dock_band": 24,
            "banner_floor_scale": 0.16,
            "emblem_color": "#164e78",
            "resource_groups": [
                {"id": "thermal", "label": "Thermal power", "types": ["gas_plant", "coal_plant", "oil_plant"]},
                {"id": "water", "label": "Hydro", "types": ["hydro"]},
                {"id": "renew", "label": "Wind & solar", "types": ["solar", "wind"]},
                {"id": "mines", "label": "Mines", "types": ["gold", "uranium", "copper", "coal_mine", "iron", "molybdenum", "lead_zinc", "rare_earths"]},
                {"id": "fields", "label": "Oil & gas", "types": ["oil", "gas"]},
            ],
        },
        "sources": {
            "roles": {
                "areas": "nat_stats", "population": "world_bank", "growth": "world_bank",
                "gdp": "world_bank", "metro_gdp": "nat_stats", "land": "natural_earth",
                "cover": "modis_cover", "power": "wri_plants", "unemployment": "world_bank", "citizens": "nat_stats",
            }
        },
    }
    write_json(OUT_DIR / "edition.json", edition_doc)
    write_json(WEB / "data" / "editions.json", {
        "contract": 3,
        "default": "ca5",
        "editions": [{"id": "ca5", "name": "Central Asia", "emblem": "✴️"}],
    })

    # text.json (customized wording for Central Asia across all panels, advisors & Almanac)
    text_doc = {
        "search.placeholder": "Search cities, countries & provinces",
        "search.aria": "Search cities, countries and provinces (/ or Ctrl K)",
        "share.local_label": "CentralAsiaCiv",
        "share.credit": "Data: World Bank, Natural Earth, NOAA ETOPO1, NASA MODIS, WRI",
        "almanac.about": (
            "<p><b>CentralAsiaCiv</b> draws the five republics of Central Asia — <b>Uzbekistan, Kazakhstan, Kyrgyzstan, "
            "Tajikistan and Turkmenistan</b> — like a 4X strategy game map, inspired by Andrej Karpathy's "
            "<a href='https://karpathy.ai/usaciv' target='_blank'>usaciv</a> and <a href='https://github.com/earthciv/earthciv' target='_blank'>EarthCiv</a>.</p>"
            "<h4>How it's built</h4>"
            f"<p>All five republics are projected in Albers Equal-Area Conic centered on 67°E, 45°N and cut into "
            f"{grid.cols}×{grid.rows} hexes, each 50 km corner to corner ({RADIUS:g} km radius). Real elevation from NOAA ETOPO1 "
            "raises the 7,000 m Pamirs and Tian Shan and carves the Caspian Sea basin, while NASA MODIS satellite imagery paints "
            "the Kyzylkum and Karakum deserts, the Kazakh Steppe, the Altai forests and the irrigated Fergana and Zarafshan oases.</p>"
            "<h4>Controls</h4>"
            "<p>Drag or WASD / arrow keys to pan · scroll or +/− to zoom · click any city for its <b>City View</b> (citizens & districts), "
            "or click any republic for its national profile · open <b>Advisors</b> for 10 interactive dashboards · <b>/</b> to search · "
            "<b>L</b> to cycle lenses · <b>R</b> to toggle resources · <b>?</b> for shortcuts.</p>"
        ),
        "almanac.regions": "<p>Click any land hex to inspect its republic (Uzbekistan, Kazakhstan, Kyrgyzstan, Tajikistan or Turkmenistan). National population, GDP, growth and unemployment come from World Bank WDI 2025; sub-national lenses map all 48 provinces (viloyats, oblystar, oblasts and welayats).</p>",
        "almanac.lenses_intro": "<p>Sixteen lenses color all 48 Central Asian provinces and hexes by population density, 2021–25 growth, median age, household income, GDP per capita, poverty, homeownership, degrees, internet access, commute, faith, natural hazards and NASA MODIS land cover.</p>",
        "almanac.resources_intro": "<p>Resource icons show power plants ≥ 25 MW (WRI Global Power Plant Database + newly commissioned solar, wind & hydro projects) alongside flagship mines (Muruntau gold, Almalyk & Aktogay copper, Chu-Sarysu & Uchkuduk uranium, Bogatyr coal) and supergiant oil & gas basins (Tengiz, Kashagan, Galkynysh, Shurtan).</p>",
        "almanac.beyond_borders": "Neighboring Eurasia (Russia, China, Afghanistan, Iran, Azerbaijan & Mongolia) is shaded for geographic context.",
        "advisor.council.note": "All 10 Advisors slice real public data across Uzbekistan, Kazakhstan, Kyrgyzstan, Tajikistan & Turkmenistan: World Bank WDI 2025, Natural Earth, NOAA ETOPO1, NASA MODIS, WRI Power Plants, OurAirports, UNESCO and national statistical yearbooks.",
        "advisor.commerce.blurb": "Middle Corridor & Silk Road freight corridors, gas pipelines, Caspian & dry ports, and major airports.",
        "advisor.commerce.callout": "Major inter-regional freight and pipeline corridors ({year} estimates in USD), plus Caspian Sea seaports, Khorgos/Dostyk dry ports and 30+ commercial airports. Regional imports {imports} and exports {exports}.",
        "advisor.commerce.ports_what": "Caspian seaports & Silk Road dry ports (tonnes)",
        "advisor.commerce.cargo_note": "Annual air cargo handled in metric tonnes.",
        "advisor.culture.blurb": "36 Silk Road landmarks, Pamir/Tian Shan parks & universities, faith traditions, and Central Asian natural disasters.",
        "advisor.culture.disasters_kicker": "EM-DAT / UNDRR 1980–2025",
        "advisor.culture.faith_kicker": "Regional composition",
        "advisor.culture.faith_regions": "Republics by religiously affiliated residents, per 100 ≈",
        "advisor.culture.park_visits_sub": "mapped national parks & reserves, {year}",
        "advisor.energy.mines_sub": "flagship gold, uranium, copper, coal & iron sites",
        "advisor.energy.oilgas_label": "Oil & gas basins",
        "advisor.energy.oilgas_sub": "supergiant & major fields",
        "advisor.military.blurb": "Armed forces, defense spending, major bases, Caspian naval commands, and Baikonur / test ranges.",
        "advisor.explorer.region_example": "e.g. UZ or KZ",
        "layers.toggle.roads": "Highways",
        "layers.toggle.rail": "Railroads",
        "layers.toggle.hubs": "Ports & airports",
        "layers.toggle.wonders": "Wonders",
        "layers.toggle.trade": "Trade routes",
        "layers.toggle.military": "Military",
        "cv.districts_counting": "Workers by industry (2025 estimates)",
        "cv.districts_note": "Districts reflect sectors where a city's workforce share exceeds 1.25× the Central Asian norm.",
    }
    write_json(OUT_DIR / "text.json", text_doc)

    # ------------------------------------------------------------------ Self-check summary
    total_bytes = sum(p.stat().st_size for p in OUT_DIR.glob("*.json"))
    print(f"=== Done! Built {len(list(OUT_DIR.glob('*.json')))} files in {OUT_DIR} ({total_bytes / 1e6:.2f} MB) ===")
    print(f"    5 Republics | {len(admin1_records)} Provinces | {len(cities_out)} Cities | {len(res_items)} Resources | {len(wonders_out)} Wonders | {len(ports_out)} Ports | {len(airports_out)} Airports | {len(routes_out)} Trade Routes | {len(mil_insts)} Bases")


if __name__ == "__main__":
    build()
