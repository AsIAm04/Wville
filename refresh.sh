#!/bin/bash
# One command for every refresh: pull data, update the embed, sync GitHub.
# Run from this folder:  ./refresh.sh
set -e
cd "$(dirname "$0")"
REPO="https://github.com/AsIAm04/Wville.git"

echo "== 1 of 4: checks"
[ -f .env ] || { echo "Missing .env. Run: cp .env.example .env && open -e .env  (paste your Census key, save)"; exit 1; }
[ -f .gitignore ] || { echo "Missing .gitignore; unzip the full package again."; exit 1; }
if [ -z "$SKIP_GH" ]; then
  command -v gh >/dev/null || { echo "GitHub CLI not installed. Run: brew install gh   then: gh auth login"; exit 1; }
  gh auth status >/dev/null 2>&1 || { echo "Not signed in to GitHub. Run: gh auth login"; exit 1; }
  gh auth setup-git >/dev/null 2>&1
fi

echo "== 2 of 4: Python environment"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt

echo "== 3 of 4: pull data and update the embed"
[ -n "$SKIP_PULL" ] || python pull/pull_data.py
python pull/update_embed.py

echo "== 4 of 4: sync GitHub"
if [ ! -d .git ]; then
  git init -q -b main
  git remote add origin "${REPO_OVERRIDE:-$REPO}"
fi
git fetch -q origin main
git reset -q --mixed origin/main          # match GitHub's history; keep local files as they are
if [ -z "$(git config user.name)" ] && [ -z "$SKIP_GH" ]; then
  LOGIN=$(gh api user -q .login)
  git config user.name "$LOGIN"; git config user.email "$LOGIN@users.noreply.github.com"
fi
git add -A                                  # adds new files, records moves and deletions
git ls-files -ci --exclude-standard -z | xargs -0 git rm -q --cached --ignore-unmatch --   # untrack ignored files (e.g. .DS_Store)
if git ls-files | grep -qE '(^|/)\.env$|^\.venv/'; then
  echo "Stopped: .env or .venv would be uploaded. Nothing was pushed."; exit 1
fi
if git diff --cached --quiet; then
  echo "GitHub already up to date."
else
  git commit -q -m "Refresh $(date +%Y-%m-%d)"
  git push -q origin main
  echo "Pushed to GitHub."
fi
echo
echo "Done. Last step: paste embed/wrightsville-dashboard-embed.html into the Squarespace Code Block."
echo "Gaps and table choices are listed in data/pull_log.txt."
