# app/templates/ig_plus_bridge.py
# -*- coding: utf-8 -*-
"""Browser-side bridge scripts served by the IG tester router.

Each function returns a JS source as a plain string. The JS is delivered as
text/plain (PlainTextResponse) so the browser can ``<script src=...>`` it.
Versions are kept side-by-side because individual UIs lock onto specific
versions.
"""


def pro_bridge() -> str:
    return r"""/*! pro-bridge v5 */
(function(){
  const $=s=>document.querySelector(s);
  const esc=s=>(s??"").toString().replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));

  function host(){
    const all=[...document.querySelectorAll("main,section,div,article")];
    return all.find(el=>/Compare IG vs X/i.test(el.textContent))||document.body;
  }
  function findCompare(){ return [...document.querySelectorAll("section,div,article")]
    .find(el=>/Compare IG vs X/i.test(el.textContent)); }
  function readUser(){ const b=findCompare(); const i=b?b.querySelector("input"):null; return (i?.value||"").trim(); }

  function ensureUI(){
    const h=host();
    if(!$('#bioHead')){
      const x=document.createElement('section'); x.id='bioHead';
      x.innerHTML=`<style>
        #bioHead{margin:12px 0;border:1px solid #1f2937;border-radius:14px;padding:12px;
                 background:linear-gradient(145deg,#0b1220,#0a1222);color:#dbeafe;box-shadow:0 6px 22px rgba(0,0,0,.25)}
        #bioHead .row{display:flex;gap:14px;align-items:center}
        #bioHead .pp{width:70px;height:70px;border-radius:16px;object-fit:cover}
        #bioHead .name{font-weight:800;font-size:18px}
        #bioHead .handle{opacity:.85;margin-left:6px}
        #bioHead .stats{opacity:.9;margin-top:2px}
        #bioHead a{color:#60a5fa;text-decoration:none}
        #bioHead .bio{white-space:pre-wrap;line-height:1.35;margin-top:6px}
        #bridgeCtl{display:flex;gap:8px;margin-bottom:10px}
        #bridgeCtl input{flex:1;min-width:220px;padding:8px 10px;border-radius:10px;border:1px solid #334155;background:#0b1220;color:#dbeafe}
        #bridgeCtl button{padding:8px 12px;border:0;border-radius:10px;background:#3b82f6;color:#fff;font-weight:700;cursor:pointer}
      </style>
      <div id="bridgeCtl">
        <input id="bridgeUser" placeholder="instagram kullanıcı adı (örn. ahmettssyn)">
        <button id="bridgeGo">Göster</button>
      </div>
      <div class="row">
        <img id="bh_pp" class="pp" alt="">
        <div>
          <div class="name" id="bh_name">—</div>
          <div class="stats" id="bh_stats">—</div>
          <div class="links" id="bh_links"></div>
        </div>
      </div>
      <div class="bio" id="bh_bio">—</div>`;
      h.prepend(x);
    }
    if(!$('#igPreview')){
      const box=document.createElement('section');
      box.innerHTML=`<style>
        #igPreview{position:relative;height:360px;border-radius:16px;background:#0b1220;border:1px solid #1f2937;box-shadow:0 12px 35px rgba(0,0,0,.35)}
        #igPrevImg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:16px;display:none}
        #igCap{position:absolute;left:8px;bottom:8px;color:#dbeafe;background:rgba(0,0,0,.45);padding:6px 10px;border-radius:10px;margin:0}
      </style>
      <div id="igPreview">
        <img id="igPrevImg" alt="">
        <div id="igCap">Instagram önizleme</div>
      </div>`;
      h.prepend(box);
    }
    if($('#bridgeGo') && !$('#bridgeGo').dataset.wired){
      $('#bridgeGo').dataset.wired='1';
      $('#bridgeGo').addEventListener('click',()=>trigger());
    }
    const cmp=findCompare();
    if(cmp && !cmp.dataset.bridgeHook){
      cmp.dataset.bridgeHook='1';
      const btn=[...cmp.querySelectorAll('button')].find(b=>b.textContent.trim().toLowerCase().startsWith('karşılaştır'));
      if(btn){ btn.addEventListener('click',()=>setTimeout(trigger,90)); }
    }
  }

  async function fetchAll(user){
    const j1 = await (await fetch('/tester/ig-bio',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams([['user',user]])})).json();
    let p = (j1||{}).profile || {};
    const j2 = await (await fetch('/tester/compare-ig-x-plus',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams([['user',user],['with_bio','1'],['prefer_native','1']])})).json();
    if((!p.username) && j2.profile?.ig) p = j2.profile.ig;
    return { p, links: j2.links||{} };
  }

  function paint(p,links){
    const nm=(p.full_name||'').trim(), handle=p.username?('@'+p.username):'';
    if($('#bh_pp') && p.profile_pic_url) $('#bh_pp').src=p.profile_pic_url;
    if($('#bh_name')) $('#bh_name').innerHTML = esc(nm) + (handle?` <span class="handle">${esc(handle)}</span>`:'');
    if($('#bh_stats')) $('#bh_stats').innerHTML = `<b>Takipçi:</b> ${esc(p.followers??'-')} · <b>Takip:</b> ${esc(p.following??'-')}`;
    if($('#bh_bio')) $('#bh_bio').textContent = p.biography || '—';
    if($('#bh_links')){
      const ig = p.username ? `https://www.instagram.com/${p.username}/` : null;
      const xs = (links.x||[]);
      $('#bh_links').innerHTML = [ ig?`<a target="_blank" href="${ig}">instagram.com/${esc(p.username)}</a>`:'', ...xs.map(h=>`<a target="_blank" href="${h}">${esc(h.replace('https://',''))}</a>`) ].filter(Boolean).join(' ');
    }
    const box=$('#igPreview'), img=$('#igPrevImg');
    if(img && p.profile_pic_url){
      img.style.display='none';
      img.onload=()=>{ img.style.display='block'; };
      img.onerror=()=>{ img.removeAttribute('src'); img.style.display='none'; };
      img.src = '/tester/ig-proxy?url=' + encodeURIComponent(p.profile_pic_url);
    }
    if($('#igCap')) $('#igCap').textContent = p.username ? `instagram.com/${p.username}` : 'Instagram önizleme';
    if($('#bridgeUser') && p.username) $('#bridgeUser').value=p.username;
  }

  async function trigger(){
    const u = ($('#bridgeUser')?.value||'').trim() || readUser();
    if(!u) return;
    try{ const {p,links}=await fetchAll(u); paint(p,links); }catch(e){ console.warn('[bridge]',e); }
  }

  function init(){
    ensureUI();
    const u0=new URL(location.href).searchParams.get('user');
    if(u0){ const i=$('#bridgeUser'); if(i) i.value=u0; trigger(); }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
"""


