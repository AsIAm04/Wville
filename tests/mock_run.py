"""Full offline run of pull_data.py against mock API responses. Values are fake.
Run: python tests/mock_run.py"""
import sys, random, json, pathlib
import os; HERE=pathlib.Path(__file__).resolve().parent; sys.path.insert(0,str(HERE.parent/"pull")); sys.path.insert(0,str(HERE))
import test_pull as T, pull_data as P
random.seed(1)
ACSV={"B19013":{"B19013_001E":"Estimate!!Median household income"},
"B17001":{"B17001_001E":"Estimate!!Total:","B17001_002E":"Estimate!!Total:!!Income in the past 12 months below poverty level:","B17001_003E":"Estimate!!Total:!!Income in the past 12 months below poverty level:!!Male:"},
"B25003":{"B25003_001E":"Estimate!!Total:","B25003_002E":"Estimate!!Total:!!Owner occupied"},
"B25044":{"B25044_001E":"Estimate!!Total:","B25044_003E":"Estimate!!Total:!!Owner occupied:!!No vehicle available","B25044_010E":"Estimate!!Total:!!Renter occupied:!!No vehicle available"},
"B25070":{"B25070_001E":"Estimate!!Total:","B25070_007E":"Estimate!!Total:!!30.0 to 34.9 percent","B25070_008E":"Estimate!!Total:!!35.0 to 39.9 percent","B25070_009E":"Estimate!!Total:!!40.0 to 49.9 percent","B25070_010E":"Estimate!!Total:!!50.0 percent or more","B25070_011E":"Estimate!!Total:!!Not computed"},
"B25034":{"B25034_001E":"Estimate!!Total:","B25034_008E":"Estimate!!Total:!!Built 1970 to 1979"},
"B18101":{"B18101_001E":"Estimate!!Total:","B18101_004E":"Estimate!!Total:!!Male:!!Under 5 years:!!With a disability"},
"B27001":{"B27001_001E":"Estimate!!Total:","B27001_005E":"Estimate!!Total:!!Male:!!Under 6 years:!!No health insurance coverage"}}
def fake(url, params=None):
    params=params or {}
    if "tigerweb" in url:
        if url.endswith("MapServer"): return {"layers":[{"id":8,"name":"Census Tracts"},{"id":28,"name":"Incorporated Places"},{"id":12,"name":"Census Blocks"}]}
        if "/12/query" in url:
            return {"type":"FeatureCollection","features":[
              {"type":"Feature","properties":{"GEOID":"051190040051000"},"geometry":{"type":"Polygon","coordinates":[[[-92.199,34.601],[-92.195,34.601],[-92.195,34.604],[-92.199,34.601]]]}},
              {"type":"Feature","properties":{"GEOID":"051190040072000"},"geometry":{"type":"Polygon","coordinates":[[[-92.199,34.6005],[-92.196,34.6005],[-92.196,34.602],[-92.199,34.6005]]]}},
              {"type":"Feature","properties":{"GEOID":"051190040059999"},"geometry":{"type":"Polygon","coordinates":[[[-80,30],[-80.1,30],[-80.1,30.1],[-80,30]]]}}]}
        if "/8/query" in url and params.get("geometry"):
            return {"type":"FeatureCollection","features":[{"type":"Feature","properties":{"GEOID":"05119004005","NAME":"Census Tract 40.05"},"geometry":{"type":"Polygon","coordinates":[[[-92.3,34.5],[-92.1,34.5],[-92.1,34.7],[-92.3,34.5]]]}}]}
        return {"type":"FeatureCollection","features":[{"type":"Feature","properties":{"NAME":"X"},"geometry":{"type":"Polygon","coordinates":[[[-92.2,34.6],[-92.19,34.6],[-92.19,34.61],[-92.2,34.6]]]}}]}
    if url.endswith("2020/dec/pl/groups.json"):
        return {"groups":[{"name":"P1","description":"RACE"},{"name":"P5","description":"GROUP QUARTERS POPULATION BY MAJOR GROUP QUARTERS TYPE"},{"name":"H1","description":"OCCUPANCY STATUS"}]}
    if url.endswith("groups.json"): return T.GROUPS
    if "dec/pl/groups/" in url:
        PL={"P1":{"P1_001N":" !!Total:"},"P5":{"P5_001N":" !!Total:"},"H1":{"H1_001N":" !!Total:","H1_002N":" !!Total:!!Occupied"}}
        return {"variables":{n:{"label":l} for n,l in PL[url.rsplit("/",1)[1][:-5]].items()}}
    if "/groups/" in url:
        g=url.rsplit("/",1)[1][:-5]
        if g in ACSV: return {"variables":{n:{"label":l} for n,l in ACSV[g].items()}}
        return T.fake(url)
    if params.get("for")=="block:*":
        t=params["in"].split("tract:")[1]
        names=params["get"].split(",")
        rows=[names+["state","county","tract","block"]]
        for b,v in (("1000",["120","100","8"]),("2000",["60","0","25"]),("9999",["5","0","2"])):
            rows.append(v+["05","119",t,b])
        return rows
    if url.endswith("2020/dec/pl/groups.json"):
        return {"groups":[{"name":"P1","description":"RACE"},{"name":"P5","description":"GROUP QUARTERS POPULATION BY MAJOR GROUP QUARTERS TYPE"},{"name":"H1","description":"OCCUPANCY STATUS"}]}
    if params.get("get")=="NAME": return [["NAME","state","place"],["Wrightsville city, Arkansas","05","76970"],["Little Rock city, Arkansas","05","41000"]]
    if "acs5" in url and url.split("/")[-3]=="2009" and "tract" in params.get("for",""): return None
    names=params["get"].split(",")
    return [names,[str(random.randint(10,500)) for _ in names]]
P.get_json=fake
P.api_key=lambda:"x"
import tempfile; P.DATA=pathlib.Path(tempfile.mkdtemp()); print("mock output in", P.DATA)
P.main()
