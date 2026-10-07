"""Pull Wrightsville dashboard data from the Census API and TIGERweb.

Run from the repo root:
    python pull/pull_data.py

Needs CENSUS_API_KEY in the environment or in a .env file at the repo root.
Writes:
    data/series.csv          tidy table, one row per measure x geography x period
    data/pull_log.txt        every variable used, with its published label
    data/boundaries.geojson  city and tract 40.05 outlines (2020 vintage)
    data/embed_block.js      paste over the WV_SERIES block in the embed
"""
import csv, json, math, os, re, sys, datetime, pathlib
import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import measures as M

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
API = "https://api.census.gov/data"
TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer"
Z90 = 1.645
LOG = []


def log(msg):
    print(msg)
    LOG.append(msg)


def api_key():
    key = os.environ.get("CENSUS_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("CENSUS_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("CENSUS_API_KEY not set. Copy .env.example to .env and add your key.")
    return key


SESSION = requests.Session()


def get_json(url, params=None):
    r = SESSION.get(url, params=params, timeout=60)
    if r.status_code == 204 or not r.text.strip():
        return None
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} for {r.url}: {r.text[:200]}")
    try:
        return r.json()
    except ValueError:
        raise RuntimeError(f"Non-JSON response for {r.url}: {r.text[:200]}")


# ---------------------------------------------------------------- labels
def norm(s):
    return re.sub(r"\s*\[\d+\]\s*", "", s).strip().rstrip(":").strip().lower()


def label_path(label):
    """'Estimate!!Total:!!Owner occupied:!!No vehicle available'
    -> 'owner occupied>no vehicle available'. Top-level Total -> ''."""
    parts = [norm(p) for p in label.split("!!")]
    parts = [p for p in parts if p not in ("estimate", "")]
    if parts and parts[0] == "total":
        parts = parts[1:]
    return ">".join(parts)


def is_value_var(name, meta, acs):
    lab = meta.get("label", "")
    if "annotation" in lab.lower() or name in ("GEO_ID", "NAME"):
        return False
    if acs:
        return name.endswith("E") and lab.lower().startswith("estimate")
    return not name.endswith(("NA", "EA", "MA"))


_group_cache = {}


def find_group(year, dataset, desc_regex):
    key = (year, dataset)
    if key not in _group_cache:
        js = get_json(f"{API}/{year}/{dataset}/groups.json")
        _group_cache[key] = js["groups"] if js else []
    hits = [g for g in _group_cache[key] if re.search(desc_regex, norm(g["description"]))]
    if not hits:
        raise LookupError(f"No group matching /{desc_regex}/ in {year} {dataset}")
    hits.sort(key=lambda g: (len(g["name"]), g["name"]))
    if len(hits) > 1:
        log(f"  note: {len(hits)} groups match /{desc_regex}/ in {year}; using {hits[0]['name']} ({hits[0]['description']})")
    return hits[0]["name"]


def group_vars(year, dataset, group, acs):
    js = get_json(f"{API}/{year}/{dataset}/groups/{group}.json")
    if not js:
        raise LookupError(f"Group {group} not available in {year} {dataset}")
    out = {}
    for name, meta in js["variables"].items():
        if is_value_var(name, meta, acs):
            out[name] = label_path(meta["label"])
    return out


def match(vars_, regexes, required=True, what=""):
    names = []
    for rx in regexes:
        if rx == "TOTAL":
            hit = [n for n, p in vars_.items() if p == ""]
            if not hit and len(vars_) == 1:      # single-line tables (e.g. a median)
                hit = list(vars_)
        else:
            hit = [n for n, p in vars_.items() if re.search(rx, p)]
        if not hit and required:
            raise LookupError(f"No line matches /{rx}/ {what}")
        names += hit
    return sorted(set(names))


def age65_vars(vars_):
    out = []
    for n, p in vars_.items():
        parts = p.split(">")
        if len(parts) == 2 and parts[0] in ("male", "female"):
            m = re.match(r"^(\d+)", parts[1])
            if m and int(m.group(1)) >= 65 and "year" in parts[1]:
                out.append(n)
    if not out:
        raise LookupError("No [sex > age 65+] lines found")
    return sorted(out)