def pro_bridge_v2() -> str:
    return """/*! pro-bridge v2 */
(function(){
 const $=s=>document.querySelector(s);
 async function getPlus(user){
   const fd=new URLSearchParams([["user",user],["with_bio","1"],["prefer_native","1"]]);
   const r = await fetch("/tester/compare-ig-x-plus",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:fd});
   const j = await r.json();
   let p=(j.profile && j.profile.ig) || null;
   if(!p){ const r2=await fetch("/tester/ig-bio",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams([["user",user]])}); p=(await r2.json()).profile||{}; }
   return p||{};
 }
 function ensureImg(){
   let box = $("#igPreview");
   if(!box){ box = document.createElement("div"); box.id="igPreview"; box.style.cssText="position:relative;height:260px;border-radius:16px;border:1px solid #1f2937;background:#0b1220;margin-bottom:8px;"; const host=document.querySelector("main,body"); (host||document.body).prepend(box); const cap=document.createElement("div"); cap.textContent="Instagram önizleme"; cap.style.cssText="font-size:12px;opacity:.8;margin-top:4px"; (host||document.body).insertBefore(cap, (box.nextSibling)); }
   let img = document.getElementById("igPrevImg");
   if(!img){ img=document.createElement("img"); img.id="igPrevImg"; img.alt=""; img.style.cssText="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:16px;display:block"; box.appendChild(img); }
   return {box,img};
 }
 async function run(user){
   if(!user) return;
   const p = await getPlus(user);
   const {box,img} = ensureImg();
   if(p.profile_pic_url){
     const prox = "/tester/ig-proxy?url="+encodeURIComponent(p.profile_pic_url)+"&t="+Date.now();
     box.style.backgroundImage = "url('"+prox+"')";
     img.src = prox;
   }
 }
 function wire(){
   const input = document.querySelector('input') || document.getElementById('u');
   const btn = Array.from(document.querySelectorAll('button')).find(b=>/(karşılaştır|göster|ara)/i.test(b.textContent||""));
   if(!input||!btn) return;
   btn.addEventListener("click", ()=> setTimeout(()=> run((input.value||"").trim()), 80));
   const u0=new URL(location.href).searchParams.get("user"); if(u0){ input.value=u0; btn.click(); }
 }
 if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", wire); else wire();
})();
"""


