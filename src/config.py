"""Paths and fixed constants used by the numbered scripts.

This module only defines constants. It does not read data or compute results.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to the repository root)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_OECD = RAW / "oecd"
RAW_PORTWATCH = RAW / "portwatch"
RAW_VERSCHUUR = RAW / "verschuur_v3"
INTERIM = DATA / "interim"
REFERENCE = DATA / "reference"
MANIFEST = DATA / "MANIFEST.csv"

OUTPUTS = ROOT / "outputs"
CHECKS = OUTPUTS / "checks"

# Raw files
OECD_FILE = RAW_OECD / "oecd_maritime_co2_raw_2026-10-31.csv"
PORTWATCH_FILE = RAW_PORTWATCH / "Daily_Chokepoints_Data.csv"
V3_EXPORT_FILE = RAW_VERSCHUUR / "country_export_dependency.csv"
V3_IMPORT_FILE = RAW_VERSCHUUR / "country_import_dependency.csv"
V3_TRADE_RISK_FILE = RAW_VERSCHUUR / "chokepoint_systemic_trade_risk.csv"
V3_ECON_RISK_FILE = RAW_VERSCHUUR / "chokepoint_systemic_economic_risk.csv"
V3_NOTEBOOK_FILE = RAW_VERSCHUUR / "Maritime_chokepoint_risk_trade.ipynb"
RAW_UNCTAD = RAW / "unctad"
UNCTAD_FLEET_FILE = RAW_UNCTAD / "US_MerchantFleet.csv"

# Interim files
OECD_MONTHLY = INTERIM / "oecd_monthly.csv.gz"
PORTWATCH_MONTHLY = INTERIM / "portwatch_monthly.csv.gz"
V3_SHARES = INTERIM / "verschuur_v3_shares.csv"

# Reference files
COUNTRY_GROUPS = REFERENCE / "country_groups.csv"

# ---------------------------------------------------------------------------
# Dates (YYYY-MM)
# ---------------------------------------------------------------------------
PRE_START = "2019-01"
PRE_END = "2023-11"
SHOCK_START = "2023-12"
MAIN_END = "2025-10"
SENS_END_RESIDENCE = "2026-02"
COVID_EXCL = ("2020-01", "2021-12")
RECLASS_2022_EXCL = ("2021-11", "2022-10")

# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------
NON_ECONOMY_AREAS = ("W", "OECD", "W_O")

# ---------------------------------------------------------------------------
# Country groups (pre-specified by geography)
# ---------------------------------------------------------------------------
RSL = (
    "EGY", "SDN", "ERI", "DJI", "YEM", "SAU", "JOR", "ISR", "SOM",
)
RSL_RULE = (
    "Economies with a coastline on the Red Sea, Gulf of Suez, "
    "Gulf of Aqaba or Gulf of Aden."
)

CPA = (
    "MRT", "SEN", "GMB", "GNB", "GIN", "SLE", "LBR", "CIV", "GHA", "TGO",
    "BEN", "NGA", "CPV", "CMR", "GNQ", "GAB", "COG", "COD", "AGO", "STP",
    "NAM", "ZAF", "MOZ", "MDG", "MUS", "SYC", "COM", "KEN", "TZA", "MYT",
    "REU", "SHN",
)
CPA_RULE = (
    "Coastal economies of Sub-Saharan Africa (UN M49) on the Atlantic or "
    "Indian Ocean, excluding RSL, plus African island economies and "
    "territories in those oceans."
)

HQ = ("CHE", "DNK", "FRA", "CHN", "TWN", "DEU", "KOR", "SGP")
HQ_RULE = (
    "Headquarters of the nine alliance carriers on Asia-Europe and "
    "Asia-Mediterranean services in October 2023 (Yap & Yang, 2024): "
    "CHE (MSC), DNK (Maersk), FRA (CMA CGM), CHN (COSCO), "
    "TWN (Evergreen, Yang Ming), DEU (Hapag-Lloyd), KOR (HMM), SGP (ONE)."
)
# Sensitivity assignments for HQ
HQ_SENS_ONE = "JPN"
HQ_SENS_SUBSIDIARIES = {"APL": "SGP", "OOCL": "HKG"}

EEA = (
    "AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA",
    "DEU", "GRC", "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD",
    "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE", "NOR", "ISL", "LIE",
)
EEA_RULE = "Economies under the maritime EU ETS."

RUS = ("RUS",)
RUS_RULE = "Russia."

COUNTRY_GROUP_DEFS = {
    "RSL": (RSL, RSL_RULE),
    "CPA": (CPA, CPA_RULE),
    "HQ": (HQ, HQ_RULE),
    "EEA": (EEA, EEA_RULE),
    "RUS": (RUS, RUS_RULE),
}

# ---------------------------------------------------------------------------
# Expected raw-file metadata and checksums
# ---------------------------------------------------------------------------
CHECK = "[check]"

_OECD_META = {
    "source": (
        "OECD, Maritime transport CO2 emissions (experimental), dataflow "
        "OECD.SDD.NAD.SEEA:DSD_MARITIME_TRANSPORT@DF_MARITIME_TRANSPORT"
    ),
    "version": "2.0",
    "release_date": "2026-10-14",
    "download_date": "2026-10-31",
    "licence": (
        "OECD Terms and Conditions, section 3: reuse and redistribution "
        "with attribution"
    ),
    "doi_or_url": CHECK,
}
_PORTWATCH_META = {
    "source": "IMF PortWatch, Daily Chokepoints Data",
    "version": CHECK,
    "release_date": CHECK,
    "download_date": "2026-10-31",
    "licence": CHECK,
    "doi_or_url": CHECK,
}
_V3_META = {
    "source": (
        "Verschuur & Hall, Maritime chokepoint dependencies and systemic "
        "risks (Zenodo dataset)"
    ),
    "version": "v3",
    "release_date": "2025-11-24",
    "download_date": CHECK,
    "licence": "CC BY 4.0",
    "doi_or_url": "https://doi.org/10.5281/zenodo.19663059",
}
_UNCTAD_META = {
    "source": ("UNCTADstat (Clarksons Research), Merchant fleet: By flag of registration "
               "and ship type, annual (bulk file)"),
    "version": CHECK,
    "release_date": CHECK,
    "download_date": CHECK,
    "licence": CHECK,
    "doi_or_url": CHECK,
    "checksum_note": "recorded at intake",
}

# Each entry: file path, metadata, checksum algorithm, expected checksum,
# expected size in bytes (None when not recorded).
RAW_FILES = [
    (OECD_FILE, _OECD_META, "sha256",
     "88fb19b9645e4452d26e88cf8891467a3732d380a54f1b445f3735849fdf6002",
     200_921_743),
    (PORTWATCH_FILE, _PORTWATCH_META, "sha256",
     "7b56fbaffba58c16ef0ff6e6024846438647e7d15861911f9c67932116f4d439",
     None),
    (V3_EXPORT_FILE, _V3_META, "md5", "88df0a9cc8302021d06c86c871780c2d", None),
    (V3_IMPORT_FILE, _V3_META, "md5", "148bd8775a7d51c7207a6ff796a8d33d", None),
    (V3_TRADE_RISK_FILE, _V3_META, "md5",
     "365d388f4c23309a6a0c906f4f8fd85e", None),
    (V3_ECON_RISK_FILE, _V3_META, "md5",
     "c0d3576ceba2be6304eefaf32e1ada45", None),
    (V3_NOTEBOOK_FILE, _V3_META, "md5",
     "fc14fc4206f5f8ab52828361924759bb", None),
    (UNCTAD_FLEET_FILE, _UNCTAD_META, "sha256",
     "a0c318d2e174e022ef8319fa08cef85cee9625ade9ca48a3dde7a15029372a62", 9_461_926),
]
