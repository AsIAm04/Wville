"""Offline tests: the resolver and math against mock Census responses
shaped like the published API (labels in 2000/2010/2020 styles)."""
import sys, pathlib, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "pull"))
import pull_data as P

GROUPS = {"groups": [
  {"name": "P1", "description": "TOTAL POPULATION"},
  {"name": "P12", "description": "SEX BY AGE FOR SELECTED AGE CATEGORIES"},
  {"name": "P18", "description": "GROUP QUARTERS POPULATION BY MAJOR GROUP QUARTERS TYPE"},
  {"name": "PCO1", "description": "GROUP QUARTERS POPULATION BY SEX BY AGE"},
  {"name": "H3", "description": "OCCUPANCY STATUS"}]}
VARS = {
 "P1": {"P1_001N": "!!Total"},
 "P18": {"P18_001N": " !!Total:", "P18_002N": " !!Total:!!Institutionalized population:"},
 "H3": {"H3_001N": " !!Total:", "H3_002N": " !!Total:!!Occupied", "H3_003N": " !!Total:!!Vacant"},
 "P12": {"P12_001N": " !!Total:", "P12_002N": " !!Total:!!Male:", "P12_020N": " !!Total:!!Male:!!65 and 66 years",
         "P12_021N": " !!Total:!!Male:!!67 to 69 years", "P12_019N": " !!Total:!!Male:!!62 to 64 years",
         "P12_049N": " !!Total:!!Female:!!85 years and over", "P12_ANN": "Annotation of !!Total"},
 "PCO1": {"PCO1_001N": " !!Total:", "PCO1_020N": " !!Total:!!Male:!!65 to 69 years"},
}
def fake(url, params=None):
    if url.endswith("groups.json"): return GROUPS
    g = url.rsplit("/", 1)[1].replace(".json", "")
    return {"variables": {n: {"label": l} for n, l in VARS[g].items()}}
P.get_json = fake

def test_groups_and_lines():
    g = P.find_group(2020, "dec/dhc", r"^group quarters population by (major )?group quarters type$")
    assert g == "P18"
    vs = P.group_vars(2020, "dec/dhc", "P18", acs=False)
    assert P.match(vs, ["TOTAL"]) == ["P18_001N"]
    vs = P.group_vars(2020, "dec/dhc", "H3", acs=False)
    assert P.match(vs, [r"^occupied$"]) == ["H3_002N"]
    vs = P.group_vars(2020, "dec/dhc", "P12", acs=False)
    assert P.age65_vars(vs) == ["P12_020N", "P12_021N", "P12_049N"]
    assert "P12_ANN" not in vs
    g = P.find_group(2020, "dec/dhc", r"^group quarters population by sex by age( by group quarters type)?$")
    assert g == "PCO1"

def test_label_paths():
    assert P.label_path("Estimate!!Total:!!Owner occupied:!!No vehicle available") == "owner occupied>no vehicle available"
    assert P.label_path("Estimate!!Total") == ""
    assert P.label_path("Total!!Male!!65 and 66 years") == "male>65 and 66 years"
    assert P.norm("SEX BY AGE [49]") == "sex by age"

def test_math():
    assert abs(P.sum_moe({"a": 3, "b": 4}, ["a", "b"]) - 5) < 1e-9
    m = P.share_moe(20, 100, 5, 10)        # p=.2 -> sqrt(25-0.04*100)/100
    assert abs(m - math.sqrt(21) / 100) < 1e-9
    assert P.differs({"est": 30, "moe": 2}, {"est": 20, "moe": 2}) is True
    assert P.differs({"est": 21, "moe": 8}, {"est": 20, "moe": 2}) is False

def test_acs_rent_burden_lines():
    vs = {"B25070_001E": "", "B25070_007E": "30.0 to 34.9 percent", "B25070_010E": "50.0 percent or more",
          "B25070_011E": "not computed", "B25070_006E": "25.0 to 29.9 percent"}
    import measures as M
    m = [x for x in M.ACS_MEASURES if x["id"] == "rent_burden_30"][0]
    nums = P.match(vs, [r"^30\.0 to 34\.9 percent$", r"^50\.0 percent or more$"])
    assert nums == ["B25070_007E", "B25070_010E"]
    vs2 = {"B25034_001E": "", "B25034_002E": "built 2020 or later", "B25034_008E": "built 1970 to 1979", "B25034_011E": "built 1939 or earlier"}
    b = [x for x in M.ACS_MEASURES if x["id"] == "built_pre1980"][0]
    assert P.match(vs2, b["num"]) == ["B25034_008E", "B25034_011E"]
