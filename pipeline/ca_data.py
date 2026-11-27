"""Authoritative Central Asia domain, demographic, economic, resource, wonder, military, and disaster data.

National totals (population, GDP, unemployment, internet, urbanization, military) are pulled live from
World Bank WDI (2024–2025) during build; sub-national oblast/viloyat and city breakdowns are anchored
to Stat.uz, Stat.gov.kz, Stat.kg, Stat.tj, UN/ADB/IMF statistical yearbooks, WRI Power Plants, and OurAirports.
"""

from __future__ import annotations

# 5 Central Asian Republics -> mapped to `states.json` (each republic gets painted territorial borders & panel)
REPUBLICS = [
    {"fips": "UZ", "iso3": "UZB", "abbr": "UZ", "name": "Uzbekistan", "capital": "Tashkent", "emblem_color": "#1eb53a"},
    {"fips": "KZ", "iso3": "KAZ", "abbr": "KZ", "name": "Kazakhstan", "capital": "Astana", "emblem_color": "#00afca"},
    {"fips": "KG", "iso3": "KGZ", "abbr": "KG", "name": "Kyrgyzstan", "capital": "Bishkek", "emblem_color": "#c8102e"},
    {"fips": "TJ", "iso3": "TJK", "abbr": "TJ", "name": "Tajikistan", "capital": "Dushanbe", "emblem_color": "#cc0000"},
    {"fips": "TM", "iso3": "TKM", "abbr": "TM", "name": "Turkmenistan", "capital": "Ashgabat", "emblem_color": "#00843d"},
]

# Normalize Natural Earth admin-1 names to current official English names
NE_ADMIN1_RENAME = {
    ("UZ", "Andijon"): "Andijan Region",
    ("UZ", "Bukhoro"): "Bukhara Region",
    ("UZ", "Ferghana"): "Fergana Region",
    ("UZ", "Jizzakh"): "Jizzakh Region",
    ("UZ", "Karakalpakstan"): "Karakalpakstan",
    ("UZ", "Kashkadarya"): "Kashkadarya Region",
    ("UZ", "Khorezm"): "Khorezm Region",
    ("UZ", "Namangan"): "Namangan Region",
    ("UZ", "Navoi"): "Navoiy Region",
    ("UZ", "Samarkand"): "Samarkand Region",
    ("UZ", "Sirdaryo"): "Syrdarya Region",
    ("UZ", "Surkhandarya"): "Surkhandarya Region",
    ("UZ", "Tashkent"): "Tashkent Region",  # smaller polygon disambiguated as Tashkent City in builder
    ("KZ", "Almaty"): "Almaty & Jetisu",
    ("KZ", "Almaty City"): "Almaty City",
    ("KZ", "Aqmola"): "Akmola Region",
    ("KZ", "Aqtöbe"): "Aktobe Region",
    ("KZ", "Astana"): "Astana City",
    ("KZ", "Atyrau"): "Atyrau Region",
    ("KZ", "East Kazakhstan"): "East Kazakhstan & Abai",
    ("KZ", "Mangghystau"): "Mangystau Region",
    ("KZ", "North Kazakhstan"): "North Kazakhstan",
    ("KZ", "Pavlodar"): "Pavlodar Region",
    ("KZ", "Qaraghandy"): "Karaganda & Ulytau",
    ("KZ", "Qostanay"): "Kostanay Region",
    ("KZ", "Qyzylorda"): "Kyzylorda Region",
    ("KZ", "South Kazakhstan"): "Turkistan & Shymkent",
    ("KZ", "West Kazakhstan"): "West Kazakhstan",
    ("KZ", "Zhambyl"): "Zhambyl Region",
    ("KG", "Batken"): "Batken Region",
    ("KG", "Bishkek"): "Bishkek City",
    ("KG", "Chuy"): "Chuy Region",
    ("KG", "Jalal-Abad"): "Jalal-Abad Region",
    ("KG", "Naryn"): "Naryn Region",
    ("KG", "Osh"): "Osh Region & City",
    ("KG", "Talas"): "Talas Region",
    ("KG", "Ysyk-Köl"): "Issyk-Kul Region",
    ("TJ", "Dushanbe"): "Dushanbe City",
    ("TJ", "Gorno-Badakhshan"): "Gorno-Badakhshan (Pamirs)",
    ("TJ", "Khatlon"): "Khatlon Region",
    ("TJ", "Leninabad"): "Sughd Region",
    ("TJ", "Tadzhikistan Territories"): "Districts of Rep. Subordination",
    ("TM", "Ahal"): "Ahal & Ashgabat",
    ("TM", "Balkan"): "Balkan Region",
    ("TM", "Chardzhou"): "Lebap Region",
    ("TM", "Mary"): "Mary Region",
    ("TM", "Tashauz"): "Dashoguz Region",
}

