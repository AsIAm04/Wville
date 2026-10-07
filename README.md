# Wrightsville Community Conditions Dashboard

Public data dashboard for the City of Wrightsville, Arkansas. Built by As-I-Am Consulting Group; owned by the City.

## What is here

| Path | What it is |
| --- | --- |
| `embed/wrightsville-dashboard-embed.html` | The dashboard. Paste the whole file into a Squarespace Code Block (HTML mode). |
| `pull/pull_data.py` | Pulls Census data and city/tract boundaries. |
| `pull/measures.py` | The list of measures, geographies, and time periods. Edit this to add a measure. |
| `data/` | Output of the last pull. Commit it so every change is on record. |
| `tests/` | Offline checks that run without internet or an API key. |

## One-time setup

1. Install Python 3.9 or newer.
2. In this folder, run `pip install -r requirements.txt`.
3. Get a free Census API key at https://api.census.gov/data/key_signup.html.
4. Copy `.env.example` to `.env` and put the key after `CENSUS_API_KEY=`.
   `.env` is listed in `.gitignore`, so the key never goes into the repository.

## Each refresh

1. Run `python pull/pull_data.py` from this folder.
2. Read `data/pull_log.txt`. It lists every Census variable used with its published label.
   Lines starting with `MISSING` or `SKIP` are gaps; the dashboard shows those measures as pending.
3. Open `data/embed_block.js`, copy all of it, and paste it over the `WV_SERIES` block in the embed file
   (between the `WV_SERIES` and `end WV_SERIES` comment lines).
4. Paste the updated embed file into the Squarespace Code Block.
5. Commit `data/` and the embed file with a message such as `Refresh: ACS 2020-2024`.

## Rules the dashboard follows

- Condition measures use people in households only. The official count of 1,542 includes 909 people at the Department of Correction unit.
- Survey (ACS) trends compare only five-year periods that do not overlap: 2005-2009, 2010-2014, 2015-2019, 2020-2024.
- Survey values with a margin of error above 30% of the estimate are withheld; 15% to 30% are marked "Use with caution."
- "Differs from county" means the 90% confidence intervals support a real difference.
- Median household income is not adjusted for inflation; the dashboard says so next to the figure.

## Checks

- Unit checks: `python -c "import sys; sys.path.insert(0,'tests'); import test_pull as T; [getattr(T,n)() for n in dir(T) if n.startswith('test_')]"`
- `python tests/mock_run.py` runs the full pull against fake responses.

## Not yet covered by the pull script

HUD low and moderate income data, USDA food access, CDC PLACES and life expectancy, HRSA shortage areas, DOE energy burden, FCC broadband, FEMA flood and risk data, SVI, EJI, LEHD jobs, EPA wastewater compliance records, and Opportunity Zone status. These are entered by hand in the `WV_DATA` block until scripts are added.
