"""Render SVG assets frozen at a given time to PNG (headless Chrome).

usage: python scripts/snap.py OUTDIR T [name.svg ...]
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

out, t = sys.argv[1], float(sys.argv[2])
names = sys.argv[3:] or sorted(f for f in os.listdir(os.path.join(ROOT, "profile", "assets")) if f.endswith(".svg"))
os.makedirs(out, exist_ok=True)
for name in names:
    src = open(os.path.join(ROOT, "profile", "assets", name)).read()
    w = int(src.split('width="')[1].split('"')[0])
    h = int(src.split('height="')[1].split('"')[0])
    html = f"""<!doctype html><html><body style="margin:0;background:#0d1117">{src}
<script>
const s=document.querySelector('svg');s.pauseAnimations();s.setCurrentTime({t});
document.getAnimations().forEach(a=>{{a.pause();a.currentTime={t * 1000};}});
</script></body></html>"""
    page = os.path.join(out, name + ".html")
    open(page, "w").write(html)
    png = os.path.join(out, f"{name[:-4]}_{t:g}.png")
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", f"--window-size={w},{h}",
                    "--virtual-time-budget=300", f"--screenshot={png}", "file://" + page],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    print(png)