# Sub-national Admin-1 statistical profiles (48 regions):
# (pop_2025_k, growth_21_25, grp_pc_usd, hh_income_usd, poverty_pct, median_age, bachelors_pct,
#  broadband_pct, commute_min, homeown_pct, faith_per100, faith_tradition, hazards_count)
# faith_tradition: sunni | shia_ismaili | orthodox | mixed_secular
ADMIN1_STATS = {
    # Uzbekistan (Stat.uz 2025, total ~37.05M)
    ("UZ", "Tashkent City"):        (3110, 0.118,  8900, 15200, 0.042, 31.8, 0.34, 0.96, 32, 0.84, 86.0, "sunni", 4),
    ("UZ", "Tashkent Region"):      (3080, 0.068,  4650,  9400, 0.088, 29.4, 0.16, 0.90, 29, 0.91, 91.5, "sunni", 6),
    ("UZ", "Samarkand Region"):     (4260, 0.082,  3150,  7600, 0.105, 27.6, 0.15, 0.87, 25, 0.93, 94.0, "sunni", 5),
    ("UZ", "Fergana Region"):       (4110, 0.075,  2950,  7200, 0.112, 27.8, 0.14, 0.88, 24, 0.94, 95.5, "sunni", 7),
    ("UZ", "Andijan Region"):       (3440, 0.078,  3250,  7800, 0.108, 27.9, 0.14, 0.88, 24, 0.94, 96.0, "sunni", 8),
    ("UZ", "Namangan Region"):      (3100, 0.081,  2850,  7100, 0.118, 27.2, 0.13, 0.86, 23, 0.94, 96.2, "sunni", 7),
    ("UZ", "Kashkadarya Region"):   (3610, 0.084,  3400,  7400, 0.125, 26.8, 0.13, 0.84, 24, 0.93, 94.5, "sunni", 5),
    ("UZ", "Surkhandarya Region"):  (2920, 0.089,  2450,  6400, 0.142, 25.9, 0.12, 0.82, 23, 0.95, 95.8, "sunni", 6),
    ("UZ", "Bukhara Region"):       (2060, 0.056,  4100,  8600, 0.089, 29.1, 0.17, 0.89, 22, 0.92, 92.0, "sunni", 3),
    ("UZ", "Khorezm Region"):       (2010, 0.062,  3100,  7300, 0.115, 28.4, 0.15, 0.86, 22, 0.94, 94.2, "sunni", 4),
    ("UZ", "Karakalpakstan"):       (2020, 0.052,  2750,  6600, 0.158, 27.5, 0.14, 0.81, 23, 0.92, 90.5, "sunni", 6),
    ("UZ", "Navoiy Region"):        (1085, 0.064,  8400, 12800, 0.062, 29.8, 0.19, 0.91, 21, 0.89, 89.0, "sunni", 3),
    ("UZ", "Jizzakh Region"):       (1525, 0.074,  2900,  7100, 0.122, 27.3, 0.13, 0.85, 23, 0.93, 94.0, "sunni", 5),
    ("UZ", "Syrdarya Region"):      ( 920, 0.065,  3300,  7400, 0.128, 28.1, 0.14, 0.86, 22, 0.92, 92.5, "sunni", 5),

    # Kazakhstan (Stat.gov.kz 2025, total ~20.84M)
    ("KZ", "Almaty City"):          (2300, 0.145, 27500, 24800, 0.031, 32.6, 0.44, 0.97, 36, 0.74, 72.0, "sunni", 7),
    ("KZ", "Astana City"):          (1530, 0.215, 26800, 26200, 0.025, 30.8, 0.48, 0.98, 30, 0.71, 74.5, "sunni", 4),
    ("KZ", "Turkistan & Shymkent"): (3420, 0.095,  6400, 11800, 0.088, 25.4, 0.22, 0.90, 25, 0.88, 92.0, "sunni", 6),
    ("KZ", "Almaty & Jetisu"):      (2260, 0.065,  8800, 14600, 0.056, 29.7, 0.25, 0.92, 28, 0.87, 84.0, "sunni", 8),
    ("KZ", "Karaganda & Ulytau"):   (1360, 0.012, 16900, 18400, 0.041, 35.1, 0.31, 0.94, 24, 0.84, 68.5, "sunni", 5),
    ("KZ", "East Kazakhstan & Abai"): (1330, -0.014, 13400, 16200, 0.049, 36.4, 0.29, 0.92, 23, 0.86, 66.0, "sunni", 9),
    ("KZ", "Zhambyl Region"):       (1225, 0.048,  6900, 12200, 0.065, 27.9, 0.24, 0.91, 22, 0.89, 88.5, "sunni", 5),
    ("KZ", "Aktobe Region"):        ( 950, 0.055, 13800, 16900, 0.042, 31.4, 0.29, 0.93, 23, 0.86, 82.0, "sunni", 7),
    ("KZ", "Atyrau Region"):        ( 715, 0.072, 46500, 28500, 0.029, 29.2, 0.32, 0.95, 22, 0.85, 89.5, "sunni", 6),
    ("KZ", "Mangystau Region"):     ( 805, 0.098, 18200, 21400, 0.048, 27.6, 0.27, 0.94, 23, 0.84, 91.0, "sunni", 4),
    ("KZ", "Pavlodar Region"):      ( 755, 0.005, 15200, 17600, 0.040, 36.1, 0.30, 0.94, 22, 0.85, 64.0, "sunni", 5),
    ("KZ", "Kostanay Region"):      ( 830, -0.018, 12600, 15800, 0.044, 37.8, 0.28, 0.92, 21, 0.87, 62.5, "orthodox", 7),
    ("KZ", "Kyzylorda Region"):     ( 845, 0.044,  9100, 13600, 0.064, 27.2, 0.25, 0.91, 21, 0.89, 93.0, "sunni", 5),
    ("KZ", "Akmola Region"):        ( 790, 0.028, 11400, 15400, 0.048, 34.8, 0.28, 0.92, 24, 0.86, 67.0, "sunni", 6),
    ("KZ", "West Kazakhstan"):      ( 695, 0.036, 17800, 17400, 0.043, 33.1, 0.29, 0.93, 22, 0.86, 79.0, "sunni", 8),
    ("KZ", "North Kazakhstan"):     ( 530, -0.032, 10800, 14500, 0.058, 39.2, 0.27, 0.91, 20, 0.88, 61.0, "orthodox", 8),

    # Kyrgyzstan (Stat.kg 2025, total ~7.34M)
    ("KG", "Bishkek City"):         (1185, 0.095,  6900, 12400, 0.145, 29.8, 0.36, 0.96, 30, 0.78, 81.0, "sunni", 5),
    ("KG", "Chuy Region"):          (1080, 0.072,  3400,  7800, 0.220, 29.2, 0.19, 0.93, 26, 0.88, 84.0, "sunni", 6),
    ("KG", "Osh Region & City"):    (1870, 0.088,  2100,  5900, 0.315, 24.8, 0.16, 0.90, 24, 0.92, 95.5, "sunni", 9),
    ("KG", "Jalal-Abad Region"):    (1360, 0.076,  2350,  6200, 0.330, 25.4, 0.15, 0.89, 23, 0.93, 95.0, "sunni", 9),
    ("KG", "Issyk-Kul Region"):     ( 555, 0.052,  4900,  8900, 0.245, 28.9, 0.21, 0.92, 21, 0.91, 88.0, "sunni", 7),
    ("KG", "Batken Region"):        ( 595, 0.082,  1650,  5200, 0.355, 25.1, 0.14, 0.87, 22, 0.94, 96.5, "sunni", 8),
    ("KG", "Naryn Region"):         ( 315, 0.041,  1950,  5600, 0.340, 26.8, 0.17, 0.88, 20, 0.95, 94.0, "sunni", 7),
    ("KG", "Talas Region"):         ( 285, 0.048,  2150,  5800, 0.295, 27.4, 0.16, 0.90, 20, 0.94, 93.5, "sunni", 5),

    # Tajikistan (Stat.tj 2025, total ~10.79M)
    ("TJ", "Dushanbe City"):        (1290, 0.112,  3900,  8400, 0.115, 25.4, 0.29, 0.78, 27, 0.82, 94.0, "sunni", 6),
    ("TJ", "Sughd Region"):         (3010, 0.082,  1850,  5400, 0.195, 24.9, 0.16, 0.60, 23, 0.93, 96.5, "sunni", 7),
    ("TJ", "Khatlon Region"):       (3850, 0.096,  1180,  4200, 0.275, 22.4, 0.11, 0.48, 22, 0.95, 97.5, "sunni", 9),
    ("TJ", "Districts of Rep. Subordination"): (2380, 0.092, 1420, 4700, 0.235, 23.1, 0.13, 0.54, 24, 0.94, 97.0, "sunni", 10),
    ("TJ", "Gorno-Badakhshan (Pamirs)"): (256, 0.032, 1250, 4500, 0.285, 26.8, 0.24, 0.52, 21, 0.96, 95.0, "shia_ismaili", 12),

    # Turkmenistan (UN/ADB/World Bank 2025, total ~7.62M)
    ("TM", "Ahal & Ashgabat"):      (2110, 0.072,  8400, 12800, 0.085, 28.4, 0.23, 0.46, 25, 0.88, 90.0, "sunni", 4),
    ("TM", "Mary Region"):          (1760, 0.064,  7600, 10800, 0.110, 26.5, 0.15, 0.34, 21, 0.93, 94.0, "sunni", 3),
    ("TM", "Lebap Region"):         (1610, 0.058,  5400,  9400, 0.125, 26.9, 0.15, 0.33, 22, 0.93, 94.5, "sunni", 4),
    ("TM", "Dashoguz Region"):      (1520, 0.060,  4200,  8200, 0.148, 26.1, 0.13, 0.30, 21, 0.94, 95.0, "sunni", 4),
    ("TM", "Balkan Region"):        ( 618, 0.054,  9800, 13400, 0.088, 28.8, 0.19, 0.40, 22, 0.89, 91.0, "sunni", 4),
}

