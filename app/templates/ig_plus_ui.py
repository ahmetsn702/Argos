# app/templates/ig_plus_ui.py
# -*- coding: utf-8 -*-
"""Static HTML pages served by the IG tester router.

Each function returns a complete HTML document. They are kept as plain
strings (rather than Jinja templates) because they are self-contained and
small enough to ship inline.
"""


def ig_bio_ui() -> str:
    return """<!doctype html>
<meta charset="utf-8">
<title>IG BIO Tester</title>
<style>
body{font:14px system-ui,Segoe UI,Arial;margin:24px;max-width:900px;background:#0b0b0f;color:#ddd}
input,button{font:14px inherit;padding:8px}
code,pre{background:#111;color:#eee;padding:12px;border-radius:8px;display:block;white-space:pre-wrap}
.card{border:1px solid #333;border-radius:12px;padding:16px;margin-top:16px;background:#0f1117}
small{color:#9aa}
</style>
<h2>IG BIO Tester</h2>
<p>Kullanıcı adı gir → <code>/tester/ig-bio</code> çağrılır, JSON aşağıda görünür.</p>
<input id="u" placeholder="ahmettssyn" value="ahmettssyn">
<button onclick="run()">Get BIO</button>
<div id="out" class="card"><small>Sonuç burada…</small></div>
<script>
async function run(){
  const user=document.getElementById('u').value.trim();
  const fd = new URLSearchParams({user});
  const r = await fetch('/tester/ig-bio',{
    method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:fd
  });
  const j = await r.json();
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(j,null,2);
  const out = document.getElementById('out');
  out.innerHTML=''; out.appendChild(pre);
}
</script>"""


def ig_bio_ui_pro() -> str:
    return """<!doctype html><meta charset="utf-8">
<title>IG BIO — Pro</title>
<style>
  :root{--fg:#0a2540;--muted:#64748b}
  body{font-family:system-ui,Segoe UI,Arial;margin:28px;color:#111}
  .wrap{max-width:820px}
  .top{display:flex;gap:16px;align-items:center;margin-bottom:12px}
  .name{font-size:24px;font-weight:800;color:var(--fg)}
  .handle{font-weight:600;color:var(--muted)}
  .stats{margin-top:4px;font-size:15px;color:#222}
  .stats b{font-weight:700}
  .card{border:1px solid #e5e7eb;border-radius:16px;padding:18px;box-shadow:0 4px 18px rgba(0,0,0,.06)}
  .bio{white-space:pre-wrap;line-height:1.35;margin-top:8px}
  .links{margin-top:10px}
  .links a{color:#2563eb;text-decoration:none}
  .pp{border-radius:16px;width:86px;height:86px;object-fit:cover}
</style>
<div class="wrap">
  <div class="top" id="top" style="display:none"></div>
  <div class="card">
    <form onsubmit="run(event)" style="display:flex;gap:10px;margin-bottom:12px">
      <input id="u" placeholder="instagram kullanıcı adı" value="ahmettssyn"
             style="flex:1;padding:10px 12px;border:1px solid #cbd5e1;border-radius:10px;font-size:16px">
      <button style="padding:10px 14px;border:0;background:#2563eb;color:white;border-radius:10px;font-size:16px;font-weight:700">
        Getir
      </button>
    </form>
    <div id="out" class="bio"></div>
    <div id="links" class="links"></div>
  </div>
</div>
<script>
async function run(ev){
  ev && ev.preventDefault();
  const u = document.getElementById('u').value.trim();
  if(!u) return;
  const fd = new URLSearchParams(); fd.set('user', u);
  const r = await fetch('/tester/ig-bio',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:fd});
  const j = await r.json();
  const p = j.profile || {};
  const top = document.getElementById('top');
  top.innerHTML = `
    ${p.profile_pic_url?`<img class="pp" src="${p.profile_pic_url}" alt="">`:''}
    <div>
      <div class="name">${p.full_name||''} <span class="handle">@${p.username||''}</span></div>
      <div class="stats"><b>Takipçi:</b> ${p.followers ?? '-'} · <b>Takip:</b> ${p.following ?? '-'}</div>
    </div>`;
  top.style.display = 'flex';
  document.getElementById('out').textContent = p.biography || '';
  const ig = p.username ? `https://www.instagram.com/${p.username}/` : null;
  document.getElementById('links').innerHTML = ig ? `<a href="${ig}" target="_blank">instagram.com/${p.username}</a>` : '';
}
run();
</script>"""