# ---------------------------------------------------------------- geographies
def geos(year, dataset, key, place_code):
    return {
        "city": {"for": f"place:{place_code}", "in": f"state:{M.STATE_FIPS}"},
        **{k: {"for": f"tract:{t}", "in": f"state:{M.STATE_FIPS} county:{M.COUNTY_FIPS}"} for k, t in M.TRACTS.items()},
        "county": {"for": f"county:{M.COUNTY_FIPS}", "in": f"state:{M.STATE_FIPS}"},
        "state": {"for": f"state:{M.STATE_FIPS}"},
    }


def resolve_place(year, dataset, key):
    js = get_json(f"{API}/{year}/{dataset}", {"get": "NAME", "for": "place:*", "in": f"state:{M.STATE_FIPS}", "key": key})
    hits = [r for r in js[1:] if re.match(M.PLACE_NAME_REGEX, r[0])]
    if len(hits) != 1:
        raise LookupError(f"Expected one Wrightsville place in {year}, found {len(hits)}")
    log(f"  place {year}: {hits[0][0]} = {M.STATE_FIPS}-{hits[0][-1]}")
    return hits[0][-1]


def fetch(year, dataset, names, geo, key):
    """Fetch variables (chunked to 45) for one geography. Returns {var: float|None}."""
    out = {}
    for i in range(0, len(names), 45):
        chunk = names[i:i + 45]
        params = {"get": ",".join(chunk), "key": key, **geo}
        js = get_json(f"{API}/{year}/{dataset}", params)
        if not js:
            return None
        head, row = js[0], js[1]
        for n in chunk:
            v = row[head.index(n)]
            try:
                f = float(v)
                out[n] = None if f < -555555 else f   # Census jam values are large negatives
            except (TypeError, ValueError):
                out[n] = None
    return out


# ---------------------------------------------------------------- math
def sum_est(vals, names):
    xs = [vals.get(n) for n in names]
    return None if any(x is None for x in xs) else sum(xs)


def sum_moe(moes, names):
    xs = [moes.get(n) for n in names]
    return None if any(x is None for x in xs) else math.sqrt(sum(x * x for x in xs))


def share_moe(num, den, moe_num, moe_den):
    """Census approximation for a proportion; falls back to ratio form if negative."""
    if None in (num, den, moe_num, moe_den) or den == 0:
        return None
    p = num / den
    inside = moe_num ** 2 - p ** 2 * moe_den ** 2
    if inside < 0:
        inside = moe_num ** 2 + p ** 2 * moe_den ** 2
    return math.sqrt(inside) / den


def differs(a, b):
    """90% test: are two estimates statistically different?"""
    if None in (a.get("est"), b.get("est"), a.get("moe"), b.get("moe")):
        return None
    se = math.sqrt((a["moe"] / Z90) ** 2 + (b["moe"] / Z90) ** 2)
    if se == 0:
        return a["est"] != b["est"]
    return abs(a["est"] - b["est"]) / se > Z90


# ---------------------------------------------------------------- pulls
ROWS = []


def add(mid, geo, period, est, moe, source, var_note):
    ROWS.append({"measure": mid, "geo": geo, "period": period, "est": est, "moe": moe,
                 "source": source, "variables": var_note})