# 78 Major & Regional Cities across all 5 Central Asian republics:
# (id, name, state, region_name, lon, lat, pop_2025, growth_21_25, capital, metro,
#  specialty_profile, gdp_pc_mult, inc_mult)
# specialty_profile drives realistic industry mix, districts & city-type badges!
CITIES = [
    # --- UZBEKISTAN (22 cities) ---
    ("uz-tashkent", "Tashkent", "UZ", "Tashkent City", 69.2401, 41.2995, 3110000, 0.118, True, True, "capital_tech", 1.15, 1.12),
    ("uz-namangan", "Namangan", "UZ", "Namangan Region", 71.6726, 40.9983, 710000, 0.098, False, True, "textile_trade", 1.12, 1.08),
    ("uz-samarkand", "Samarkand", "UZ", "Samarkand Region", 66.9597, 39.6542, 605000, 0.088, False, True, "silkroad_campus", 1.32, 1.18),
    ("uz-andijan", "Andijan", "UZ", "Andijan Region", 72.3442, 40.7821, 492000, 0.082, False, True, "auto_industrial", 1.28, 1.15),
    ("uz-nukus", "Nukus", "UZ", "Karakalpakstan", 59.6103, 42.4619, 345000, 0.071, False, True, "regional_gov", 1.18, 1.10),
    ("uz-fergana", "Fergana", "UZ", "Fergana Region", 71.7864, 40.3842, 330000, 0.074, False, True, "refining_agri", 1.24, 1.14),
    ("uz-bukhara", "Bukhara", "UZ", "Bukhara Region", 64.4286, 39.7747, 302000, 0.062, False, True, "silkroad_gas", 1.28, 1.16),
    ("uz-karshi", "Karshi", "UZ", "Kashkadarya Region", 65.7891, 38.8606, 298000, 0.086, False, True, "gas_hub", 1.25, 1.12),
    ("uz-kokand", "Kokand", "UZ", "Fergana Region", 70.9425, 40.5286, 276000, 0.068, False, True, "textile_trade", 1.10, 1.06),
    ("uz-margilan", "Margilan", "UZ", "Fergana Region", 71.7246, 40.4711, 255000, 0.072, False, False, "silk_craft", 1.08, 1.05),
    ("uz-jizzakh", "Jizzakh", "UZ", "Jizzakh Region", 67.8422, 40.1158, 204000, 0.084, False, True, "auto_industrial", 1.20, 1.10),
    ("uz-termez", "Termez", "UZ", "Surkhandarya Region", 67.2783, 37.2242, 202000, 0.095, False, True, "border_garrison", 1.22, 1.12),
    ("uz-angren", "Angren", "UZ", "Tashkent Region", 70.1436, 41.0167, 198000, 0.052, False, False, "coal_industrial", 1.18, 1.08),
    ("uz-chirchiq", "Chirchiq", "UZ", "Tashkent Region", 69.5822, 41.4689, 174000, 0.064, False, False, "chem_garrison", 1.25, 1.12),
    ("uz-navoiy", "Navoiy", "UZ", "Navoiy Region", 65.3792, 40.0844, 166000, 0.078, False, True, "gold_uranium", 1.38, 1.25),
    ("uz-urgench", "Urgench", "UZ", "Khorezm Region", 60.6333, 41.5500, 158000, 0.066, False, True, "silkroad_agri", 1.18, 1.10),
    ("uz-almalyk", "Almalyk", "UZ", "Tashkent Region", 69.5983, 40.8447, 146000, 0.061, False, False, "copper_mining", 1.45, 1.22),
    ("uz-shakhrisabz", "Shakhrisabz", "UZ", "Kashkadarya Region", 66.8342, 39.0578, 148000, 0.074, False, False, "silkroad_agri", 1.05, 1.02),
    ("uz-khiva", "Khiva", "UZ", "Khorezm Region", 60.3639, 41.3783, 102000, 0.064, False, False, "silkroad_heritage", 1.12, 1.05),
    ("uz-gulistan", "Gulistan", "UZ", "Syrdarya Region", 68.7842, 40.4897, 101000, 0.070, False, False, "agri_power", 1.15, 1.06),
    ("uz-zarafshan", "Zarafshan", "UZ", "Navoiy Region", 64.2000, 41.5767, 89000, 0.058, False, False, "gold_uranium", 1.65, 1.35),
    ("uz-denov", "Denov", "UZ", "Surkhandarya Region", 67.8989, 38.2675, 118000, 0.081, False, False, "agri_trade", 1.02, 1.00),

    # --- KAZAKHSTAN (25 cities) ---
    ("kz-almaty", "Almaty", "KZ", "Almaty City", 76.8897, 43.2389, 2300000, 0.145, False, True, "finance_tech", 1.08, 1.05),
    ("kz-astana", "Astana", "KZ", "Astana City", 71.4491, 51.1605, 1530000, 0.215, True, True, "capital_gov", 1.06, 1.04),
    ("kz-shymkent", "Shymkent", "KZ", "Turkistan & Shymkent", 69.5901, 42.3417, 1265000, 0.142, False, True, "trade_industrial", 1.45, 1.24),
    ("kz-aktobe", "Aktobe", "KZ", "Aktobe Region", 57.1670, 50.2839, 582000, 0.086, False, True, "mining_oil", 1.12, 1.08),
    ("kz-karaganda", "Karaganda", "KZ", "Karaganda & Ulytau", 73.1094, 49.8047, 524000, 0.042, False, True, "coal_industrial", 1.08, 1.05),
    ("kz-taraz", "Taraz", "KZ", "Zhambyl Region", 71.3667, 42.9000, 435000, 0.068, False, True, "chem_agri", 1.18, 1.10),
    ("kz-ust-kamenogorsk", "Ust-Kamenogorsk", "KZ", "East Kazakhstan & Abai", 82.6142, 49.9483, 372000, 0.038, False, True, "metals_hydro", 1.22, 1.12),
    ("kz-pavlodar", "Pavlodar", "KZ", "Pavlodar Region", 76.9674, 52.2873, 368000, 0.025, False, True, "metals_power", 1.15, 1.08),
    ("kz-atyrau", "Atyrau", "KZ", "Atyrau Region", 51.9238, 47.0945, 338000, 0.112, False, True, "oil_capital", 1.18, 1.14),
    ("kz-semey", "Semey", "KZ", "East Kazakhstan & Abai", 80.2275, 50.4111, 332000, 0.032, False, True, "culture_campus", 0.96, 0.98),
    ("kz-kyzylorda", "Kyzylorda", "KZ", "Kyzylorda Region", 65.5092, 44.8479, 286000, 0.064, False, True, "uranium_agri", 1.12, 1.06),
    ("kz-aktau", "Aktau", "KZ", "Mangystau Region", 51.1601, 43.6500, 282000, 0.138, False, True, "caspian_port", 1.20, 1.12),
    ("kz-kostanay", "Kostanay", "KZ", "Kostanay Region", 63.6246, 53.2144, 272000, 0.045, False, True, "wheat_auto", 1.16, 1.08),
    ("kz-oral", "Oral", "KZ", "West Kazakhstan", 51.3700, 51.2333, 265000, 0.056, False, True, "gas_hub", 1.10, 1.06),
    ("kz-turkistan", "Turkistan", "KZ", "Turkistan & Shymkent", 68.2518, 43.2973, 238000, 0.165, False, True, "silkroad_heritage", 1.15, 1.08),
    ("kz-petropavl", "Petropavl", "KZ", "North Kazakhstan", 69.1500, 54.8667, 224000, 0.015, False, True, "wheat_rail", 1.12, 1.06),
    ("kz-kokshetau", "Kokshetau", "KZ", "Akmola Region", 69.3833, 53.2833, 194000, 0.068, False, False, "resort_agri", 1.10, 1.06),
    ("kz-temirtau", "Temirtau", "KZ", "Karaganda & Ulytau", 72.9646, 50.0549, 179000, -0.008, False, False, "steel_industrial", 1.18, 1.08),
    ("kz-taldykorgan", "Taldykorgan", "KZ", "Almaty & Jetisu", 78.3739, 45.0156, 172000, 0.062, False, False, "agri_trade", 1.08, 1.04),
    ("kz-ekibastuz", "Ekibastuz", "KZ", "Pavlodar Region", 75.3228, 51.7237, 134000, -0.005, False, False, "coal_power", 1.30, 1.12),
    ("kz-zhanaozen", "Zhanaozen", "KZ", "Mangystau Region", 52.8619, 43.3412, 152000, 0.095, False, False, "oil_capital", 1.15, 1.10),
    ("kz-rudny", "Rudny", "KZ", "Kostanay Region", 63.1200, 52.9729, 114000, -0.010, False, False, "iron_mining", 1.32, 1.14),
    ("kz-zhezkazgan", "Zhezkazgan", "KZ", "Karaganda & Ulytau", 67.7144, 47.7833, 92000, 0.028, False, False, "copper_mining", 1.28, 1.12),
    ("kz-balkhash", "Balkhash", "KZ", "Karaganda & Ulytau", 74.9950, 46.8481, 79000, 0.004, False, False, "copper_mining", 1.26, 1.10),
    ("kz-baikonur", "Baikonur", "KZ", "Kyzylorda Region", 63.3140, 45.6232, 58000, -0.025, False, False, "spaceport", 1.48, 1.25),

    # --- KYRGYZSTAN (10 cities) ---
    ("kg-bishkek", "Bishkek", "KG", "Bishkek City", 74.5698, 42.8746, 1185000, 0.095, True, True, "capital_tech", 1.12, 1.08),
    ("kg-osh", "Osh", "KG", "Osh Region & City", 72.7985, 40.5283, 375000, 0.108, False, True, "silkroad_trade", 1.35, 1.18),
    ("kg-jalal-abad", "Jalal-Abad", "KG", "Jalal-Abad Region", 73.0000, 40.9333, 132000, 0.084, False, True, "hydro_agri", 1.15, 1.08),
    ("kg-karakol", "Karakol", "KG", "Issyk-Kul Region", 78.3936, 42.4907, 88000, 0.062, False, False, "mountain_resort", 1.12, 1.06),
    ("kg-tokmok", "Tokmok", "KG", "Chuy Region", 75.3015, 42.8419, 76000, 0.058, False, False, "agri_industrial", 1.08, 1.04),
    ("kg-uzgen", "Uzgen", "KG", "Osh Region & City", 73.3007, 40.7699, 66000, 0.074, False, False, "silkroad_agri", 1.04, 1.00),
    ("kg-balykchy", "Balykchy", "KG", "Issyk-Kul Region", 76.1871, 42.4602, 55000, 0.054, False, False, "rail_resort", 1.06, 1.02),
    ("kg-naryn", "Naryn", "KG", "Naryn Region", 75.9911, 41.4287, 44000, 0.048, False, False, "alpine_campus", 1.10, 1.04),
    ("kg-talas", "Talas", "KG", "Talas Region", 72.2427, 42.5228, 43000, 0.052, False, False, "agri_trade", 1.05, 1.02),
    ("kg-batken", "Batken", "KG", "Batken Region", 70.8194, 40.0626, 36000, 0.078, False, False, "border_agri", 1.08, 1.02),

    # --- TAJIKISTAN (10 cities) ---
    ("tj-dushanbe", "Dushanbe", "TJ", "Dushanbe City", 68.7870, 38.5598, 1290000, 0.112, True, True, "capital_gov", 1.12, 1.08),
    ("tj-khujand", "Khujand", "TJ", "Sughd Region", 69.6222, 40.2826, 208000, 0.078, False, True, "silkroad_industrial", 1.38, 1.22),
    ("tj-bokhtar", "Bokhtar", "TJ", "Khatlon Region", 68.7800, 37.8364, 134000, 0.095, False, True, "agri_trade", 1.22, 1.12),
    ("tj-kulob", "Kulob", "TJ", "Khatlon Region", 69.7845, 37.9146, 114000, 0.082, False, False, "agri_culture", 1.12, 1.06),
    ("tj-istaravshan", "Istaravshan", "TJ", "Sughd Region", 69.0033, 39.9142, 72000, 0.076, False, False, "silk_craft", 1.06, 1.02),
    ("tj-tursunzoda", "Tursunzoda", "TJ", "Districts of Rep. Subordination", 68.2300, 38.5127, 64000, 0.072, False, False, "metals_hydro", 1.48, 1.20),
    ("tj-vahdat", "Vahdat", "TJ", "Districts of Rep. Subordination", 69.0135, 38.5563, 58000, 0.088, False, False, "agri_industrial", 1.12, 1.05),
    ("tj-panjakent", "Panjakent", "TJ", "Sughd Region", 67.6093, 39.4952, 52000, 0.074, False, False, "silkroad_mining", 1.18, 1.08),
    ("tj-nurek", "Nurek", "TJ", "Khatlon Region", 69.3227, 38.3892, 36000, 0.068, False, False, "hydro_power", 1.55, 1.22),
    ("tj-khorog", "Khorog", "TJ", "Gorno-Badakhshan (Pamirs)", 71.5530, 37.4897, 33000, 0.044, False, False, "alpine_campus", 1.28, 1.15),

    # --- TURKMENISTAN (9 cities) ---
    ("tm-ashgabat", "Ashgabat", "TM", "Ahal & Ashgabat", 58.3261, 37.9601, 1085000, 0.088, True, True, "capital_gov", 1.22, 1.15),
    ("tm-turkmenabat", "Turkmenabat", "TM", "Lebap Region", 63.5786, 39.0733, 275000, 0.062, False, True, "gas_rail", 1.18, 1.10),
    ("tm-dashoguz", "Dashoguz", "TM", "Dashoguz Region", 59.9666, 41.8363, 245000, 0.065, False, True, "agri_trade", 1.14, 1.08),
    ("tm-mary", "Mary", "TM", "Mary Region", 61.8303, 37.5938, 172000, 0.072, False, True, "gas_power", 1.28, 1.15),
    ("tm-balkanabat", "Balkanabat", "TM", "Balkan Region", 54.3671, 39.5108, 128000, 0.058, False, True, "oil_capital", 1.25, 1.14),
    ("tm-turkmenbashi", "Turkmenbashi", "TM", "Balkan Region", 52.9552, 40.0222, 96000, 0.064, False, True, "caspian_port", 1.32, 1.16),
    ("tm-bayramaly", "Bayramaly", "TM", "Mary Region", 62.1672, 37.6185, 94000, 0.056, False, False, "silkroad_agri", 1.08, 1.04),
    ("tm-tejen", "Tejen", "TM", "Ahal & Ashgabat", 60.5054, 37.3834, 82000, 0.052, False, False, "agri_trade", 1.04, 1.02),
    ("tm-kerki", "Kerki", "TM", "Lebap Region", 65.2006, 37.8360, 48000, 0.058, False, False, "gas_rail", 1.10, 1.04),
]