def tester_pro() -> str:
    return """<!doctype html><meta charset="utf-8">
<title>Footprint — PRO</title>
<style>
  :root{
    --blue:#1e40af; --blue2:#3b82f6; --ink:#0f172a; --muted:#64748b; --card:#ffffff;
    --ring:rgba(59,130,246,.35); --bd:#e5e7eb;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:system-ui,Segoe UI,Arial;color:var(--ink);background:#f8fafc}
  header{background:linear-gradient(135deg,var(--blue2),var(--blue));color:#fff;padding:18px 22px}
  header .brand{font-size:18px;font-weight:800;letter-spacing:.3px}
  main{max-width:980px;margin:18px auto;padding:0 18px}
  .bar{display:flex;gap:10px}
  input[type=text]{flex:1;padding:10px 12px;border:1px solid var(--bd);border-radius:12px;font-size:16px;outline:none}
  input[type=text]:focus{box-shadow:0 0 0 4px var(--ring);border-color:var(--blue2)}
  button{padding:10px 14px;border:0;background:var(--blue2);color:#fff;border-radius:12px;font-size:16px;font-weight:700;cursor:pointer}
  .hero{display:none;align-items:center;gap:16px;margin-top:14px;background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:16px;
        box-shadow:0 10px 30px rgba(0,0,0,.07)}
  .pp{width:84px;height:84px;border-radius:18px;object-fit:cover}
  .name{font-size:22px;font-weight:800}
  .handle{font-weight:700;color:#e2e8f0;background:rgba(255,255,255,.2);padding:4px 8px;border-radius:999px;margin-left:8px}
  .stats{margin-top:4px;opacity:.9}
  .cards{display:grid;grid-template-columns:1fr;gap:12px;margin-top:14px}
  @media(min-width:900px){ .cards{grid-template-columns:1fr 1fr} }
  .card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:14px}
  .card h3{margin:0 0 8px 0;font-size:16px}
  .bio{white-space:pre-wrap;line-height:1.35}
  .links a{display:inline-block;margin-right:10px;color:#2563eb;text-decoration:none}
  .item{padding:8px;border:1px dashed #e2e8f0;border-radius:10px;margin-top:8px}
  details{margin-top:12px}
</style>
<header>
  <div class="brand">FOOTPRINT — Tester (PRO)</div>
</header>
<main>
  <div class="bar">
    <input id="u" type="text" placeholder="kullanıcı (ör. ahmettssyn)" />
    <button onclick="run()">Ara</button>
  </div>

  <section id="hero" class="hero">
    <img id="pp" class="pp" alt="">
    <div>
      <div class="name" id="nm">—</div>
      <div class="stats" id="st">—</div>
      <div class="links" id="ln">—</div>
    </div>
  </section>

  <section class="cards">
    <div class="card">
      <h3>Biyografi</h3>
      <div id="bio" class="bio">—</div>
    </div>
    <div class="card">
      <h3>Google (IG/X) isabetleri</h3>
      <div id="gcs">—</div>
    </div>
  </section>

  <details>
    <summary>Raw JSON</summary>
    <pre id="raw" style="white-space:pre-wrap;background:#0b1220;color:#dbeafe;border-radius:12px;padding:10px;overflow:auto;max-height:340px"></pre>
  </details>
</main>

<script>
function q(k){return document.querySelector(k)}
function esc(s){return (s??"").toString().replace(/[&<>]/g,m=>({ "&":"&amp;","<":"&lt;",">":"&gt;"}[m]))}

async function run(){
  const u = q('#u').value.trim(); if(!u) return;
  const fd = new URLSearchParams(); fd.set('user', u); fd.set('with_bio','1'); fd.set('prefer_native','1');
  const r  = await fetch('/tester/compare-ig-x-plus',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:fd});
  const j  = await r.json();

  q('#raw').textContent = JSON.stringify(j,null,2);

  const p = (j.profile && j.profile.ig) ? j.profile.ig : {};
  const full = p.full_name || ''; const handle = p.username ? '@'+p.username : '';
  const foll = (p.followers ?? '-'); const folg = (p.following ?? '-');

  if(p.profile_pic_url){ q('#pp').src = p.profile_pic_url }
  q('#nm').innerHTML = esc(full) + (handle?` <span class="handle">${esc(handle)}</span>`:'');
  q('#st').innerHTML = `<b>Takipçi:</b> ${esc(foll)} · <b>Takip:</b> ${esc(folg)}`;
  const igLink = p.username ? `https://www.instagram.com/${p.username}/` : null;
  const xLinks = (j.links && j.links.x) ? j.links.x : [];
  q('#ln').innerHTML = [
    igLink ? `<a target="_blank" href="${igLink}">instagram.com/${esc(p.username)}</a>` : '',
    ...xLinks.map(h=>`<a target="_blank" href="${h}">${esc(h.replace('https://',''))}</a>`)
  ].filter(Boolean).join(' ');
  q('#hero').style.display = 'flex';

  q('#bio').textContent = p.biography || '—';

  const gcsIG = (((j.gcs||{}).ig||{}).items)||[];
  if(gcsIG.length){
    q('#gcs').innerHTML = gcsIG.slice(0,6).map(it=>`
      <div class="item">
        <div style="font-weight:700">${esc(it.title||'—')}</div>
        <div style="opacity:.8;margin-top:2px">${esc(it.snippet||'')}</div>
        <div style="margin-top:4px"><a target="_blank" href="${it.link}">${esc(it.displayLink||it.link||'link')}</a></div>
      </div>`).join('');
  }else{
    q('#gcs').textContent = 'Sonuç yok';
  }
}

const u0 = new URL(location.href).searchParams.get('user');
if(u0){ q('#u').value = u0; run(); }
</script>
"""


