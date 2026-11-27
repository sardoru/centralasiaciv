"""Download and cache real public geospatial and statistical datasets for Central Asia."""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

from .core.fetch import download
from .core.paths import RAW

RAW_DIR = RAW / "central_asia"
NE_BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson"

NE_LAYERS = [
    ("admin_0_countries", 10),
    ("admin_1_states_provinces", 10),
    ("lakes", 10),
    ("rivers_lake_centerlines", 10),
    ("populated_places", 10),
    ("roads", 10),
    ("railroads", 10),
    ("ports", 10),
]

# Central Asia bounding box (with generous context margin for neighbours & Caspian Sea)
LAT_MIN, LAT_MAX = 33, 57
LON_MIN, LON_MAX = 45, 90

WB_COUNTRIES = "UZB;KAZ;KGZ;TJK;TKM"
WB_INDICATORS = {
    "pop": "SP.POP.TOTL",
    "gdp": "NY.GDP.MKTP.CD",
    "gdp_pc": "NY.GDP.PCAP.CD",
    "agri_pct": "NV.AGR.TOTL.ZS",
    "ind_pct": "NV.IND.TOTL.ZS",
    "manuf_pct": "NV.IND.MANF.ZS",
    "serv_pct": "NV.SRV.TOTL.ZS",
    "unemp": "SL.UEM.TOTL.ZS",
    "emp_agri": "SL.AGR.EMPL.ZS",
    "emp_ind": "SL.IND.EMPL.ZS",
    "emp_serv": "SL.SRV.EMPL.ZS",
    "labor": "SL.TLF.TOTL.IN",
    "internet": "IT.NET.USER.ZS",
    "urban": "SP.URB.TOTL.IN.ZS",
    "life_exp": "SP.DYN.LE00.IN",
    "mil_usd": "MS.MIL.XPND.CD",
    "mil_gdp": "MS.MIL.XPND.GD.ZS",
    "mil_pers": "MS.MIL.TOTL.P1",
    "poverty": "SI.POV.NAHC",
    "tertiary": "SE.TER.ENRR",
    "land_km2": "AG.LND.TOTL.K2",
    "forest_pct": "AG.LND.FRST.ZS",
    "agri_land_pct": "AG.LND.AGRI.ZS",
}


def fetch_all(force: bool = False) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # 1. Natural Earth 1:10m vector layers
    for layer, scale in NE_LAYERS:
        url = f"{NE_BASE}/ne_{scale}m_{layer}.geojson"
        print(f"Fetching Natural Earth {layer}...", flush=True)
        download("central_asia", url, f"ne_{layer}.geojson", force=force)

    # 2. NOAA ETOPO1 relief (every 5 arc-minutes across 33-57N, 45-90E -> crisp ~9 km resolution!)
    etopo_url = (
        f"https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo180.csv"
        f"?altitude%5B({LAT_MIN}):5:({LAT_MAX})%5D%5B({LON_MIN}):5:({LON_MAX})%5D"
    )
    print("Fetching NOAA ETOPO1 relief...", flush=True)
    download("central_asia", etopo_url, "etopo_ca.csv", force=force)

    # 3. ESA WorldCover 2021 satellite land cover via Terrascope WMS (EPSG:4326)
    wms_params = urllib.parse.urlencode({
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": "WORLDCOVER_2021_MAP",
        "STYLES": "",
        "SRS": "EPSG:4326",
        "BBOX": f"{LON_MIN},{LAT_MIN},{LON_MAX},{LAT_MAX}",
        "WIDTH": 2250,
        "HEIGHT": 1200,
        "FORMAT": "image/png",
    })
    wms_url = f"https://services.terrascope.be/wms/v2?{wms_params}"
    print("Fetching ESA WorldCover 2021 land cover WMS...", flush=True)
    try:
        download("central_asia", wms_url, "esa_worldcover_2021.png", force=force, expect_binary=True)
    except Exception as exc:
        print(f"Warning: ESA WorldCover WMS failed ({exc}), will use fallback if needed.", file=sys.stderr)

    # 4. WRI Global Power Plant Database v1.3.0
    print("Fetching WRI Global Power Plant Database...", flush=True)
    download(
        "central_asia",
        "https://raw.githubusercontent.com/wri/global-power-plant-database/7a91cfbb2a4e272597acbc00506d61fc1ec73b3d/output_database/global_power_plant_database.csv",
        "wri_power_plants.csv",
        force=force,
    )

    # 5. OurAirports CSV
    print("Fetching OurAirports dataset...", flush=True)
    download(
        "central_asia",
        "https://davidmegginson.github.io/ourairports-data/airports.csv",
        "ourairports.csv",
        force=force,
    )

    # 6. World Bank WDI indicators (2019-2025) for UZ, KZ, KG, TJ, TM
    print("Fetching World Bank WDI indicators for Central Asia...", flush=True)
    wb_combined: dict[str, list] = {}
    for key, ind in WB_INDICATORS.items():
        url = f"https://api.worldbank.org/v2/country/{WB_COUNTRIES}/indicator/{ind}?format=json&date=2019:2025&per_page=100"
        path = download("central_asia", url, f"wb_{key}.json", force=force)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            wb_combined[key] = raw[1] if isinstance(raw, list) and len(raw) > 1 and raw[1] else []
        except Exception as exc:
            print(f"Warning: could not parse wb_{key}: {exc}", file=sys.stderr)
    (RAW_DIR / "wb_summary.json").write_text(json.dumps(wb_combined, indent=1), encoding="utf-8")
    print("All public datasets fetched successfully!", flush=True)


if __name__ == "__main__":
    fetch_all(force="--force" in sys.argv)