# Strategic Mines, Oil & Gas Fields, and Major New Power Plants (supplementing WRI Power Plants)
# (type, name, state, lon, lat, value, detail)
EXTRA_RESOURCES = [
    # Major recently commissioned power plants not in 2018 WRI v1.3.0
    ("hydro", "Rogun Hydropower Project", "TJ", 69.776, 38.685, 3600, "Under phased commissioning (Units 1–2 online; 3,600 MW planned), Vakhsh River"),
    ("gas_plant", "Syrdarya 1,500 MW CCGT", "UZ", 68.678, 40.228, 1500, "ACWA Power modern combined-cycle gas plant, Syrdarya"),
    ("gas_plant", "Talimarjan CCGT Expansion", "UZ", 65.565, 38.496, 1700, "Combined-cycle natural gas power complex, Kashkadarya"),
    ("wind", "Zarafshan 500 MW Wind Farm", "UZ", 64.550, 41.480, 500, "Masdar utility-scale wind farm, Navoiy desert"),
    ("solar", "Nur Navoi & Sherabad Solar", "UZ", 65.250, 40.150, 457, "Utility-scale solar PV complex, Navoiy"),
    ("solar", "Samarkand & Jizzakh Solar", "UZ", 66.520, 39.780, 440, "Masdar solar PV complexes, Samarkand"),
    ("solar", "Nukus & Bukhara Solar", "UZ", 64.220, 39.550, 500, "ACWA Power solar + storage complex, Bukhara"),
    ("wind", "Zhanatas & Shelek Wind Corridor", "KZ", 69.750, 43.580, 260, "Southern Kazakhstan utility-scale wind farms"),
    ("wind", "Badamsha & Astana Wind Farms", "KZ", 58.280, 50.560, 200, "Steppe wind power cluster, Aktobe & Akmola"),
    ("hydro", "Kambaratinskaya HPP-2", "KG", 73.320, 41.765, 120, "Naryn River cascade hydro plant, Jalal-Abad"),

    # Flagship Gold, Copper, Uranium, Iron, Chromite & Coal Mines
    ("gold", "Muruntau Gold Mine", "UZ", 64.571, 41.498, 65, "World's largest open-pit gold mine (NMMC), Kyzylkum Desert"),
    ("copper", "Almalyk / Kalmakyr & Yoshlik", "UZ", 69.644, 40.822, 148, "Major copper-gold-molybdenum porphyry complex (AGMK)"),
    ("uranium", "Uchkuduk & Zafarabad Uranium", "UZ", 63.555, 42.156, 3800, "Navoiyuran in-situ leach uranium mining belt, Kyzylkum"),
    ("coal_mine", "Angren Coal Basin", "UZ", 70.185, 41.010, 4900, "Uzbekistan's primary lignite open-pit coal basin"),
    ("gold", "Kumtor Gold Mine", "KG", 78.198, 41.862, 14, "High-altitude Tian Shan gold mine (4,000 m), Issyk-Kul"),
    ("gold", "Jerooy & Taldy-Bulak Gold", "KG", 72.710, 42.445, 5, "Gold mining operations, Talas & Chuy"),
    ("gold", "Taror & Jilau Gold Complex", "TJ", 67.855, 39.420, 6, "Zeravshan Gold Company mines, Panjakent"),
    ("lead_zinc", "Anzob Antimony & Zarnisor", "TJ", 68.870, 39.210, 45, "Antimony, mercury & lead-zinc deposits, Sughd"),

    ("uranium", "Inkai & Budenovskoye Uranium", "KZ", 67.550, 45.220, 12500, "Chu-Sarysu basin — world's #1 uranium-producing district (Kazatomprom)"),
    ("uranium", "Tortkuduk & Moynkum Uranium", "KZ", 68.020, 44.620, 5200, "KATCO / Kazatomprom in-situ recovery uranium operations"),
    ("uranium", "Khorasan & Karamurun Uranium", "KZ", 66.810, 44.080, 3400, "Syr Darya basin uranium cluster, Kyzylorda"),
    ("coal_mine", "Bogatyr & Severny Coal", "KZ", 75.460, 51.705, 42000, "One of the world's largest open-pit coal mines, Ekibastuz"),
    ("coal_mine", "Shubarkol & Karaganda Coal", "KZ", 70.820, 48.880, 22000, "Coking and thermal coal mining hub, Karaganda/Ulytau"),
    ("copper", "Aktogay Copper Mine", "KZ", 79.995, 46.972, 230, "KAZ Minerals open-pit copper sulphide & oxide mine, Abai"),
    ("copper", "Bozshakol Copper Mine", "KZ", 74.260, 51.835, 115, "Large open-pit copper-gold mine, Pavlodar"),
    ("copper", "Zhezkazgan Copper Belt", "KZ", 67.740, 47.820, 180, "Kazakhmys historic sandstone copper district, Ulytau"),
    ("copper", "Kounrad & Sayak Copper", "KZ", 75.010, 46.995, 85, "Lake Balkhash copper mining & smelting complex"),
    ("gold", "Vasilkovskoye (Altyntau Kokshetau)", "KZ", 69.210, 53.395, 16, "Kazakhstan's largest single gold mine, Akmola"),
    ("gold", "Bakyrchik (Kyzyl) Gold Mine", "KZ", 81.550, 49.705, 12, "Refractory gold deposit, Abai Region"),
    ("iron", "Sokolov-Sarbay (SSGPO) Iron Ore", "KZ", 63.105, 52.980, 28000, "Major magnetite iron ore pellets & concentrate complex, Rudny"),
    ("iron", "Kachary & Lisakovsk Iron Ore", "KZ", 62.550, 52.560, 14000, "Kostanay iron ore mining belt"),
    ("molybdenum", "Donskoy Chromite (Khromtau)", "KZ", 58.440, 50.250, 4800, "World's largest chromite ore reserve (Kazchrome), Aktobe"),
    ("lead_zinc", "Maleevsky & Ridder Polymetallic", "KZ", 83.510, 50.350, 210, "Kazzinc zinc-lead-silver-gold mines, Altai / East Kazakhstan"),
    ("rare_earths", "Karabogazgol Mineral Basin", "TM", 53.650, 41.050, 600, "World's largest natural mirabilite & sodium sulfate evaporite lagoon"),

    # Supergiant Oil & Gas Fields
    ("oil", "Tengiz Supergiant Oil Field", "KZ", 53.400, 46.150, 28000, "One of the world's deepest supergiant oil fields (~600k bbl/d), Atyrau"),
    ("oil", "Kashagan Offshore Oil Field", "KZ", 51.620, 46.200, 18000, "North Caspian offshore supergiant oil & gas complex (NCOC)"),
    ("oil", "Uzen & Kalamkas Oil Fields", "KZ", 52.920, 43.380, 12000, "Mangystau Peninsula onshore oil producing basin"),
    ("oil", "Zhanazhol & Kenkiyak Oil", "KZ", 57.320, 48.350, 8500, "Pre-Caspian eastern flank oil & gas fields, Aktobe"),
    ("oil", "Kumkol Oil Field", "KZ", 65.580, 46.420, 6200, "South Turgay basin oil producing hub, Kyzylorda"),
    ("gas", "Karachaganak Gas-Condensate Field", "KZ", 53.330, 51.250, 15000, "Supergiant gas & condensate field, West Kazakhstan"),
    ("gas", "Galkynysh Supergiant Gas Field", "TM", 62.520, 37.250, 45000, "World's second-largest natural gas field, Mary Region"),
    ("gas", "Dauletabad & Bagtyyarlyk Gas", "TM", 61.350, 36.450, 18000, "Major Amu Darya & Murgab natural gas production zones"),
    ("oil", "Cheleken & Nebitdag Oil Fields", "TM", 53.350, 39.420, 9000, "West Turkmenistan Caspian oil & gas basin, Balkan"),
    ("gas", "Shurtan & Kandym Gas Complex", "UZ", 65.720, 38.520, 22000, "Major gas extraction, processing & GTL hub, Kashkadarya & Bukhara"),
    ("gas", "Gazli & Mubarek Gas Basin", "UZ", 63.450, 40.130, 19000, "Historic Bukhara-Khiva natural gas & underground storage hub"),
    ("gas", "Surgil / Ustyurt Gas-Chemical", "UZ", 58.250, 44.320, 11000, "Ustyurt Plateau gas field & polymer complex, Karakalpakstan"),
]