def tester_pro2() -> str:
    return """<!doctype html><meta charset="utf-8">
<title>Footprint — PRO2</title>
<style>
  :root{--blue:#1e40af;--blue2:#3b82f6;--ink:#0f172a;--muted:#64748b;--card:#fff;--bd:#e5e7eb;--ring:rgba(59,130,246,.35)}
  *{box-sizing:border-box} body{margin:0;font-family:system-ui,Segoe UI,Arial;background:#f8fafc;color:var(--ink)}
  header{background:linear-gradient(135deg,var(--blue2),var(--blue));color:#fff;padding:18px 22px}
  header .brand{font-size:18px;font-weight:800}
  main{max-width:980px;margin:18px auto;padding:0 18px}
  .bar{display:flex;gap:10px}
  input{flex:1;padding:10px 12px;border:1px solid var(--bd);border-radius:12px;font-size:16px;outline:none}
  input:focus{box-shadow:0 0 0 4px var(--ring);border-color:var(--blue2)}
  button{padding:10px 14px;border:0;background:var(--blue2);color:#fff;border-radius:12px;font-size:16px;font-weight:700;cursor:pointer}
  .hero{display:none;align-items:center;gap:16px;margin-top:14px;background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,.07)}
  .pp{width:84px;height:84px;border-radius:18px;object-fit:cover}
  .name{font-size:22px;font-weight:800}
  .handle{font-weight:700;color:#e2e8f0;background:rgba(255,255,255,.2);padding:4px 8px;border-radius:999px;margin-left:8px}
  .stats{margin-top:4px;opacity:.9}
  .cards{display:grid;grid-template-columns:1fr;gap:12px;margin-top:14px}
  @media(min-width:900px){ .cards{grid-template-columns:1fr 1fr} }
  .card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:14px}
  .card h3{margin:0 0 8px 0;font-size:16px}
  .bio{white-space:pre-wrap;line-height:1.35}
  .links a{display:inline-block;margin-right:10px;color:#2563eb;text-decoration:none}
  .item{padding:8px;border:1px dashed #e2e8f0;border-radius:10px;margin-top:8px}
  details{margin-top:12px}
</style>
<header><div class="brand">FOOTPRINT — Tester (PRO2)</div></header>
<main>
  <div class="bar">
    <input id="u" placeholder="kullanıcı (ör. ahmettssyn)" />
    <button onclick="run()">Ara</button>
  </div>

  <section id="hero" class="hero">
    <img id="pp" class="pp" alt="">
    <div>
      <div class="name" id="nm">—</div>
      <div class="stats" id="st">—</div>
      <div class="links" id="ln">—</div>
    </div>
  </section>

  <section class="cards">
    <div class="card"><h3>Biyografi</h3><div id="bio" class="bio">—</div></div>
    <div class="card"><h3>Google (IG/X) isabetleri</h3><div id="gcs">—</div></div>
  </section>

  <details><summary>Raw JSON</summary>
    <pre id="raw" style="white-space:pre-wrap;background:#0b1220;color:#dbeafe;border-radius:12px;padding:10px;overflow:auto;max-height:340px"></pre>
  </details>
</main>

<script>
const Q=(s)=>document.querySelector(s);
const esc=(s)=> (s??"").toString().replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));
async function run(){
  const u = Q('#u').value.trim(); if(!u) return;
  const fd = new URLSearchParams([['user',u],['with_bio','1'],['prefer_native','1']]);
  const r  = await fetch('/tester/compare-ig-x-plus',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:fd});
  const j  = await r.json();
  Q('#raw').textContent = JSON.stringify(j,null,2);

  let p = (j.profile && j.profile.ig) ? j.profile.ig : null;
  if(!p || (!p.username && !p.full_name)){
    const fd2 = new URLSearchParams([['user',u]]);
    const r2  = await fetch('/tester/ig-bio',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:fd2});
    const j2  = await r2.json();
    p = j2.profile || {};
  }

  if(p.profile_pic_url) Q('#pp').src = p.profile_pic_url;
  const handle = p.username ? '@'+p.username : '';
  Q('#nm').innerHTML = esc(p.full_name||'') + (handle?` <span class="handle">${esc(handle)}</span>`:'');
  Q('#st').innerHTML = `<b>Takipçi:</b> ${esc(p.followers??'-')} · <b>Takip:</b> ${esc(p.following??'-')}`;
  const igLink = p.username ? `https://www.instagram.com/${p.username}/` : null;
  const xLinks = (j.links && j.links.x) ? j.links.x : [];
  Q('#ln').innerHTML = [
    igLink ? `<a target="_blank" href="${igLink}">instagram.com/${esc(p.username)}</a>` : '',
    ...xLinks.map(h=>`<a target="_blank" href="${h}">${esc(h.replace('https://',''))}</a>`)
  ].filter(Boolean).join(' ');
  Q('#hero').style.display = 'flex';

  Q('#bio').textContent = p.biography || '—';

  const gcsIG = (((j.gcs||{}).ig||{}).items)||[];
  Q('#gcs').innerHTML = gcsIG.length
    ? gcsIG.slice(0,6).map(it=>`
      <div class="item">
        <div style="font-weight:700">${esc(it.title||'—')}</div>
        <div style="opacity:.8;margin-top:2px">${esc(it.snippet||'')}</div>
        <div style="margin-top:4px"><a target="_blank" href="${it.link}">${esc(it.displayLink||it.link||'link')}</a></div>
      </div>`).join('')
    : 'Sonuç yok';
}

const u0 = new URL(location.href).searchParams.get('user');
if(u0){ Q('#u').value = u0; run(); }
</script>
"""


__all__ = ["ig_bio_ui", "ig_bio_ui_pro", "tester_pro", "tester_pro2"]