def pull_decennial(key):
    for v in M.DECENNIAL:
        y, ds = v["year"], v["dataset"]
        log(f"Decennial {y} ({ds})")
        try:
            place = resolve_place(y, ds, key)
        except Exception as e:
            log(f"  SKIP {y}: {e}")
            continue
        G = geos(y, ds, key, place)
        for m in M.DEC_MEASURES:
            specs = [m] + m.get("alts", [])
            for si, spec in enumerate(specs):
                sds = spec.get("dataset", ds) if si else ds
                try:
                    g = find_group(y, sds, spec["group"])
                    vs = group_vars(y, sds, g, acs=False)
                    if spec["kind"] == "total":
                        names = match(vs, ["TOTAL"], what=f"in {g}")
                    elif spec["kind"] == "label":
                        names = match(vs, spec["path"], what=f"in {g}")
                    else:
                        names = age65_vars(vs)
                except Exception as e:
                    log(f"  {'MISSING' if si == len(specs) - 1 else 'try next'} {m['id']} {y} ({sds}): {e}")
                    if si == len(specs) - 1:
                        diagnose(y, sds, m["id"])
                    continue
                note = f"{sds} {g}: " + "; ".join(f"{n}={vs[n] or 'total'}" for n in names)
                got = {}
                for gname, geo in G.items():
                    try:
                        vals = fetch(y, sds, names, geo, key)
                    except Exception as e:
                        log(f"    {gname}: not available ({str(e)[:80]})")
                        continue
                    if vals is not None:
                        got[gname] = sum_est(vals, names)
                if got.get("city") is None and si < len(specs) - 1:
                    log(f"  try next {m['id']} {y}: {g} has no city value")
                    continue
                if got.get("city") is None:
                    log(f"  MISSING {m['id']} {y}: {g} returned no city value")
                    diagnose(y, sds, m["id"])
                log(f"  {m['id']}: {note}")
                for gname, est in got.items():
                    add(m["id"], gname, str(y), est, None, f"Census {y} {sds}", note)
                break


def diagnose(year, dataset, mid):
    """Log candidate groups so the next fix is one step."""
    words = ("group quarters", "65 years") if ("gq" in mid or "65" in mid) else ("total",)
    try:
        gs = _group_cache.get((year, dataset)) or get_json(f"{API}/{year}/{dataset}/groups.json")["groups"]
    except Exception:
        return
    hits = [f"{g['name']}: {g['description']}" for g in gs if any(w in g["description"].lower() for w in words)]
    for h in hits[:15]:
        log(f"    candidate {h}")


def derive_decennial():
    idx = {(r["measure"], r["geo"], r["period"]): r["est"] for r in ROWS}
    periods = sorted({r["period"] for r in ROWS if r["source"].startswith("Census") and "acs" not in r["source"]})
    for d in M.DEC_DERIVED:
        for geo in ["city", *M.TRACTS, "county", "state"]:
            for p in periods:
                get = lambda k: idx.get((k, geo, p))
                f = d["formula"]
                est = None
                if f[0] == "minus" and None not in (get(f[1]), get(f[2])):
                    est = get(f[1]) - get(f[2])
                elif f[0] == "share" and None not in (get(f[1]), get(f[2])) and get(f[2]):
                    est = get(f[1]) / get(f[2]) * 100
                elif f[0] == "share_of_diff" and None not in (get(f[1]), get(f[2]), get(f[3]), get(f[4])):
                    den = get(f[3]) - get(f[4])
                    est = (get(f[1]) - get(f[2])) / den * 100 if den else None
                if est is not None:
                    add(d["id"], geo, p, est, None, "Derived from Census counts", str(f))


def pull_acs(key):
    for end in M.ACS_END_YEARS:
        ds, period = "acs/acs5", f"{end-4} to {end}"
        log(f"ACS 5-year {period}")
        try:
            place = resolve_place(end, ds, key)
        except Exception as e:
            log(f"  SKIP {period}: {e}")
            continue
        G = geos(end, ds, key, place)
        for m in M.ACS_MEASURES:
            try:
                vs = group_vars(end, ds, m["group"], acs=True)
                num = match(vs, m["num"], what=f"in {m['group']} {end}")
                den = match(vs, m.get("den", []), what=f"in {m['group']} {end}") if m.get("den") else []
                dmin = match(vs, m.get("den_minus", []), what=f"in {m['group']} {end}") if m.get("den_minus") else []
            except Exception as e:
                log(f"  MISSING {m['id']} {end}: {e}")
                continue
            note = f"{m['group']}: num={','.join(num)}" + (f" den={','.join(den)}" if den else "") + (f" minus={','.join(dmin)}" if dmin else "")
            log(f"  {m['id']}: {note}")
            allv = num + den + dmin
            mnames = [n[:-1] + "M" for n in allv]
            for gname, geo in G.items():
                try:
                    vals = fetch(end, ds, allv + mnames, geo, key)
                except Exception as e:
                    log(f"    {gname}: not available ({str(e)[:80]})")
                    continue
                if vals is None:
                    continue
                E = {n: vals.get(n) for n in allv}
                Mo = {n: vals.get(n[:-1] + "M") for n in allv}
                ne, nm = sum_est(E, num), sum_moe(Mo, num)
                if m["kind"] == "value":
                    add(m["id"], gname, period, ne, nm, f"ACS 5-year {period}", note)
                    continue
                de, dm = sum_est(E, den), sum_moe(Mo, den)
                if dmin:
                    me, mm = sum_est(E, dmin), sum_moe(Mo, dmin)
                    de = None if None in (de, me) else de - me
                    dm = None if None in (dm, mm) else math.sqrt(dm ** 2 + mm ** 2)
                est = ne / de * 100 if None not in (ne, de) and de else None
                moe = share_moe(ne, de, nm, dm)
                add(m["id"], gname, period, est, moe * 100 if moe is not None else None, f"ACS 5-year {period}", note)