# 36 Central Asian Wonders across the 4 published rules
# (id, name, short, kind, rule, state, lon, lat, motif, metric_val, area_or_extra, desc)
WONDERS = [
    # --- Rule 1: National Parks & Biosphere Reserves (12) ---
    ("ca-park-burabay", "Burabay National Park", "Burabay", "natural", "national_park", "KZ", 70.300, 53.085, "forest", 1320000, 1299, "Granite peaks, pine forests & alpine lakes in northern Kazakhstan"),
    ("ca-park-ile-alatau", "Ile-Alatau National Park", "Ile-Alatau", "natural", "national_park", "KZ", 77.050, 43.050, "peak", 960000, 1997, "Glaciated Trans-Ili Alatau range rising directly above Almaty"),
    ("ca-park-ugam-chatkal", "Ugam-Chatkal National Park", "Ugam-Chatkal", "natural", "national_park", "UZ", 70.050, 41.580, "peak", 890000, 5746, "Western Tian Shan peaks, Chimgan & Charvak mountain biosphere"),
    ("ca-park-issyk-kul", "Issyk-Kul Biosphere Reserve", "Issyk-Kul", "coastal", "national_park", "KG", 77.250, 42.450, "coast", 840000, 6236, "World's second-largest alpine salt lake ringed by snow-capped Tian Shan"),
    ("ca-park-kolsai", "Kolsai Lakes & Kaindy Park", "Kolsai Lakes", "natural", "national_park", "KZ", 78.324, 42.938, "peak", 460000, 1610, "Three emerald alpine glacial lakes & sunken spruce forest"),
    ("ca-park-ala-archa", "Ala-Archa National Park", "Ala-Archa", "natural", "national_park", "KG", 74.482, 42.565, "peak", 410000, 220, "Glacial alpine gorge in the Kyrgyz Ala-Too range south of Bishkek"),
    ("ca-park-zaamin", "Zaamin National Park", "Zaamin", "natural", "national_park", "UZ", 68.480, 39.660, "forest", 340000, 241, "Ancient juniper forests of the Turkestan Range ('Uzbek Switzerland')"),
    ("ca-park-charyn", "Charyn Canyon National Park", "Charyn Canyon", "natural", "national_park", "KZ", 79.078, 43.352, "canyon", 285000, 1270, "Red sandstone Valley of Castles carved by the Charyn River"),
    ("ca-park-altyn-emel", "Altyn-Emel National Park", "Altyn-Emel", "natural", "national_park", "KZ", 78.730, 43.900, "desert", 145000, 3076, "Singing Barkhan Dune & Aktau painted chalk mountains"),
    ("ca-park-katon-karagay", "Katon-Karagay National Park", "Katon-Karagay", "natural", "national_park", "KZ", 85.850, 49.250, "peak", 112000, 6435, "Kazakhstan's largest national park bordering Belukha in the Altai"),
    ("ca-park-sary-chelek", "Sary-Chelek Biosphere Reserve", "Sary-Chelek", "natural", "national_park", "KG", 71.950, 41.880, "forest", 88000, 239, "Deep mountain lake surrounded by ancient wild walnut forests"),
    ("ca-park-pamir", "Tajik National Park (Pamirs)", "Pamir National Park", "natural", "national_park", "TJ", 72.800, 38.750, "peak", 62000, 26117, "UNESCO World Heritage: 7,495 m Ismoil Somoni Peak & Fedchenko Glacier"),

    # --- Rule 2: Other Iconic Natural & Geological Monuments (4) ---
    ("ca-unit-darvaza", "Darvaza Gas Crater", "Darvaza Crater", "natural", "park_unit", "TM", 58.439, 40.252, "geyser", 45000, 12, "Burning natural gas crater glowing in the heart of the Karakum Desert"),
    ("ca-unit-songkol", "Song-Köl Alpine Reserve", "Song-Köl", "coastal", "park_unit", "KG", 75.130, 41.840, "coast", 54000, 270, "3,016 m high-altitude nomadic summer jailoo lake in Naryn"),
    ("ca-unit-tigrovaya", "Tigrovaya Balka Reserve", "Tigrovaya Balka", "natural", "park_unit", "TJ", 68.420, 37.260, "forest", 28000, 497, "UNESCO World Heritage tugay riverine forest at the Vakhsh–Panj confluence"),
    ("ca-unit-repetek", "Repetek Biosphere Reserve", "Repetek", "natural", "park_unit", "TM", 63.180, 38.560, "desert", 18000, 346, "Classic sand-dune saxaul desert biosphere reserve in the Eastern Karakum"),

    # --- Rule 3: Leading Research Universities (10) ---
    ("ca-uni-kaznu", "Al-Farabi Kazakh National University", "Al-Farabi KazNU", "university", "research_university", "KZ", 76.922, 43.224, "hall", 42000000, 26500, "Kazakhstan's flagship research university (QS top 200), Almaty"),
    ("ca-uni-nu", "Nazarbayev University", "Nazarbayev Univ.", "university", "research_university", "KZ", 71.398, 51.091, "spire", 68000000, 7400, "Autonomous English-language STEM & research university, Astana"),
    ("ca-uni-nuuz", "National University of Uzbekistan", "NUUz Tashkent", "university", "research_university", "UZ", 69.205, 41.348, "hall", 28000000, 32000, "Central Asia's oldest university (est. 1918), mathematics & sciences"),
    ("ca-uni-satbayev", "Satbayev University", "Satbayev Univ.", "university", "research_university", "KZ", 76.931, 43.237, "redhall", 31000000, 17200, "Premier mining, geology, metallurgy & engineering university, Almaty"),
    ("ca-uni-enu", "L.N. Gumilyov Eurasian National Univ.", "Gumilyov ENU", "university", "research_university", "KZ", 71.464, 51.160, "hall", 26000000, 23000, "Major multidisciplinary research university, Astana"),
    ("ca-uni-tstu", "Tashkent State Technical University", "Tashkent Tech", "university", "research_university", "UZ", 69.206, 41.353, "redhall", 21000000, 28500, "Flagship energy, aviation, mining & engineering university, Tashkent"),
    ("ca-uni-samsu", "Samarkand State University", "Samarkand State", "university", "research_university", "UZ", 66.963, 39.649, "spire", 19000000, 24000, "Historic Silk Road center of scholarship tracing to Ulugh Beg's Madrasa"),
    ("ca-uni-auca", "American Univ. of Central Asia / KNU", "AUCA & KNU", "university", "research_university", "KG", 74.630, 42.845, "spire", 14000000, 18500, "Leading liberal arts & national research hub, Bishkek"),
    ("ca-uni-tnu", "Tajik National University", "Tajik National", "university", "research_university", "TJ", 68.795, 38.573, "hall", 11000000, 25000, "Flagship research & humanities university of Tajikistan, Dushanbe"),
    ("ca-uni-tsu", "Magtymguly Turkmen State University", "Magtymguly TSU", "university", "research_university", "TM", 58.380, 37.935, "hall", 10000000, 11000, "Premier national university of Turkmenistan, Ashgabat"),

    # --- Rule 4: UNESCO Silk Road & Modern Landmarks (12) ---
    ("ca-lm-registan", "Registan Square & Samarkand", "Registan Square", "landmark", "landmark", "UZ", 66.975, 39.655, "rotunda", 2400000, "UNESCO 2001", "Timurid turquoise-tiled ensemble of Ulugh Beg, Sher-Dor & Tilya-Kori Madrasas"),
    ("ca-lm-bukhara", "Historic Centre of Bukhara", "Bukhara Old City", "landmark", "landmark", "UZ", 64.415, 39.776, "obelisk", 1650000, "UNESCO 1993", "Po-i-Kalyan Minaret, Ark Citadel & 2,000 years of Silk Road urban fabric"),
    ("ca-lm-khiva", "Itchan Kala (Khiva)", "Itchan Kala", "landmark", "landmark", "UZ", 60.359, 41.378, "adobe", 920000, "UNESCO 1990", "Intact walled inner oasis city of the Khiva Khanate in Khorezm"),
    ("ca-lm-yasawi", "Mausoleum of Khoja Ahmed Yasawi", "Yasawi Mausoleum", "landmark", "landmark", "KZ", 68.271, 43.298, "rotunda", 1480000, "UNESCO 2003", "Monumental Timurid turquoise-domed shrine in Turkistan"),
    ("ca-lm-baikonur", "Baikonur Cosmodrome", "Baikonur Cosmodrome", "landmark", "landmark", "KZ", 63.342, 45.965, "gantry", 120000, "Est. 1955", "World's first & largest operational space launch facility (Sputnik & Gagarin)"),
    ("ca-lm-merv", "State Historical Park Ancient Merv", "Ancient Merv", "landmark", "landmark", "TM", 62.185, 37.661, "adobe", 180000, "UNESCO 1999", "Oldest & best-preserved Silk Road oasis-city; Seljuk capital of Sultan Sanjar"),
    ("ca-lm-kunya", "Kunya-Urgench", "Kunya-Urgench", "landmark", "landmark", "TM", 59.155, 42.320, "obelisk", 110000, "UNESCO 2005", "Medieval Khwarezm capital with Central Asia's tallest ancient brick minaret"),
    ("ca-lm-sulaiman", "Sulaiman-Too Sacred Mountain", "Sulaiman-Too", "landmark", "landmark", "KG", 72.782, 40.531, "carved", 420000, "UNESCO 2009", "Five-peaked sacred limestone beacon overlooking the Fergana Valley in Osh"),
    ("ca-lm-tamgaly", "Petroglyphs of Tamgaly", "Tamgaly", "landmark", "landmark", "KZ", 75.534, 43.803, "carved", 95000, "UNESCO 2004", "5,000 Bronze Age sun-headed deity rock carvings in the Chu-Ili steppe"),
    ("ca-lm-burana", "Burana Tower (Balasagun)", "Burana Tower", "landmark", "landmark", "KG", 75.250, 42.746, "obelisk", 210000, "UNESCO 2014", "11th-century Karakhanid brick minaret & balbal stone garden in Chuy Valley"),
    ("ca-lm-sarazm", "Proto-Urban Site of Sarazm", "Sarazm", "landmark", "landmark", "TJ", 67.456, 39.514, "mound", 78000, "UNESCO 2010", "5,500-year-old Bronze Age metallurgical & trade settlement on the Zeravshan"),
    ("ca-lm-shakhrisabz", "Historic Centre of Shakhrisabz", "Shakhrisabz", "landmark", "landmark", "UZ", 66.828, 39.060, "arch", 520000, "UNESCO 2000", "Monumental Ak-Saray Palace portal & birthplace of Amir Timur"),
]