def pro_bridge_v3() -> str:
    return """/*! pro-bridge v3 */
(function(){
  const $ = s => document.querySelector(s);
  const esc = s => (s??"").toString().replace(/[&<>]/g, m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));

  async function getProfile(user){
    try{
      const fd = new URLSearchParams([["user",user],["with_bio","1"],["prefer_native","1"]]);
      const r  = await fetch("/tester/compare-ig-x-plus",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:fd});
      const j  = await r.json();
      if (j.profile && j.profile.ig) return j.profile.ig;
    }catch(_){}
    const r2 = await fetch("/tester/ig-bio",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams([["user",user]])});
    const j2 = await r2.json();
    return j2.profile||{};
  }

  function ensureBox(){
    let box = document.getElementById("igPreview");
    if(!box){
      const host = document.querySelector("main") || document.body;
      box = document.createElement("div");
      box.id="igPreview";
      box.style.cssText="position:relative;height:260px;border-radius:16px;border:1px solid #1f2937;background:#0b1220;margin:12px 0;overflow:hidden";
      host.prepend(box);
    }
    let img = document.getElementById("igPrevImg");
    if(!img){
      img = document.createElement("img");
      img.id="igPrevImg";
      img.alt="";
      img.style.cssText="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;border-radius:16px";
      box.appendChild(img);
    }
    return {box,img};
  }

  async function show(user){
    if(!user) return;
    const p = await getProfile(user);
    const {box,img} = ensureBox();
    if (p && p.profile_pic_url){
      img.onerror = ()=>{ /* sessizce geç */ };
      img.src = p.profile_pic_url;
      let head = document.getElementById("igHead");
      if(!head){
        head = document.createElement("div");
        head.id="igHead";
        head.style.cssText="margin:6px 2px;color:#dbeafe";
        box.insertAdjacentElement("afterend", head);
      }
      head.innerHTML = `<b>${esc(p.full_name||"")}</b> <span style="opacity:.8">@${esc(p.username||"")}</span>
        <span style="opacity:.9;margin-left:8px">· Takipçi: ${esc(p.followers??"-")} · Takip: ${esc(p.following??"-")}</span>`;
    }
  }

  function wire(){
    const input = document.querySelector('input') || document.getElementById('u');
    const btn = Array.from(document.querySelectorAll('button')).find(b=>/(karşılaştır|göster|ara|getir)/i.test((b.textContent||"")));
    if(!input || !btn) return;
    btn.addEventListener("click", ()=> setTimeout(()=> show((input.value||"").trim()), 80));
    const u0 = new URL(location.href).searchParams.get("user");
    if(u0){ input.value=u0; btn.click(); }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", wire); else wire();
})();
"""