# ---------------------------------------------------------------- boundaries
def esri_to_geojson(feat):
    rings = feat["geometry"]["rings"]
    return {"type": "Feature", "properties": feat["attributes"],
            "geometry": {"type": "Polygon", "coordinates": rings}}


def pull_boundaries(place_code):
    log("Boundaries (TIGERweb, Census 2020 vintage)")
    layers = get_json(TIGER, {"f": "json"})["layers"]
    def layer_id(rx):
        hits = [l for l in layers if re.search(rx, l["name"], re.I)]
        if not hits:
            raise LookupError(f"No TIGERweb layer matching /{rx}/")
        return hits[0]["id"], hits[0]["name"]
    feats = []
    for role, rx, geoid in (("city", r"^Incorporated Places$", M.STATE_FIPS + place_code),
                            ("tract", r"^Census Tracts$", M.STATE_FIPS + M.COUNTY_FIPS + M.TRACT)):  # map frame
        lid, lname = layer_id(rx)
        q = {"where": f"GEOID='{geoid}'", "outFields": "GEOID,NAME", "outSR": "4326", "returnGeometry": "true"}
        try:
            js = get_json(f"{TIGER}/{lid}/query", {**q, "f": "geojson"})
            fs = js.get("features", []) if js else []
        except Exception:
            fs = []
        if not fs:
            js = get_json(f"{TIGER}/{lid}/query", {**q, "f": "json"})
            fs = [esri_to_geojson(f) for f in (js or {}).get("features", [])]
        if len(fs) != 1:
            log(f"  {role}: expected 1 feature for GEOID {geoid} in '{lname}', got {len(fs)}")
            continue
        f = fs[0]
        f["properties"] = {"role": role, "geoid": geoid, "name": f["properties"].get("NAME"), "layer": lname}
        feats.append(f)
        log(f"  {role}: {f['properties']['name']} (GEOID {geoid}) from layer '{lname}'")
    # Every tract the city touches, with the share of city area in each.
    city = [f for f in feats if f["properties"]["role"] == "city"]
    if city:
        try:
            from shapely.geometry import shape
            cg = shape(city[0]["geometry"])
            minx, miny, maxx, maxy = cg.bounds
            lid, lname = layer_id(r"^Census Tracts$")
            q = {"geometry": f"{minx},{miny},{maxx},{maxy}", "geometryType": "esriGeometryEnvelope",
                 "inSR": "4326", "spatialRel": "esriSpatialRelIntersects", "outFields": "GEOID,NAME",
                 "outSR": "4326", "returnGeometry": "true", "f": "geojson"}
            js = get_json(f"{TIGER}/{lid}/query", q) or {}
            fs = js.get("features") or [esri_to_geojson(f) for f in (get_json(f"{TIGER}/{lid}/query", {**q, "f": "json"}) or {}).get("features", [])]
            for f in fs:
                share = shape(f["geometry"]).intersection(cg).area / cg.area * 100
                gid = f["properties"].get("GEOID")
                if share < 0.5:
                    continue
                log(f"  city area in tract {f['properties'].get('NAME')} ({gid}): {share:.1f}%")
                if gid != M.STATE_FIPS + M.COUNTY_FIPS + M.TRACT:
                    f["properties"] = {"role": "tract_other", "geoid": gid, "name": f["properties"].get("NAME"),
                                       "city_share": round(share, 1), "layer": lname}
                    feats.append(f)
                else:
                    [x for x in feats if x["properties"]["role"] == "tract"][0]["properties"]["city_share"] = round(share, 1)
        except ImportError:
            log("  shapely not installed; skipped tract overlap (pip install -r requirements.txt)")
        except Exception as e:
            log(f"  tract overlap failed: {e}")
    return {"type": "FeatureCollection", "features": feats}


