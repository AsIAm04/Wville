# Wrightsville Community Conditions Dashboard

Public data dashboard for the City of Wrightsville, Arkansas. Built by As-I-Am Consulting Group; owned by the City.

## What is here

| Path | What it is |
| --- | --- |
| `embed/wrightsville-dashboard-embed.html` | The dashboard. Paste the whole file into a Squarespace Code Block (HTML mode). |
| `refresh.sh` | Runs everything: pull, embed update, GitHub sync. |
| `pull/pull_data.py` | Pulls Census data and city/tract boundaries. |
| `pull/update_embed.py` | Writes the latest pull into the embed file. |
| `pull/measures.py` | The list of measures, geographies, and time periods. Edit this to add a measure. |
| `data/` | Output of the last pull. Commit it so every change is on record. |
| `tests/` | Offline checks that run without internet or an API key. |

## One-time setup (Mac)

1. Unzip this folder somewhere on your computer, for example `~/Downloads/wrightsville-dashboard`.
2. Get a free Census API key at https://api.census.gov/data/key_signup.html.
3. In Terminal, run one line at a time:
   ```
   cd ~/Downloads/wrightsville-dashboard
   cp .env.example .env
   open -e .env
   ```
   Paste the key after `CENSUS_API_KEY=` (no spaces or quotes), then save with Cmd + S.
4. Create a private Python environment and install what the script needs:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   Your Terminal prompt now starts with `(.venv)`.

**Never upload `.env` or `.venv` to GitHub.** `.gitignore` only protects you when using git from the
command line; GitHub's web upload page ignores it. In Finder, Cmd + Shift + . (period) shows hidden files
so you can see what you are dragging.

## Each refresh: one command

```
cd ~/Downloads/wrightsville-dashboard
./refresh.sh
```

It pulls the data, writes it into the embed, and syncs GitHub (adds, moves, and deletes files to match
this folder). It refuses to push if `.env` or `.venv` would be uploaded. The only manual step left is
pasting `embed/wrightsville-dashboard-embed.html` into the Squarespace Code Block.

First time only, sign in to GitHub from Terminal:
```
brew install gh
gh auth login
```
Answer: GitHub.com, HTTPS, Yes (authenticate Git), Login with a web browser.

## Rules the dashboard follows

- Condition measures use people in households only. The official count of 1,542 includes 909 people at the Department of Correction unit.
- Survey (ACS) trends compare only five-year periods that do not overlap: 2005-2009, 2010-2014, 2015-2019, 2020-2024.
- Survey values with a margin of error above 30% of the estimate are withheld; 15% to 30% are marked "Use with caution."
- "Differs from county" means the 90% confidence intervals support a real difference.
- Median household income is not adjusted for inflation; the dashboard says so next to the figure.
- Trend charts drop survey periods that fail the reliability rule and say how many were withheld.
- A row shows a pulled value as current only if it is from the latest period for its source; otherwise the hand-entered, verified value stays.

## Checks

- Unit checks: `python -c "import sys; sys.path.insert(0,'tests'); import test_pull as T; [getattr(T,n)() for n in dir(T) if n.startswith('test_')]"`
- `python tests/mock_run.py` runs the full pull against fake responses.

## Not yet covered by the pull script

HUD low and moderate income data, USDA food access, CDC PLACES and life expectancy, HRSA shortage areas, DOE energy burden, FCC broadband, FEMA flood and risk data, SVI, EJI, LEHD jobs, EPA wastewater compliance records, and Opportunity Zone status. These are entered by hand in the `WV_DATA` block until scripts are added.