def pro_bridge_v4() -> str:
    return """/*! pro-bridge v4 (no-referrer + fallback) */
(function(){
  const $=s=>document.querySelector(s);
  const esc=s=>(s??"").toString().replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));

  async function getProfile(user){
    try{
      const fd=new URLSearchParams([["user",user],["with_bio","1"],["prefer_native","1"]]);
      const r = await fetch("/tester/compare-ig-x-plus",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:fd});
      const j = await r.json();
      if (j.profile && j.profile.ig) return j.profile.ig;
    }catch(_){}
    const r2=await fetch("/tester/ig-bio",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams([["user",user]])});
    const j2=await r2.json();
    return j2.profile||{};
  }

  function ensure(){
    let box = document.getElementById("igPreview");
    if(!box){
      const host=document.querySelector("main")||document.body;
      box=document.createElement("div");
      box.id="igPreview";
      box.style.cssText="position:relative;height:240px;border-radius:16px;border:1px solid #1f2937;background:#0b1220;margin:12px 0;overflow:hidden";
      host.prepend(box);
    }
    let img = document.getElementById("igPrevImg");
    if(!img){
      img=document.createElement("img");
      img.id="igPrevImg";
      img.alt="";
      img.referrerPolicy="no-referrer";
      img.style.cssText="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;border-radius:16px";
      box.appendChild(img);
    }
    return {box,img};
  }

  function makeFallbacks(u){
    const direct = u;
    const weserv = "https://images.weserv.nl/?url="+encodeURIComponent(u)+"&w=400&h=400&fit=cover&a=entropy";
    return [direct, weserv];
  }

  async function show(user){
    if(!user) return;
    const p = await getProfile(user);
    const {box,img} = ensure();
    const u = p.profile_pic_url_hd || p.profile_pic_url;
    if(!u) return;

    const candidates = makeFallbacks(u);
    let i = 0;
    img.onerror = ()=>{ i++; if(i < candidates.length){ img.src = candidates[i]; box.style.backgroundImage = "url('"+candidates[i]+"')"; } };
    img.src = candidates[0];
    box.style.backgroundImage = "url('"+candidates[0]+"')";

    let head = document.getElementById("igHead");
    if(!head){
      head = document.createElement("div");
      head.id="igHead";
      head.style.cssText="margin:6px 2px;color:#dbeafe";
      box.insertAdjacentElement("afterend", head);
    }
    head.innerHTML = `<b>${esc(p.full_name||"")}</b> <span style="opacity:.8">@${esc(p.username||"")}</span>
      <span style="opacity:.9;margin-left:8px">· Takipçi: ${esc(p.followers??"-")} · Takip: ${esc(p.following??"-")}</span>`;
  }

  function wire(){
    const input = document.querySelector('input') || document.getElementById('u');
    const btn = Array.from(document.querySelectorAll('button')).find(b=>/(karşılaştır|göster|ara|getir)/i.test((b.textContent||"")));
    if(!input||!btn) return;
    btn.addEventListener("click", ()=> setTimeout(()=> show((input.value||"").trim()), 80));
    const u0 = new URL(location.href).searchParams.get("user"); if(u0){ input.value=u0; btn.click(); }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", wire); else wire();
})();
"""


