"""Insert data/embed_block.js into the embed file, replacing the old WV_SERIES block."""
import pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
emb = ROOT / "embed" / "wrightsville-dashboard-embed.html"
blk = (ROOT / "data" / "embed_block.js").read_text()
html = emb.read_text()
pat = re.compile(r"/\* ===== WV_SERIES:.*?/\* ===== end WV_SERIES ===== \*/\n?", re.S)
if len(pat.findall(html)) != 1:
    sys.exit("Could not find exactly one WV_SERIES block in the embed file; nothing changed.")
emb.write_text(pat.sub(lambda _: blk if blk.endswith("\n") else blk + "\n", html))
print("Embed updated with the latest pull.")