# Real Caspian Sea Ports, Major Dry Ports & River Ports
# (id, name, state, ptype, lon, lat, tons_2024, domestic, foreign)
PORTS = [
    ("ca-port-aktau", "Port of Aktau (Caspian Sea)", "KZ", "coastal", 51.219, 43.606, 4650000, 350000, 4300000),
    ("ca-port-kuryk", "Port of Kuryk Ferry Terminal", "KZ", "coastal", 51.630, 43.165, 2250000, 120000, 2130000),
    ("ca-port-turkmenbashi", "Turkmenbashi International Seaport", "TM", "coastal", 52.976, 40.005, 5800000, 600000, 5200000),
    ("ca-port-khorgos", "Khorgos Gateway Dry Port (Middle Corridor)", "KZ", "inland", 80.388, 44.172, 11800000, 900000, 10900000),
    ("ca-port-dostyk", "Dostyk–Alashankou Rail Dry Port", "KZ", "inland", 82.482, 45.253, 14200000, 1100000, 13100000),
    ("ca-port-termez", "Termez Amu Darya River & Dry Port", "UZ", "inland", 67.255, 37.202, 1450000, 250000, 1200000),
    ("ca-port-bautino", "Port of Bautino Offshore Base", "KZ", "coastal", 50.250, 44.550, 820000, 480000, 340000),
]

# Major Central Asian commercial airports with 2024-2025 passenger boardings & cargo tonnes
# (iata, city_short, enplanements_2025, enplanements_prev, cargo_t)
AIRPORT_TRAFFIC = {
    "ALA": ("Almaty", 11400000, 9520000, 118000),
    "TAS": ("Tashkent", 8700000, 7100000, 78000),
    "NQZ": ("Astana", 8300000, 7500000, 42000),
    "BSZ": ("Bishkek", 3450000, 3100000, 24000),
    "FRU": ("Bishkek", 3450000, 3100000, 24000),
    "CIT": ("Shymkent", 3150000, 2780000, 14000),
    "DYU": ("Dushanbe", 2350000, 2050000, 11000),
    "ASB": ("Ashgabat", 2150000, 1920000, 38000),
    "OSS": ("Osh", 2100000, 1950000, 4800),
    "SKD": ("Samarkand", 1420000, 1010000, 6200),
    "SCO": ("Aktau", 1380000, 1260000, 8400),
    "GUW": ("Atyrau", 1040000, 960000, 5200),
    "AKX": ("Aktobe", 980000, 890000, 4100),
    "LBD": ("Khujand", 940000, 840000, 2400),
    "UGC": ("Urgench", 720000, 590000, 1800),
    "BHK": ("Bukhara", 680000, 540000, 1500),
    "UKK": ("Ust-Kamenogorsk", 650000, 590000, 2200),
    "KGF": ("Karaganda", 540000, 490000, 19500),
    "FEG": ("Fergana", 520000, 430000, 1600),
    "NMA": ("Namangan", 490000, 410000, 1400),
    "URA": ("Oral", 460000, 410000, 1200),
    "KZO": ("Kyzylorda", 430000, 380000, 950),
    "KSN": ("Kostanay", 410000, 360000, 1100),
    "HSA": ("Turkistan", 390000, 340000, 900),
    "PWQ": ("Pavlodar", 340000, 310000, 800),
    "KRW": ("Turkmenbashi", 320000, 290000, 4500),
    "NVI": ("Navoiy", 280000, 240000, 46000),  # Major Silk Road air cargo hub!
    "TMJ": ("Termez", 240000, 195000, 1200),
    "PLX": ("Semey", 210000, 185000, 600),
    "CRZ": ("Turkmenabat", 220000, 195000, 1400),
    "TJU": ("Kulob", 210000, 185000, 400),
    "DMB": ("Taraz", 195000, 170000, 500),
    "PPK": ("Petropavl", 165000, 145000, 400),
}