def pro_bridge_compact() -> str:
    return """/*! pro-bridge compact (avatar header) */
(function(){
  const $=s=>document.querySelector(s);
  const esc=s=>(s??"").toString().replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));

  async function getProfile(user){
    try{
      const fd=new URLSearchParams([["user",user],["with_bio","1"],["prefer_native","1"]]);
      const r = await fetch("/tester/compare-ig-x-plus",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:fd});
      const j = await r.json();
      if (j.profile && j.profile.ig) return j.profile.ig;
    }catch(_){}
    const r2=await fetch("/tester/ig-bio",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams([["user",user]])});
    const j2=await r2.json();
    return j2.profile||{};
  }

  function ensureHeader(){
    let wrap = document.getElementById("igMiniHead");
    if(wrap) return wrap;
    const host = document.querySelector("main") || document.body;
    wrap = document.createElement("section");
    wrap.id = "igMiniHead";
    wrap.innerHTML = `
      <style>
        #igMiniHead{max-width:720px;margin:10px 0 14px 0}
        #igMiniHead .card{
          display:flex;gap:14px;align-items:center;
          background:#0b1220;border:1px solid #1f2937;border-radius:14px;
          padding:12px 14px;box-shadow:0 6px 22px rgba(0,0,0,.18)
        }
        #igMiniHead img{
          width:86px;height:86px;border-radius:50%;
          object-fit:cover;display:block;referrer-policy:no-referrer
        }
        #igMiniHead .nm{font-weight:800;color:#dbeafe}
        #igMiniHead .handle{opacity:.85;margin-left:6px}
        #igMiniHead .st{opacity:.9;margin-top:2px}
        #igMiniHead a{color:#60a5fa;text-decoration:none}
      </style>
      <div class="card">
        <img id="igMiniAvatar" alt="">
        <div>
          <div class="nm" id="igMiniName">—</div>
          <div class="st" id="igMiniStats">—</div>
          <div class="ln" id="igMiniLinks"></div>
        </div>
      </div>`;
    host.prepend(wrap);
    return wrap;
  }

  function fallbacks(u){
    const direct=u;
    const proxy="https://images.weserv.nl/?url="+encodeURIComponent(u)+"&w=200&h=200&fit=cover&a=entropy";
    return [direct, proxy];
  }

  async function show(user){
    if(!user) return;
    const p = await getProfile(user);
    ensureHeader();
    const av = document.getElementById("igMiniAvatar");
    const nm = document.getElementById("igMiniName");
    const st = document.getElementById("igMiniStats");
    const ln = document.getElementById("igMiniLinks");

    nm.innerHTML = esc(p.full_name||"") + (p.username?` <span class="handle">@${esc(p.username)}</span>`:"");
    st.innerHTML = `<b>Takipçi:</b> ${esc(p.followers??"-")} · <b>Takip:</b> ${esc(p.following??"-")}`;
    ln.innerHTML = p.username ? `<a target="_blank" href="https://www.instagram.com/${esc(p.username)}/">instagram.com/${esc(p.username)}</a>` : "";

    const u = p.profile_pic_url_hd || p.profile_pic_url;
    if(!u) return;
    const list = fallbacks(u);
    let i=0;
    av.onerror = ()=>{ i++; if(i<list.length){ av.src=list[i]; } };
    av.referrerPolicy = "no-referrer";
    av.src = list[0];
  }

  function wire(){
    const input = document.querySelector('input') || document.getElementById('u');
    const btn = Array.from(document.querySelectorAll('button')).find(b=>/(karşılaştır|göster|ara|getir)/i.test((b.textContent||"")));
    if(!input||!btn) return;
    btn.addEventListener("click", ()=> setTimeout(()=> show((input.value||"").trim()), 80));
    const u0=new URL(location.href).searchParams.get("user"); if(u0){ input.value=u0; btn.click(); }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", wire); else wire();
})();
"""


