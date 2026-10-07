"""Measure definitions for the Wrightsville dashboard.

Variables are found by their published group description and labels at run
time (from the Census API's groups.json), not by hard-coded codes, because
codes differ across the 2000, 2010, and 2020 censuses and shift inside some
ACS tables between years. The pull stops and reports if a match is missing
or ambiguous.
"""

# ---------------------------------------------------------------- geography
STATE_FIPS = "05"          # Arkansas
COUNTY_FIPS = "119"        # Pulaski County
TRACT = "004005"           # Tract 40.05 (2020 numbering; checked per vintage)
PLACE_NAME_REGEX = r"^Wrightsville( city| town)?, Arkansas$"

# ---------------------------------------------------------------- vintages
DECENNIAL = [
    {"year": 2000, "dataset": "dec/sf1"},
    {"year": 2010, "dataset": "dec/sf1"},
    {"year": 2020, "dataset": "dec/dhc"},
]

# ACS 5-year periods that do NOT overlap (Census Bureau guidance).
# 2009 = 2005-2009 release; may be unavailable for very small places.
ACS_END_YEARS = [2009, 2014, 2019, 2024]

# ---------------------------------------------------------------- decennial
# kind "total": the group's top-level Total line.
# kind "label": sum of lines whose path (below Total) matches the regex list.
# kind "age65": sum of [sex, age] lines with starting age 65 or older.
DEC_MEASURES = [
    {"id": "pop_total", "label": "Total population",
     "group": r"^total population$", "kind": "total"},
    {"id": "pop_gq", "label": "Group quarters population",
     "group": r"^group quarters population by (major )?group quarters type$",
     "kind": "total"},
    {"id": "housing_units", "label": "Housing units",
     "group": r"^occupancy status$", "kind": "total"},
    {"id": "households", "label": "Households (occupied units)",
     "group": r"^occupancy status$", "kind": "label", "path": [r"^occupied$"]},
    {"id": "age65_total", "label": "Residents 65 and older (all)",
     "group": r"^sex by age( for selected age categories)?$", "kind": "age65"},
    {"id": "age65_gq", "label": "Residents 65 and older in group quarters",
     "group": r"^group quarters population by sex by age( by group quarters type)?$",
     "kind": "age65"},
]

# Derived decennial measures (computed after the pull).
DEC_DERIVED = [
    {"id": "pop_household", "label": "Household population",
     "formula": ("minus", "pop_total", "pop_gq"), "unit": "count"},
    {"id": "age65_household_share", "label": "Share 65 and older, households only",
     "formula": ("share_of_diff", "age65_total", "age65_gq", "pop_total", "pop_gq"),
     "unit": "pct"},
    {"id": "age65_total_share", "label": "Share 65 and older, all residents",
     "formula": ("share", "age65_total", "pop_total"), "unit": "pct"},
]

# ---------------------------------------------------------------- ACS
# group: ACS table ID (stable across years). Lines picked by label path.
# num/den: lists of label-path regexes; each matched line is summed.
# "TOTAL" means the table's top-level Total line.
ACS_MEASURES = [
    {"id": "median_hh_income", "label": "Median household income",
     "group": "B19013", "kind": "value", "num": ["TOTAL"], "unit": "usd",
     "universe": "Households",
     "note": "Each period in its own year's dollars; not adjusted for inflation, so growth is overstated"},
    {"id": "poverty_rate", "label": "Poverty rate",
     "group": "B17001", "kind": "share", "unit": "pct",
     "num": [r"^income in the past 12 months below poverty level$"], "den": ["TOTAL"],
     "universe": "People for whom poverty status is determined (excludes institutionalized)"},
    {"id": "owner_share", "label": "Homeowner share",
     "group": "B25003", "kind": "share", "unit": "pct",
     "num": [r"^owner occupied$"], "den": ["TOTAL"], "universe": "Occupied housing units"},
    {"id": "no_vehicle_share", "label": "Households without a vehicle",
     "group": "B25044", "kind": "share", "unit": "pct",
     "num": [r"^(owner|renter) occupied>no vehicle available$"], "den": ["TOTAL"],
     "universe": "Occupied housing units"},
    {"id": "rent_burden_30", "label": "Renters paying 30% or more of income",
     "group": "B25070", "kind": "share", "unit": "pct",
     "num": [r"^30\.0 to 34\.9 percent$", r"^35\.0 to 39\.9 percent$",
             r"^40\.0 to 49\.9 percent$", r"^50\.0 percent or more$"],
     "den": ["TOTAL"], "den_minus": [r"^not computed$"],
     "universe": "Renter households with rent burden computed"},
    {"id": "built_pre1980", "label": "Homes built before 1980",
     "group": "B25034", "kind": "share", "unit": "pct",
     "num": [r"^built (19[0-7]\d to 19[0-7]\d|1939 or earlier)$"], "den": ["TOTAL"],
     "universe": "Housing units"},
    {"id": "disability_share", "label": "Residents with a disability",
     "group": "B18101", "kind": "share", "unit": "pct",
     "num": [r">with a disability$"], "den": ["TOTAL"],
     "universe": "Civilian noninstitutionalized population"},
    {"id": "uninsured_share", "label": "Residents without health insurance",
     "group": "B27001", "kind": "share", "unit": "pct",
     "num": [r">no health insurance coverage$"], "den": ["TOTAL"],
     "universe": "Civilian noninstitutionalized population"},
]