# Military installations & restricted test/space ranges (public open-source locations)
# (id, name, state, component, tier, flagship, area_km2, lon, lat, city_id)
MILITARY_BASES = [
    ("ca-mil-chirchiq", "Chirchiq Garrison & Higher Tank Command", "UZ", "army", "major", True, 185.0, 69.590, 41.485, "uz-chirchiq"),
    ("ca-mil-k2", "Karshi-Khanabad Air Base", "UZ", "air_force", "major", True, 145.0, 65.922, 38.834, "uz-karshi"),
    ("ca-mil-termez", "Termez Southern Operational Command", "UZ", "army", "major", True, 240.0, 67.310, 37.275, "uz-termez"),
    ("ca-mil-fergana", "Eastern Military District (Fergana)", "UZ", "army", "base", False, 68.0, 71.750, 40.370, "uz-fergana"),
    ("ca-mil-nukus", "Northwestern Military District (Nukus)", "UZ", "army", "base", False, 82.0, 59.650, 42.490, "uz-nukus"),
    ("ca-mil-kattakurgan", "Kattakurgan Combined-Arms Training Ground", "UZ", "army", "major", False, 320.0, 66.220, 39.820, "uz-samarkand"),
    ("ca-mil-tashkent-hq", "Tashkent Defense Ministry & Air Defense", "UZ", "other", "major", True, 45.0, 69.310, 41.320, "uz-tashkent"),

    ("ca-mil-almaty-air", "Zhetigen / Almaty Air Force Base", "KZ", "air_force", "major", True, 160.0, 77.110, 43.680, "kz-almaty"),
    ("ca-mil-astana-hq", "Astana National Defense Command", "KZ", "other", "major", True, 52.0, 71.420, 51.130, "kz-astana"),
    ("ca-mil-aktau-navy", "Aktau Caspian Naval Base", "KZ", "navy", "major", True, 48.0, 51.190, 43.620, "kz-aktau"),
    ("ca-mil-otar", "Gvardeysky (Otar) 40th Military Base", "KZ", "army", "major", True, 460.0, 75.230, 43.550, "kz-taraz"),
    ("ca-mil-karaganda-air", "Karaganda 610th Air Base", "KZ", "air_force", "major", False, 130.0, 73.320, 49.680, "kz-karaganda"),
    ("ca-mil-shymkent-air", "Shymkent 602nd Air Base", "KZ", "air_force", "base", False, 84.0, 69.480, 42.365, "kz-shymkent"),
    ("ca-mil-taldykorgan-air", "Taldykorgan 604th Air Base", "KZ", "air_force", "base", False, 92.0, 78.440, 45.120, "kz-taldykorgan"),
    ("ca-mil-semey-east", "Regional Command East (Semey)", "KZ", "army", "base", False, 95.0, 80.260, 50.430, "kz-semey"),
    ("ca-mil-aktobe-west", "Aktobe Air Defense & Aviation Institute", "KZ", "air_force", "base", False, 65.0, 57.210, 50.250, "kz-aktobe"),
    ("ca-mil-baikonur-space", "Baikonur Space Launch & Telemetry Complex", "KZ", "air_force", "major", True, 6717.0, 63.342, 45.965, "kz-baikonur"),

    ("ca-mil-kant", "Kant Air Base (CSTO Joint Aviation)", "KG", "air_force", "major", True, 58.0, 74.847, 42.853, "kg-bishkek"),
    ("ca-mil-osh", "Southern Group of Forces (Osh)", "KG", "army", "base", False, 42.0, 72.820, 40.550, "kg-osh"),
    ("ca-mil-balykchy", "Edelweiss Mountain Training Center", "KG", "army", "base", False, 88.0, 76.220, 42.440, "kg-balykchy"),

    ("ca-mil-dushanbe", "Dushanbe Garrison & Ayni Air Base", "TJ", "air_force", "major", True, 75.0, 68.672, 38.513, "tj-dushanbe"),
    ("ca-mil-bokhtar", "Khatlon Border & Mechanized Garrison", "TJ", "army", "base", False, 62.0, 68.810, 37.820, "tj-bokhtar"),

    ("ca-mil-mary-air", "Mary-2 Air Base", "TM", "air_force", "major", True, 155.0, 61.900, 37.620, "tm-mary"),
    ("ca-mil-turkmenbashi-navy", "Turkmenbashi Caspian Naval Base", "TM", "navy", "major", True, 64.0, 53.010, 40.015, "tm-turkmenbashi"),
    ("ca-mil-ashgabat-hq", "Ashgabat Garrison & Defense Command", "TM", "army", "major", True, 90.0, 58.410, 37.940, "tm-ashgabat"),
    ("ca-mil-serhetabat", "Serhetabat Southern Border Garrison", "TM", "army", "base", False, 54.0, 62.340, 35.280, None),
]

# Large restricted ground / test & space ranges (drawn as hatched restricted hex zones)
# (id, name, state, component, area_km2, lon, lat, radius_km, inst_id)
MILITARY_RANGES = [
    ("ca-rng-baikonur", "Baikonur Cosmodrome Excluded Zone", "KZ", "air_force", 6717.0, 63.34, 45.96, 52, "ca-mil-baikonur-space"),
    ("ca-rng-sary-shagan", "Sary Shagan Anti-Ballistic Test Range", "KZ", "air_force", 8120.0, 72.85, 46.38, 65, None),
    ("ca-rng-semipalatinsk", "Semipalatinsk Former Nuclear Test Polygon", "KZ", "other", 18300.0, 78.40, 50.10, 78, None),
    ("ca-rng-embi", "Emba Steppe Missile & Artillery Range", "KZ", "army", 4200.0, 58.15, 48.80, 44, None),
    ("ca-rng-kattakurgan", "Kattakurgan Combined-Arms Range", "UZ", "army", 1450.0, 66.22, 39.82, 26, "ca-mil-kattakurgan"),
]

# Major Central Asian inter-republic & corridor freight/pipeline flows (2024 estimates, MUSD, k tonnes)
# (zone_a, zone_b, value_musd, tons_k, modes_dict, top_commodity)
TRADE_CORRIDORS = [
    ("almaty", "astana", 14800, 18500, {"rail": 0.56, "truck": 0.36, "air": 0.08}, "43"),
    ("tashkent", "almaty", 9600, 11200, {"rail": 0.48, "truck": 0.46, "air": 0.06}, "35"),
    ("atyrau", "aktau", 18400, 34000, {"pipeline": 0.78, "rail": 0.16, "truck": 0.06}, "17"),
    ("mary", "bukhara", 11200, 26500, {"pipeline": 0.92, "rail": 0.06, "truck": 0.02}, "19"),
    ("bukhara", "shymkent", 10400, 24800, {"pipeline": 0.86, "rail": 0.10, "truck": 0.04}, "19"),
    ("shymkent", "almaty", 12100, 19200, {"pipeline": 0.44, "rail": 0.34, "truck": 0.22}, "19"),
    ("almaty", "aktau", 8900, 6800, {"rail": 0.72, "truck": 0.22, "multiple": 0.06}, "43"),
    ("tashkent", "samarkand", 8200, 12400, {"truck": 0.54, "rail": 0.44, "air": 0.02}, "36"),
    ("tashkent", "fergana", 7600, 10800, {"truck": 0.62, "rail": 0.38}, "30"),
    ("almaty", "bishkek", 5400, 6200, {"truck": 0.78, "rail": 0.18, "air": 0.04}, "43"),
    ("tashkent", "bishkek", 4200, 4900, {"truck": 0.68, "rail": 0.28, "air": 0.04}, "30"),
    ("tashkent", "dushanbe", 3100, 4400, {"rail": 0.52, "truck": 0.46, "air": 0.02}, "32"),
    ("astana", "karaganda", 9400, 22600, {"rail": 0.74, "truck": 0.26}, "15"),
    ("karaganda", "ust-kamenogorsk", 6300, 11800, {"rail": 0.78, "truck": 0.22}, "32"),
    ("astana", "aktobe", 7100, 13400, {"rail": 0.68, "truck": 0.28, "air": 0.04}, "14"),
    ("aktobe", "atyrau", 6800, 14200, {"pipeline": 0.52, "rail": 0.34, "truck": 0.14}, "17"),
    ("ashgabat", "turkmenbashi", 5800, 11500, {"pipeline": 0.46, "rail": 0.36, "truck": 0.18}, "18"),
    ("tashkent", "bukhara", 6400, 9800, {"rail": 0.52, "pipeline": 0.26, "truck": 0.22}, "20"),
    ("samarkand", "dushanbe", 2400, 3200, {"truck": 0.64, "rail": 0.36}, "03"),
    ("osh", "fergana", 2100, 2900, {"truck": 0.84, "rail": 0.16}, "03"),
]