# ---------------------------------------------------------------- where people live
def city_split(key, place_code, city_feature):
    """2020 counts for city blocks in each tract: people, group quarters, households."""
    log("City split by tract (2020 blocks)")
    out = {}
    try:
        from shapely.geometry import shape
    except ImportError:
        log("  shapely not installed; skipped")
        return out
    cg = shape(city_feature["geometry"])
    layers = get_json(TIGER, {"f": "json"})["layers"]
    hits = [l for l in layers if re.search(r"^Census Blocks$", l["name"], re.I)]
    if not hits:
        log("  no 'Census Blocks' layer; layers are: " + ", ".join(l["name"] for l in layers)[:300])
        return out
    lid = hits[0]["id"]
    minx, miny, maxx, maxy = cg.bounds
    q = {"geometry": f"{minx},{miny},{maxx},{maxy}", "geometryType": "esriGeometryEnvelope", "inSR": "4326",
         "spatialRel": "esriSpatialRelIntersects", "outFields": "GEOID", "outSR": "4326",
         "returnGeometry": "true", "f": "geojson"}
    js = get_json(f"{TIGER}/{lid}/query", q) or {}
    fs = js.get("features") or [esri_to_geojson(f) for f in (get_json(f"{TIGER}/{lid}/query", {**q, "f": "json"}) or {}).get("features", [])]
    in_city = set()
    for f in fs:
        g = shape(f["geometry"])
        if g.representative_point().within(cg):
            in_city.add(str(f["properties"].get("GEOID")))
    log(f"  {len(fs)} blocks near the city, {len(in_city)} inside it")
    ds = "dec/pl"
    try:
        pop = match(group_vars(2020, ds, find_group(2020, ds, r"^race$"), acs=False), ["TOTAL"])[0]
        gq = match(group_vars(2020, ds, find_group(2020, ds, r"^group quarters population by (major )?group quarters type$"), acs=False), ["TOTAL"])[0]
        hh = match(group_vars(2020, ds, find_group(2020, ds, r"^occupancy status$"), acs=False), [r"^occupied$"])[0]
    except Exception as e:
        log(f"  variable lookup failed: {e}")
        return out
    for label, tract in M.TRACTS.items():
        js = get_json(f"{API}/2020/{ds}", {"get": f"{pop},{gq},{hh}", "for": "block:*",
                                          "in": f"state:{M.STATE_FIPS} county:{M.COUNTY_FIPS} tract:{tract}", "key": key})
        if not js:
            continue
        h = js[0]
        t = {"blocks": 0, "population": 0, "group_quarters": 0, "households": 0}
        for r in js[1:]:
            geoid = r[h.index("state")] + r[h.index("county")] + r[h.index("tract")] + r[h.index("block")]
            if geoid in in_city:
                t["blocks"] += 1
                t["population"] += int(r[h.index(pop)])
                t["group_quarters"] += int(r[h.index(gq)])
                t["households"] += int(r[h.index(hh)])
        t["household_population"] = t["population"] - t["group_quarters"]
        out[label] = t
        log(f"  {label}: {t}")
    tot = sum(v["households"] for v in out.values()) or 1
    for v in out.values():
        v["share_of_city_households"] = round(v["households"] / tot * 100, 1)
    return out


def env_value(name):
    v = os.environ.get(name)
    env = ROOT / ".env"
    if not v and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(name + "="):
                v = line.split("=", 1)[1].strip().strip('"')
    return v


