"""Facebook dump service — subprocess, zip ve snapshot işlemleri."""
import io, json, os, subprocess, time, zipfile
from pathlib import Path
from app.services.base import BaseService

_HERE = Path(__file__).resolve()
FB_ROOT = str(_HERE.parents[2])
FB_CWD = "/app" if os.path.isdir("/app") else FB_ROOT
FB_PY = __import__("sys").executable or "python"


class FbDumpService(BaseService):
    def __init__(self):
        super().__init__(cache_ttl=60)

    def _outdir(self, username: str) -> str:
        return f"/tmp/fb_{username}"

    def _validate_output(self, path: str) -> bool:
        return os.path.isdir(path) and any(
            f != "snapshot.json" for f in os.listdir(path)
        )

    async def run_dump(self, username: str, limit: int = 40,
                       min_bytes: int = 4096, debug: str = "") -> dict:
        outdir = self._outdir(username)
        Path(outdir).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["FB_MIN_BYTES"] = str(min_bytes)
        if debug.strip():
            env["FB_DEBUG"] = "1"

        cmd = [FB_PY, "-m", "app.tools.fb_dump", username, outdir, str(limit)]
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd, cwd=FB_CWD, capture_output=True, text=True,
                env=env, timeout=300
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout", "outdir": outdir,
                    "returncode": -1, "stdout": "", "elapsed": 300.0}

        elapsed = round(time.time() - t0, 1)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
            "elapsed": elapsed,
            "outdir": outdir,
        }

    async def build_zip(self, outdir: str) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name in os.listdir(outdir):
                if name == "snapshot.json":
                    continue
                z.write(os.path.join(outdir, name), arcname=name)
        return buf.getvalue()

    async def read_snapshot(self, path: str) -> dict:
        snap_path = os.path.join(path, "snapshot.json")
        if not os.path.exists(snap_path):
            return {}
        try:
            with open(snap_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def list_images(self, outdir: str) -> list:
        """outdir'deki görselleri boyuta göre sıralı listele."""
        import glob
        files = sorted(
            glob.glob(os.path.join(outdir, "*.*")),
            key=os.path.getsize, reverse=True
        )
        result = []
        for fp in files:
            name = os.path.basename(fp)
            if name == "snapshot.json":
                continue
            result.append({
                "name": name,
                "size": os.path.getsize(fp),
                "url": f"/fb/file/{os.path.basename(outdir).removeprefix('fb_')}/{name}",
            })
        return result

    def cookie_summary(self) -> dict:
        path = os.path.join(FB_CWD, "app", "secrets", "fb.cookie")
        info = {"exists": os.path.isfile(path), "path": path, "keys": {}}
        try:
            if not info["exists"]:
                return info
            txt = open(path, "rb").read().decode("utf-8", "ignore").strip()
            jar = {}
            if txt.startswith("# Netscape") or "\t" in txt:
                for ln in txt.splitlines():
                    ln = ln.strip()
                    if not ln or ln.startswith("#"):
                        continue
                    pr = ln.split("\t")
                    if len(pr) >= 7:
                        jar[pr[-2].strip()] = pr[-1].strip()
            else:
                for tok in txt.split(";"):
                    tok = tok.strip()
                    if "=" in tok:
                        k, v = tok.split("=", 1)
                        jar[k.strip()] = v.strip()

            def mask(v):
                v = str(v)
                if len(v) <= 6:
                    return "***"
                return v[:3] + "***" + v[-3:]

            for k in ("c_user", "xs", "datr", "sb", "locale"):
                if k in jar:
                    info["keys"][k] = mask(jar[k])
        except Exception as e:
            info["error"] = str(e)
        return info

    def docker_info(self) -> str:
        try:
            res = subprocess.run(
                ["docker", "system", "df"],
                capture_output=True, text=True, timeout=4
            )
            return res.stdout.strip()
        except Exception:
            return "(docker bulunamadı ya da erişilemiyor)"


    # ── HTML render helpers ───────────────────────────────────────────────────

    def _html_page(self, body: str, title: str = "FB Dump") -> str:
        import html as _html
        return f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<title>{_html.escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
body{{font-family:ui-sans-serif,system-ui,Segoe UI,Arial;margin:24px}}
.wrap{{max-width:1100px;margin:0 auto}}h1{{font-size:22px;margin-bottom:12px}}
form{{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin:16px 0 20px}}
label{{display:flex;flex-direction:column;font-size:13px;gap:6px}}
input[type=text],input[type=number]{{padding:8px 10px;border:1px solid #ddd;border-radius:8px;min-width:220px}}
button{{padding:10px 14px;border:0;border-radius:10px;background:#111827;color:#fff;cursor:pointer}}
table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #eee;padding:8px;text-align:left;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-top:16px}}
.card{{border:1px solid #eee;border-radius:12px;overflow:hidden}}
.card img{{width:100%;display:block}}.meta{{padding:8px;font-size:12px;color:#444;display:flex;justify-content:space-between;gap:10px}}
.muted{{color:#666;font-size:12px}}.row{{display:flex;gap:12px;align-items:center;margin:8px 0}}
.pill{{background:#f1f5f9;color:#0f172a;padding:2px 8px;border-radius:999px;font-size:12px}}
</style></head><body><div class="wrap">{body}</div></body></html>"""

    def render_run_result(self, username: str, proc_result: dict,
                          snap: dict, images: list) -> str:
        import html as _html
        seeds_rows = ""
        for s in (snap.get("seeds") or [])[:30]:
            seeds_rows += (
                f"<tr><td>{_html.escape(str(s.get('seed','')))}</td>"
                f"<td>{_html.escape(str(s.get('final','')))}</td>"
                f"<td>{_html.escape(str(s.get('login','')))}</td>"
                f"<td>{_html.escape(str(s.get('len','')))}</td>"
                f"<td>{_html.escape(str(s.get('n_imgs','')))}</td>"
                f"<td>{_html.escape(str(s.get('n_details','')))}</td></tr>"
            )
        seeds_html = (
            f"<table><thead><tr><th>seed</th><th>final</th><th>login</th>"
            f"<th>len</th><th>n_imgs</th><th>n_details</th></tr></thead>"
            f"<tbody>{seeds_rows}</tbody></table>"
        ) if seeds_rows else "<p class='muted'>Seed bilgisi bulunamadı.</p>"

        cards = "".join(
            f"<div class='card'><a href='{it['url']}' target='_blank'>"
            f"<img src='{it['url']}' loading='lazy'/></a>"
            f"<div class='meta'><span>{_html.escape(it['name'])}</span>"
            f"<span class='pill'>{it['size']:,} B</span></div></div>"
            for it in images[:200]
        )
        grid = f"<div class='grid'>{cards}</div>" if cards else "<p class='muted'>Görsel bulunamadı.</p>"

        rc = proc_result.get("returncode", "?")
        elapsed = proc_result.get("elapsed", 0)
        stdout = _html.escape((proc_result.get("stdout") or "").strip())
        body = (
            f"<h1>Sonuç — {_html.escape(username)}</h1>"
            f"<div class='row'><a class='pill' href='/fb'>← Yeni Arama</a>"
            f"<a class='pill' href='/fb/zip/{_html.escape(username)}' target='_blank'>ZIP indir</a></div>"
            f"<p class='muted'>rc={rc} • süre={elapsed}s</p>"
            f"<pre class='muted' style='white-space:pre-wrap;background:#f8fafc;padding:8px;border-radius:8px'>{stdout}</pre>"
            f"<p><b>saved</b>: {len(images)}</p>"
            f"<h3>Seeds</h3>{seeds_html}<h3>Görseller</h3>{grid}"
        )
        return self._html_page(body, title=f"FB Dump — {username}")