def pro_bridge_v5() -> str:
    return """/*! pro-bridge v5 (right mini card + bio) */
(function(){
  const $ = s => document.querySelector(s);
  const esc = s => (s??"").toString().replace(/[&<>]/g, m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));

  function killOld(){
    ["igPreview","igHead"].forEach(id=>{const el=document.getElementById(id); if(el) el.remove();});
    for(const el of Array.from(document.querySelectorAll("*"))){
      if(el.childElementCount===0 && /Instagram önizleme/i.test((el.textContent||"").trim())) { el.remove(); }
    }
  }

  function hostRight(){
    const hunt = Array.from(document.querySelectorAll("div,section,article"))
      .find(el => /Hunt X by Name/i.test(el.textContent||""));
    return hunt ? hunt.parentElement : (document.querySelector("main")||document.body);
  }

  function ensureCard(){
    let card = document.getElementById("igCompact");
    if(card) return card;
    card = document.createElement("div");
    card.id = "igCompact";
    card.innerHTML = `
      <style>
        #igCompact{background:#0b1220;border:1px solid #334155;border-radius:14px;padding:12px;margin:0 0 12px 0}
        #igCompact .row{display:flex;gap:10px;align-items:center}
        #igCompact img{width:64px;height:64px;border-radius:12px;object-fit:cover;background:#1f2937}
        #igCompact .name{font-weight:800;color:#e2e8f0}
        #igCompact .handle{opacity:.8;margin-left:6px}
        #igCompact .stats{opacity:.85;color:#cbd5e1;font-size:12.5px;margin-top:2px}
        #igCompact .bio{margin-top:6px;color:#cbd5e1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;line-height:1.35}
        #igCompact a{color:#60a5fa;text-decoration:none}
      </style>
      <div class="row">
        <img id="igCAvatar" alt="">
        <div>
          <div class="name" id="igCName">—</div>
          <div class="stats" id="igCStats">—</div>
        </div>
      </div>
      <div class="bio" id="igCBio">—</div>
      <div class="stats"><a id="igCLink" target="_blank"></a></div>
    `;
    const host = hostRight();
    const before = Array.from(host.children).find(el => /Hunt X by Name/i.test(el.textContent||""));
    if (before) host.insertBefore(card, before); else host.prepend(card);
    return card;
  }

  async function getProfile(user){
    try{
      const fd=new URLSearchParams([["user",user],["with_bio","1"],["prefer_native","1"]]);
      const r = await fetch("/tester/compare-ig-x-plus",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:fd});
      const j = await r.json();
      if (j.profile && j.profile.ig) return j.profile.ig;
    }catch(_){}
    const r2=await fetch("/tester/ig-bio",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams([["user",user]])});
    const j2=await r2.json();
    return j2.profile||{};
  }

  async function run(user){
    killOld();
    if(!user) return;
    const p = await getProfile(user);
    const card = ensureCard();
    const ig = p.username ? `https://www.instagram.com/${p.username}/` : null;

    const badges = `${p.is_verified?' ✅':''}${p.is_private?' 🔒':''}`;
    const nameEl = $("#igCName");
    nameEl.innerHTML = `${esc(p.full_name||"")}${badges} ${p.username?`<span class="handle">@${esc(p.username)}</span>`:''}`;
    $("#igCStats").innerHTML = `<b>Takipçi:</b> ${esc(p.followers??'-')} · <b>Takip:</b> ${esc(p.following??'-')}`;
    $("#igCBio").textContent = p.biography || '';
    if (p.profile_pic_url) $("#igCAvatar").src = p.profile_pic_url;
    const link = $("#igCLink");
    link.textContent = ig ? `instagram.com/${esc(p.username)}` : "";
    if (ig){ link.href = ig; card.style.cursor="pointer"; card.onclick=(e)=>{ if(e.target.tagName!=="A") window.open(ig,"_blank"); }; }
  }

  function wire(){
    const input = document.querySelector('input') || document.getElementById('u');
    const btn = Array.from(document.querySelectorAll('button')).find(b=>/(karşılaştır|göster|ara|getir)/i.test((b.textContent||"")));
    if(!input || !btn) return;
    btn.addEventListener("click", ()=> setTimeout(()=> run((input.value||"").trim()), 60));
    const u0=new URL(location.href).searchParams.get("user"); if(u0){ input.value=u0; btn.click(); }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", wire); else wire();
})();
"""