def geocode_city_hall():
    M.CITY_HALL_ADDRESS = M.CITY_HALL_ADDRESS or env_value("CITY_HALL_ADDRESS") or ""
    if not M.CITY_HALL_ADDRESS:
        log("City Hall: no address set (add CITY_HALL_ADDRESS=... to .env); skipped")
        return None
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    try:
        js = get_json(url, {"address": M.CITY_HALL_ADDRESS, "benchmark": "Public_AR_Current",
                            "vintage": "Census2020_Current", "format": "json"})
        m = js["result"]["addressMatches"]
        if not m:
            log(f"City Hall: no geocoder match for '{M.CITY_HALL_ADDRESS}'")
            return None
        c, geo = m[0]["coordinates"], m[0]["geographies"]
        tract = geo.get("Census Tracts", [{}])[0].get("GEOID")
        log(f"City Hall: {m[0]['matchedAddress']} -> tract {tract}")
        return {"address": m[0]["matchedAddress"], "lon": c["x"], "lat": c["y"], "tract": tract}
    except Exception as e:
        log(f"City Hall: geocoder failed ({str(e)[:120]})")
        return None


# ---------------------------------------------------------------- outputs
def build_series():
    labels = {m["id"]: m for m in M.DEC_MEASURES + M.DEC_DERIVED + M.ACS_MEASURES}
    out = {}
    for r in ROWS:
        m = out.setdefault(r["measure"], {"label": labels[r["measure"]]["label"],
                                          "unit": labels[r["measure"]].get("unit", "count"),
                                          "universe": labels[r["measure"]].get("universe"),
                                          "note": labels[r["measure"]].get("note"),
                                          "source": "ACS 5-year" if r["source"].startswith("ACS") else "Decennial Census",
                                          "geos": {}})
        m["geos"].setdefault(r["geo"], []).append(
            {"period": r["period"], "est": None if r["est"] is None else round(r["est"], 2),
             "moe": None if r["moe"] is None else round(r["moe"], 2)})
    for m in out.values():
        for g in m["geos"].values():
            g.sort(key=lambda x: x["period"])
        c, k = m["geos"].get("city", []), m["geos"].get("county", [])
        if c and k and c[-1]["period"] == k[-1]["period"]:
            d = differs(c[-1], k[-1])
            m["city_vs_county"] = None if d is None else ("different" if d else "not different")
    return out


def main():
    key = api_key()
    DATA.mkdir(exist_ok=True)
    pull_decennial(key)
    derive_decennial()
    pull_acs(key)
    place2020 = resolve_place(2020, "dec/dhc", key)
    try:
        bounds = pull_boundaries(place2020)
    except Exception as e:
        log(f"  boundaries failed: {e}")
        bounds = {"type": "FeatureCollection", "features": []}
    city_f = [f for f in bounds["features"] if f["properties"]["role"] == "city"]
    split = city_split(key, place2020, city_f[0]) if city_f else {}
    hall = geocode_city_hall()

    with open(DATA / "series.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["measure", "geo", "period", "est", "moe", "source", "variables"])
        w.writeheader()
        w.writerows(ROWS)
    (DATA / "boundaries.geojson").write_text(json.dumps(bounds))
    series = build_series()
    stamp = datetime.date.today().isoformat()
    block = {"pulled": stamp, "measures": series, "boundaries": bounds, "split": split, "city_hall": hall}
    (DATA / "embed_block.js").write_text(
        "/* ===== WV_SERIES: generated by pull/pull_data.py on " + stamp + ". Paste over the old block. ===== */\n"
        "var WV_SERIES = " + json.dumps(block, separators=(",", ":")) + ";\n/* ===== end WV_SERIES ===== */\n")
    (DATA / "pull_log.txt").write_text("\n".join(LOG) + "\n")
    missing = [l for l in LOG if "MISSING" in l or "SKIP" in l]
    print(f"\nDone: {len(ROWS)} values, {len(bounds['features'])} boundaries, {len(missing)} gaps (see data/pull_log.txt).")


if __name__ == "__main__":
    main()