# Major documented Central Asian natural disasters (1980–2025, EM-DAT / UNDRR / World Bank)
# (id, date, type, kind, place, states, deaths, evacuated, cost_usd)
DISASTERS = [
    (1, "2024-04-04", "flood", "Historic Spring Snowmelt Floods", "West, North & Central Kazakhstan (Oral, Petropavl, Aktobe, Kostanay, Atyrau)", ["KZ"], 9, 119000, 1450000000),
    (2, "2020-05-01", "flood", "Sardoba Dam Collapse & Flood", "Syrdarya (UZ) & Turkistan (KZ)", ["UZ", "KZ"], 6, 102000, 520000000),
    (3, "2008-01-12", "winter", "Severe Cold Wave & Energy Crisis", "Tajikistan, Kyrgyzstan & Uzbekistan", ["TJ", "KG", "UZ"], 38, 0, 850000000),
    (4, "2023-06-08", "fire", "Abai Region Steppe & Pine Wildfire", "Semey / Abai Region, East Kazakhstan", ["KZ"], 15, 1000, 340000000),
    (5, "2021-06-15", "other", "Severe Aral & Mangystau Drought", "Mangystau, Kyzylorda (KZ) & Karakalpakstan (UZ)", ["KZ", "UZ"], 0, 0, 480000000),
    (6, "2015-12-07", "other", "M7.2 Sarez / Pamir Earthquake", "Gorno-Badakhshan (Murghab / Bartang Valley)", ["TJ"], 2, 1200, 125000000),
    (7, "1992-08-19", "other", "M7.3 Suusamyr Earthquake", "Chuy, Talas & Jalal-Abad Regions", ["KG"], 75, 18000, 290000000),
    (8, "2008-10-05", "other", "M6.7 Nura / Alay Earthquake", "Osh Region (Alay Valley)", ["KG"], 75, 1500, 95000000),
    (9, "1989-01-23", "other", "Gissar Earthquake & Loess Landslide", "Districts of Republican Subordination (Sharora)", ["TJ"], 274, 4500, 210000000),
    (10, "1985-10-13", "other", "Qayroqqum Earthquake", "Sughd Region (Khujand–Kayrakkum)", ["TJ"], 29, 8000, 260000000),
    (11, "2011-07-19", "other", "M6.1 Fergana Valley Earthquake", "Fergana (UZ), Batken (KG) & Sughd (TJ)", ["UZ", "KG", "TJ"], 14, 2400, 140000000),
    (12, "2000-12-06", "other", "M7.0 Balkanabat Earthquake", "Balkan Region (Caspian Foreland)", ["TM"], 11, 2000, 110000000),
    (13, "2010-03-11", "flood", "Kyzyl-Agash Dam Burst & Flood", "Almaty / Jetisu Region", ["KZ"], 45, 3000, 135000000),
    (14, "2015-07-23", "flood", "Almaty Glacial Mudflow (Kargaly)", "Almaty City & Ile-Alatau", ["KZ"], 0, 1050, 92000000),
    (15, "2024-01-23", "other", "M7.0 Tian Shan Border Earthquake", "Almaty (KZ) & Issyk-Kul (KG)", ["KZ", "KG"], 0, 12000, 68000000),
    (16, "2017-04-29", "flood", "Uzgen Landslides & Flash Floods", "Osh & Jalal-Abad Regions", ["KG"], 24, 3800, 54000000),
    (17, "2022-05-05", "flood", "Spring Flash Floods & Mudflows", "Khatlon & Sughd (TJ), Surkhandarya (UZ)", ["TJ", "UZ"], 16, 4200, 88000000),
    (18, "2023-01-12", "winter", "Central Asia Historic Arctic Freeze", "Tashkent, Fergana, Shymkent & Ashgabat", ["UZ", "KZ", "TM"], 8, 0, 310000000),
    (19, "1998-07-08", "flood", "Shahimardan Glacial Lake Outburst Flood", "Fergana Exclave (UZ) & Batken (KG)", ["UZ", "KG"], 104, 1500, 75000000),
    (20, "2024-07-14", "flood", "Osh & Nookat Summer Mudflows", "Osh Region & City", ["KG"], 17, 2900, 62000000),
]

# Specialty profiles -> relative multipliers across the 20 standard NAICS-style industry sectors
# so every city has distinct, realistic yields, citizens, and specialization districts!
SPECIALTY_INDUSTRY_WEIGHTS = {
    "capital_tech":       {"information": 3.4, "professional": 2.8, "finance": 2.4, "public_admin": 2.4, "education": 1.6, "arts": 1.8, "agriculture": 0.08},
    "capital_gov":        {"public_admin": 3.8, "professional": 2.3, "finance": 2.1, "construction": 1.9, "information": 2.0, "education": 1.6, "agriculture": 0.07},
    "finance_tech":       {"finance": 3.5, "information": 3.6, "professional": 3.0, "arts": 2.0, "accommodation": 1.6, "wholesale": 1.7, "agriculture": 0.06},
    "silkroad_campus":    {"education": 2.4, "accommodation": 3.2, "arts": 2.8, "retail": 1.3, "professional": 1.4, "agriculture": 0.45},
    "silkroad_heritage":  {"accommodation": 4.2, "arts": 3.6, "retail": 1.4, "education": 1.3, "agriculture": 0.5},
    "silkroad_gas":       {"mining": 2.4, "accommodation": 2.8, "arts": 2.4, "utilities": 1.5, "agriculture": 0.45},
    "silkroad_agri":      {"accommodation": 2.0, "arts": 1.8, "agriculture": 1.6, "retail": 1.2},
    "silkroad_trade":     {"wholesale": 2.1, "retail": 1.8, "accommodation": 1.8, "arts": 1.6, "transportation": 1.5},
    "silkroad_industrial":{"manufacturing": 2.0, "accommodation": 1.5, "arts": 1.6, "mining": 1.4},
    "silkroad_mining":    {"mining": 3.2, "accommodation": 1.8, "arts": 1.6, "agriculture": 0.9},
    "silk_craft":         {"manufacturing": 2.2, "arts": 2.3, "retail": 1.5, "accommodation": 1.4},
    "textile_trade":      {"manufacturing": 2.4, "wholesale": 1.7, "retail": 1.5, "agriculture": 0.7},
    "auto_industrial":    {"manufacturing": 3.2, "construction": 1.3, "transportation": 1.3, "agriculture": 0.55},
    "trade_industrial":   {"manufacturing": 1.8, "wholesale": 1.9, "retail": 1.5, "construction": 1.4, "transportation": 1.4},
    "refining_agri":      {"manufacturing": 2.5, "mining": 1.6, "utilities": 1.4, "agriculture": 0.7},
    "gas_hub":            {"mining": 4.4, "utilities": 1.9, "transportation": 1.5, "construction": 1.3, "agriculture": 0.35},
    "gas_power":          {"mining": 3.6, "utilities": 3.2, "construction": 1.3, "agriculture": 0.5},
    "gas_rail":           {"mining": 2.6, "transportation": 2.4, "manufacturing": 1.4, "agriculture": 0.55},
    "oil_capital":        {"mining": 6.2, "construction": 1.6, "transportation": 1.6, "professional": 1.5, "agriculture": 0.12},
    "mining_oil":         {"mining": 4.2, "manufacturing": 1.7, "transportation": 1.6, "agriculture": 0.3},
    "gold_uranium":       {"mining": 6.8, "manufacturing": 1.8, "utilities": 1.8, "construction": 1.3, "agriculture": 0.15},
    "uranium_agri":       {"mining": 3.4, "agriculture": 1.3, "transportation": 1.4},
    "copper_mining":      {"mining": 5.8, "manufacturing": 2.8, "utilities": 1.6, "agriculture": 0.15},
    "iron_mining":        {"mining": 6.0, "manufacturing": 2.4, "transportation": 1.5, "agriculture": 0.15},
    "coal_industrial":    {"mining": 4.5, "manufacturing": 2.2, "utilities": 2.0, "transportation": 1.5, "agriculture": 0.2},
    "coal_power":         {"mining": 5.2, "utilities": 4.8, "transportation": 1.6, "agriculture": 0.15},
    "steel_industrial":   {"manufacturing": 4.6, "mining": 2.0, "utilities": 1.8, "agriculture": 0.12},
    "metals_hydro":       {"manufacturing": 3.2, "mining": 2.8, "utilities": 2.6, "agriculture": 0.2},
    "metals_power":       {"manufacturing": 3.0, "utilities": 3.2, "mining": 1.8, "transportation": 1.4, "agriculture": 0.25},
    "hydro_power":        {"utilities": 5.8, "construction": 2.2, "agriculture": 0.35},
    "hydro_agri":         {"utilities": 2.4, "agriculture": 1.4, "retail": 1.2},
    "caspian_port":       {"transportation": 4.2, "mining": 2.8, "wholesale": 1.5, "accommodation": 1.4, "agriculture": 0.1},
    "spaceport":          {"professional": 4.8, "information": 3.2, "public_admin": 3.0, "transportation": 2.4, "agriculture": 0.05},
    "border_garrison":    {"public_admin": 2.6, "transportation": 2.4, "wholesale": 1.6, "agriculture": 0.7},
    "chem_garrison":      {"manufacturing": 2.8, "public_admin": 2.2, "utilities": 1.6, "agriculture": 0.3},
    "chem_agri":          {"manufacturing": 2.2, "mining": 1.8, "agriculture": 1.2},
    "wheat_auto":         {"agriculture": 1.9, "manufacturing": 2.2, "wholesale": 1.5, "transportation": 1.4},
    "wheat_rail":         {"agriculture": 2.1, "transportation": 2.2, "manufacturing": 1.4},
    "regional_gov":       {"public_admin": 2.2, "education": 1.6, "health": 1.5, "agriculture": 0.9},
    "culture_campus":     {"education": 2.2, "arts": 2.2, "health": 1.5, "manufacturing": 1.2},
    "resort_agri":        {"accommodation": 2.6, "agriculture": 1.6, "arts": 1.5},
    "mountain_resort":    {"accommodation": 3.4, "arts": 2.0, "agriculture": 1.2},
    "rail_resort":        {"transportation": 2.6, "accommodation": 2.4, "retail": 1.3},
    "alpine_campus":      {"education": 2.6, "public_admin": 1.8, "accommodation": 1.8, "agriculture": 1.1},
    "agri_power":         {"utilities": 2.8, "agriculture": 1.7, "manufacturing": 1.2},
    "agri_industrial":    {"manufacturing": 2.0, "agriculture": 1.5, "construction": 1.3},
    "agri_trade":         {"agriculture": 1.9, "retail": 1.4, "wholesale": 1.4},
    "agri_culture":       {"agriculture": 1.8, "arts": 1.7, "education": 1.3},
    "border_agri":        {"agriculture": 2.0, "public_admin": 1.6, "retail": 1.3},
}
