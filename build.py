# Merges every data\YYYY-MM-DD.json into template.html -> build\index.html (counts only, no PHI)
import json, glob, os
root = os.path.dirname(os.path.abspath(__file__))
snaps = {}
for f in sorted(glob.glob(os.path.join(root, "data", "*.json"))):
    snaps[os.path.splitext(os.path.basename(f))[0]] = json.load(open(f, encoding="utf-8"))
if not snaps:
    raise SystemExit("No data files found in data\\")
html = open(os.path.join(root, "template.html"), encoding="utf-8").read()
html = html.replace("/*__DATA__*/", "window.PREAUTH_DATA=" + json.dumps({"snapshots": snaps}) + ";")
os.makedirs(os.path.join(root, "build"), exist_ok=True)
open(os.path.join(root, "build", "index.html"), "w", encoding="utf-8").write(html)
print(f"Built with {len(snaps)} snapshot(s): {', '.join(snaps)}")