def pro_bridge_v6() -> str:
    return """/*! pro-bridge v6 (right mini-card + bio + 3xN media grid) */
(function(){
  const $=s=>document.querySelector(s);
  const esc=s=>(s??"").toString().replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));

  function killOld(){
    ["igPreview","igHead"].forEach(id=>{const el=document.getElementById(id); if(el) el.remove();});
    for(const el of Array.from(document.querySelectorAll("*"))){
      if(el.childElementCount===0 && /Instagram önizleme/i.test((el.textContent||"").trim())) { el.remove(); }
    }
  }
  function hostRight(){
    const hunt = Array.from(document.querySelectorAll("div,section,article"))
      .find(el => /Hunt X by Name/i.test(el.textContent||""));
    return hunt ? hunt.parentElement : (document.querySelector("main")||document.body);
  }
  function ensureCard(){
    let card = document.getElementById("igCompact");
    if(card) return card;
    card = document.createElement("div");
    card.id="igCompact";
    card.innerHTML = `
      <style>
        #igCompact{background:#0b1220;border:1px solid #334155;border-radius:14px;padding:12px;margin:0 0 12px 0}
        #igCompact .row{display:flex;gap:10px;align-items:center}
        #igCompact img.pp{width:64px;height:64px;border-radius:12px;object-fit:cover;background:#1f2937}
        #igCompact .name{font-weight:800;color:#e2e8f0}
        #igCompact .handle{opacity:.8;margin-left:6px}
        #igCompact .stats{opacity:.85;color:#cbd5e1;font-size:12.5px;margin-top:2px}
        #igCompact .bio{margin-top:6px;color:#cbd5e1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;line-height:1.35}
        #igCGrid{margin-top:8px;display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
        #igCGrid a{display:block;border-radius:10px;overflow:hidden;border:1px solid #334155}
        #igCGrid img{width:100%;aspect-ratio:1/1;object-fit:cover;display:block}
        #igCompact a{color:#60a5fa;text-decoration:none}
      </style>
      <div class="row">
        <img class="pp" id="igCAvatar" alt="">
        <div>
          <div class="name" id="igCName">—</div>
          <div class="stats" id="igCStats">—</div>
        </div>
      </div>
      <div class="bio" id="igCBio">—</div>
      <div class="stats"><a id="igCLink" target="_blank"></a></div>
      <div id="igCGrid"></div>
    `;
    const host = hostRight();
    const before = Array.from(host.children).find(el => /Hunt X by Name/i.test(el.textContent||""));
    if(before) host.insertBefore(card, before); else host.prepend(card);
    return card;
  }

  async function getProfile(user){
    try{
      const fd=new URLSearchParams([["user",user],["with_bio","1"],["prefer_native","1"]]);
      const r = await fetch("/tester/compare-ig-x-plus",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:fd});
      const j = await r.json();
      if (j.profile && j.profile.ig) return j.profile.ig;
    }catch(_){}
    const r2=await fetch("/tester/ig-bio",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams([["user",user]])});
    const j2=await r2.json();
    return j2.profile||{};
  }

  async function getMedia(user, limit=9){
    try{
      const fd=new URLSearchParams([["user",user],["limit", String(limit)]]);
      const r = await fetch("/tester/ig-media",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:fd});
      return await r.json();
    }catch(_){ return {ok:false, items:[]} }
  }

  async function run(user){
    killOld();
    if(!user) return;
    const p = await getProfile(user);
    const card = ensureCard();
    const ig = p.username ? `https://www.instagram.com/${p.username}/` : null;
    const badges = `${p.is_verified?' ✅':''}${p.is_private?' 🔒':''}`;

    $("#igCName").innerHTML = `${esc(p.full_name||"")}${badges} ${p.username?`<span class="handle">@${esc(p.username)}</span>`:''}`;
    $("#igCStats").innerHTML = `<b>Takipçi:</b> ${esc(p.followers??'-')} · <b>Takip:</b> ${esc(p.following??'-')}`;
    $("#igCBio").textContent = p.biography || '';
    if (p.profile_pic_url) $("#igCAvatar").src = p.profile_pic_url;
    const link = $("#igCLink");
    link.textContent = ig ? `instagram.com/${esc(p.username)}` : "";
    if (ig){ link.href = ig; card.style.cursor="pointer"; card.onclick=(e)=>{ if(e.target.tagName!=="A" && !e.target.closest("#igCGrid")) window.open(ig,"_blank"); }; }

    const grid = $("#igCGrid");
    grid.innerHTML = "";
    if (!p.is_private && p.username){
      const m = await getMedia(p.username, 9);
      if (m && m.ok && m.items && m.items.length){
        grid.innerHTML = m.items.map(it=> it && it.image ? `<a href="${it.link||'#'}" target="_blank"><img loading="lazy" src="${esc(it.thumb||it.image)}" alt=""></a>` : "" ).join("");
      }
    }
  }

  function wire(){
    const input = document.querySelector('input') || document.getElementById('u');
    const btn = Array.from(document.querySelectorAll('button')).find(b=>/(karşılaştır|göster|ara|getir)/i.test((b.textContent||"")));
    if(!input||!btn) return;
    btn.addEventListener("click", ()=> setTimeout(()=> run((input.value||"").trim()), 60));
    const u0=new URL(location.href).searchParams.get("user"); if(u0){ input.value=u0; btn.click(); }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", wire); else wire();
})();
"""


def head_mini() -> str:
    return """/*! head-mini */
(function(){
  const $=s=>document.querySelector(s);
  const esc=s=>(s??"").toString().replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));
  function ensure(){
    if (document.getElementById('igHeadMini')) return;
    const grid = document.querySelector('.cards') || document.querySelector('main') || document.body;
    const aside = document.createElement('div');
    aside.id='igHeadMini';
    aside.style.cssText='grid-column:2;align-self:start;background:#0b1220;border:1px solid #1f2937;border-radius:14px;padding:12px;color:#dbeafe;min-height:120px';
    aside.innerHTML = '<div style="display:flex;gap:10px;align-items:center"><img id="hm_pp" alt="" style="width:56px;height:56px;border-radius:12px;object-fit:cover"><div><div id="hm_name" style="font-weight:800"></div><div id="hm_stats" style="opacity:.85;font-size:12px"></div></div></div><div id="hm_bio" style="white-space:pre-wrap;margin-top:6px;font-size:13px;opacity:.95"></div>';
    if (grid && grid.appendChild) grid.appendChild(aside); else document.body.appendChild(aside);
  }
  async function fill(user){
    if(!user) return;
    const fd=new URLSearchParams([['user',user]]);
    const r=await fetch('/tester/ig-bio',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:fd});
    const j=await r.json(); const p=j.profile||{};
    const img=$('#hm_pp'), nm=$('#hm_name'), st=$('#hm_stats'), bio=$('#hm_bio');
    if (img && p.profile_pic_url) { img.src=p.profile_pic_url; }
    if (nm) nm.innerHTML = esc(p.full_name||'')+' <span style="opacity:.8">@'+esc(p.username||'')+'</span>';
    if (st) st.innerHTML = 'Takipçi: '+esc(p.followers??'-')+' · Takip: '+esc(p.following??'-');
    if (bio) bio.textContent = p.biography||'';
  }
  function wire(){
    ensure();
    const inp=document.getElementById('u')||document.querySelector('input');
    const btn=[...document.querySelectorAll('button')].find(b=>/(karşılaştır|göster|ara|getir)/i.test(b.textContent||''));
    const u0=new URL(location.href).searchParams.get('user');
    const go=(u)=>fill((u||'').trim());
    if (u0){ if(inp) inp.value=u0; go(u0); }
    if (btn && inp){ btn.addEventListener('click',()=> setTimeout(()=>go(inp.value),80)); }
  }
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded', wire); else wire();
})();
"""


__all__ = [
    "pro_bridge",
    "pro_bridge_v2",
    "pro_bridge_v3",
    "pro_bridge_v4",
    "pro_bridge_v5",
    "pro_bridge_v6",
    "pro_bridge_compact",
    "head_mini",
]
