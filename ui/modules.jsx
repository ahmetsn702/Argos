/* Per-module form + results */
const { Ic, Card, Pill, KV, Summary, TechBlock, Stat, ListItem, Heat } = window;

/* ============ MOSINT (Email) ============ */
function MosintModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!query) return;
    setFetching(true); setApiError(null);
    try {
      const r = await fetch(`${baseUrl}/mosint/full?email=${encodeURIComponent(query)}`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm
        query={query} setQuery={setQuery}
        label="E-posta adresi"
        placeholder="örn. ayse.demir@outlook.com"
        mono
        chips={[
          ['leaks',     'Veri sızıntıları'],
          ['accounts',  'Bağlı hesaplar'],
          ['gravatar',  'Gravatar / avatar'],
          ['breach',    'Şifre hash kontrolü'],
          ['mx',        'MX kayıtları'],
        ]}
        options={options} setOptions={setOptions}
        onRun={runFetch}
      />
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Sorgulanıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={4} title="E-posta" icon="check"
                right={<Pill kind={apiData.smtp_valid ? 'ok' : 'bad'}>{apiData.smtp_valid ? 'Geçerli' : 'Geçersiz'}</Pill>}>
            <KV rows={[
              ['Adres', apiData.email || query],
              ['SMTP', apiData.smtp_valid ? 'Geçerli' : 'Geçersiz'],
              ['Tek kullanımlık', apiData.disposable ? 'Evet' : 'Hayır'],
              ['Gravatar ismi', apiData.gravatar?.name || '—'],
            ]}/>
          </Card>
          <Card span={4} title="Veri sızıntıları" icon="alert"
                right={<Pill kind={apiData.breaches?.length ? 'bad' : 'ok'}>{apiData.breaches?.length || 0} olay</Pill>}>
            <Stat value={apiData.breaches?.length || 0} label="Sızıntı" kind={apiData.breaches?.length ? 'bad' : 'ok'}/>
            <div className="list" style={{marginTop:12}}>
              {(apiData.breaches || []).map((b,i) => (
                <ListItem key={i} icon="!" title={b.name} sub={b.date} right={b.count ? `${b.count} kayıt` : undefined}/>
              ))}
            </div>
          </Card>
          <Card span={4} title="Bağlı hesaplar" icon="link"
                right={<Pill>{apiData.accounts?.length || 0} hesap</Pill>}>
            <div className="list">
              {(apiData.accounts || []).map((a,i) => (
                <ListItem key={i} icon={a.platform?.[0]?.toUpperCase()} title={a.platform} sub={a.url}/>
              ))}
              {!apiData.accounts?.length && <div style={{fontSize:13,color:'var(--muted)'}}>Hesap bulunamadı.</div>}
            </div>
          </Card>
          <TechBlock show={tech} data={apiData}/>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>
          ⚠ API hatası: {apiError}
        </div>
      ) : (
        <EmptyState query={query} />
      )}
    </>
  );
}

/* ============ Telefon ============ */
function PhoneModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!query) return;
    setFetching(true); setApiError(null);
    try {
      const r = await fetch(`${baseUrl}/phone/lookup?number=${encodeURIComponent(query)}`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm
        query={query} setQuery={setQuery}
        label="Telefon numarası"
        placeholder="örn. +90 532 412 88 17"
        mono
        chips={[
          ['carrier','Operatör tespiti'],
          ['type','Hat tipi'],
          ['whatsapp','WhatsApp / Telegram'],
          ['social','Sosyal medya eşleştirmesi'],
          ['truecaller','Truecaller kayıtları'],
        ]}
        options={options} setOptions={setOptions}
        onRun={runFetch}
      />
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Sorgulanıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={6} title="Hat bilgisi" icon="phone"
                right={<Pill kind={apiData.valid ? 'ok' : 'bad'}>{apiData.valid ? 'Geçerli' : 'Geçersiz'}</Pill>}>
            <KV rows={[
              ['Numara', apiData.format_national || apiData.number || query],
              ['Ülke', `${apiData.country_name || ''} (+${apiData.country_code || ''})`],
              ['Operatör', apiData.carrier || '—'],
              ['Hat tipi', apiData.line_type || '—'],
              ['Bölge', apiData.location || '—'],
              ['E.164', apiData.format_e164 || '—'],
            ]}/>
            <TechBlock show={tech} data={apiData}/>
          </Card>
          <Card span={6} title="Ham yanıt" icon="database">
            <TechBlock show={true} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>
          ⚠ API hatası: {apiError}
        </div>
      ) : (
        <EmptyState query={query} />
      )}
    </>
  );
}

/* ============ Dark Web ============ */
function DarkwebModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!query) return;
    setFetching(true); setApiError(null);
    try {
      const r = await fetch(`${baseUrl}/darkweb/lookup?query=${encodeURIComponent(query)}`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm
        query={query} setQuery={setQuery}
        label="Anahtar kelime, e-posta veya kullanıcı adı"
        placeholder="örn. ayse.demir"
        chips={[
          ['forums','Yer altı forumları'],
          ['markets','Pazar yerleri'],
          ['paste','Paste siteleri (24)'],
          ['telegram','Telegram kanalları'],
          ['leaks','Sızıntı veritabanları'],
        ]}
        options={options} setOptions={setOptions}
        onRun={runFetch}
      />
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Sorgulanıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={4} title="Sonuç" icon="spider"
                right={<Pill kind={apiData.found ? 'bad' : 'ok'}>{apiData.found ? 'Bulundu' : 'Temiz'}</Pill>}>
            <Stat value={apiData.results?.length || 0} label="Eşleşme" kind={apiData.results?.length ? 'bad' : 'ok'}/>
            {apiData.sources?.length > 0 && (
              <div style={{marginTop:10, display:'flex', gap:6, flexWrap:'wrap'}}>
                {apiData.sources.map((s,i) => <Pill key={i}>{s}</Pill>)}
              </div>
            )}
          </Card>
          <Card span={8} title="Sonuçlar" icon="database">
            <div className="list">
              {(apiData.results || []).map((r,i) => (
                <ListItem key={i} icon={r.source?.[0]?.toUpperCase()} title={r.source}
                  sub={r.details || r.query}
                  badge={r.found ? 'eşleşti' : 'yok'}
                  badgeKind={r.found ? 'bad' : ''}/>
              ))}
              {!apiData.results?.length && <div style={{fontSize:13,color:'var(--muted)'}}>Sonuç bulunamadı.</div>}
            </div>
            <TechBlock show={tech} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>
          ⚠ API hatası: {apiError}
        </div>
      ) : (
        <EmptyState query={query} />
      )}
    </>
  );
}

/* ============ Domain ============ */
function DomainModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!query) return;
    setFetching(true); setApiError(null);
    try {
      const r = await fetch(`${baseUrl}/domain/lookup?domain=${encodeURIComponent(query)}`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm
        query={query} setQuery={setQuery}
        label="Alan adı"
        placeholder="örn. kavakli-holding.com.tr"
        mono
        chips={[
          ['whois','WHOIS kayıtları'],
          ['dns','DNS taraması'],
          ['sub','Subdomain enumerasyonu'],
          ['tech','Teknoloji yığını'],
          ['ssl','SSL sertifikası'],
        ]}
        options={options} setOptions={setOptions}
        onRun={runFetch}
      />
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Sorgulanıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={6} title="IP & Konum" icon="globe">
            <KV rows={[
              ['Domain', apiData.domain || query],
              ['IP', apiData.ip || '—'],
              ['Ülke', apiData.country || '—'],
              ['ISP', apiData.isp || apiData.org || '—'],
              ['ASN', apiData.asn || '—'],
              ['Koordinat', apiData.lat && apiData.lon ? `${apiData.lat}, ${apiData.lon}` : '—'],
            ]}/>
          </Card>
          <Card span={6} title="WHOIS" icon="database">
            <KV rows={[
              ['Registrar', apiData.whois?.registrar || '—'],
              ['Kayıt', apiData.whois?.created || '—'],
              ['Bitiş', apiData.whois?.expires || '—'],
              ['Kayıt sahibi', apiData.whois?.registrant || '—'],
            ]}/>
            <TechBlock show={tech} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>
          ⚠ API hatası: {apiError}
        </div>
      ) : (
        <EmptyState query={query} />
      )}
    </>
  );
}

/* ============ IG Bio ============ *//* ============ IG Bio ============ */
function IgBioModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!query) return;
    setFetching(true); setApiError(null);
    try {
      const uname = query.replace(/^@/, '');
      const r = await fetch(`${baseUrl}/ig/bio?username=${encodeURIComponent(uname)}`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm
        query={query} setQuery={setQuery}
        label="Instagram kullanıcı adı"
        placeholder="örn. @ayse.demir"
        chips={[
          ['profile','Profil meta verisi'],
          ['bio','Biyografi analizi'],
          ['links','Dış bağlantılar'],
          ['mentions','Bahsedilen hesaplar'],
          ['archived','Arşiv (geri kalan biyolar)'],
        ]}
        options={options} setOptions={setOptions}
        onRun={runFetch}
      />
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Sorgulanıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={6} title="Profil" icon="link"
                right={<Pill kind={apiData.status === 'active' ? 'ok' : 'warn'}>{apiData.status || '—'}</Pill>}>
            <KV rows={[
              ['Kullanıcı adı', apiData.username || query],
              ['Görünen ad', apiData.display_name || '—'],
              ['Bio', apiData.bio || '—'],
              ['URL', apiData.url || '—'],
              ['Kaynak', apiData.source || '—'],
            ]}/>
          </Card>
          <Card span={6} title="Ham yanıt" icon="database">
            <TechBlock show={true} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>
          ⚠ API hatası: {apiError}
        </div>
      ) : (
        <EmptyState query={query} />
      )}
    </>
  );
}

/* ============ Yüz Tanıma ============ */
function FaceModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);
  const [file, setFile] = React.useState(null);

  const runFetch = async () => {
    if (!file) {
      setApiError('Önce bir görsel yükleyin.');
      return;
    }
    setFetching(true); setApiError(null);
    try {
      const fd = new FormData();
      fd.append('image', file);
      const r = await fetch(`${baseUrl}/face/search`, { method: 'POST', body: fd });
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm
        query={query} setQuery={setQuery}
        label="Görsel dosyası veya URL"
        placeholder="bir görsel yükleyin veya bağlantı yapıştırın"
        upload
        chips={[
          ['pimeyes','PimEyes benzeri arama'],
          ['social','Sosyal medya yüz eşleşmesi'],
          ['news','Haber arşivleri'],
          ['multi','Çoklu yüz desteği'],
        ]}
        options={options} setOptions={setOptions}
        onRun={runFetch}
        onFileChange={setFile}
      />
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Görsel analiz ediliyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={4} title="Tespit" icon="camera"
                right={<Pill>{apiData.faces_detected || 0} yüz</Pill>}>
            <Stat value={apiData.faces_detected || 0} label="Tespit edilen yüz"/>
            <Stat value={apiData.results?.length || 0} label="Eşleşme bulundu" kind={apiData.results?.length ? 'ok' : ''}/>
          </Card>
          <Card span={8} title="Eşleşmeler" icon="link"
                right={<Pill kind="ok">{apiData.results?.length || 0} sonuç</Pill>}>
            <div className="list">
              {(apiData.results || []).map((r,i) => (
                <ListItem key={i}
                  icon={<span style={{color:'#6EE7B7',fontWeight:600,fontSize:11}}>{r.similarity != null ? `${Math.round(r.similarity*100)}%` : '?'}</span>}
                  title={r.source || r.url}
                  sub={r.url}
                  badge={r.similarity >= 0.8 ? 'yüksek' : r.similarity >= 0.6 ? 'orta' : 'düşük'}
                  badgeKind={r.similarity >= 0.8 ? 'ok' : r.similarity >= 0.6 ? 'warn' : 'info'}/>
              ))}
              {!apiData.results?.length && <div style={{fontSize:13,color:'var(--muted)'}}>Eşleşme bulunamadı.</div>}
            </div>
            <TechBlock show={tech} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>
          ⚠ API hatası: {apiError}
        </div>
      ) : (
        <EmptyState query={query} />
      )}
    </>
  );
}

/* ============ Geo Photo ============ */
function GeoModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);
  const [file, setFile] = React.useState(null);

  const runFetch = async () => {
    if (!file) {
      setApiError('Önce bir görsel yükleyin.');
      return;
    }
    setFetching(true); setApiError(null);
    try {
      const fd = new FormData();
      fd.append('image', file);
      const r = await fetch(`${baseUrl}/geo/analyze-photo`, { method: 'POST', body: fd });
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm
        query={query} setQuery={setQuery}
        label="Görsel dosyası"
        placeholder="görsel yükleyin (EXIF dahil ideal)"
        upload
        chips={[
          ['exif','EXIF metadata'],
          ['landmark','Referans nokta tespiti'],
          ['ocr','Görseldeki yazı (OCR)'],
          ['sun','Güneş açısı analizi'],
        ]}
        options={options} setOptions={setOptions}
        onRun={runFetch}
        onFileChange={setFile}
      />
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Görsel analiz ediliyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={5} title="Konum tahmini" icon="pin"
                right={<Pill kind="ok">{apiData.confidence != null ? `%${Math.round(apiData.confidence*100)} güven` : '—'}</Pill>}>
            <KV rows={[
              ['Kaynak', apiData.source || '—'],
              ['Koordinat', apiData.lat && apiData.lng ? `${apiData.lat}, ${apiData.lng}` : '—'],
              ['Ülke', apiData.country || '—'],
              ['Bölge', apiData.region || '—'],
              ['Hata payı', apiData.radius_km ? `±${apiData.radius_km} km` : '—'],
              ['Fallback', apiData.fallback ? 'Evet' : 'Hayır'],
            ]}/>
          </Card>
          <Card span={7} title="Akıl yürütme" icon="database">
            {apiData.reasoning && (
              <KV rows={[
                ['Güneş açısı', apiData.reasoning.solar || '—'],
                ['Görsel ipuçları', apiData.reasoning.visual || '—'],
                ['Birleşim', apiData.reasoning.fusion || '—'],
              ]}/>
            )}
            <TechBlock show={tech} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>
          ⚠ API hatası: {apiError}
        </div>
      ) : (
        <EmptyState query={query} />
      )}
    </>
  );
}

/* ============ Unified Analysis ============ *//* ============ Unified Analysis ============ */
function UnifiedModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!query) return;
    setFetching(true); setApiError(null);
    try {
      const params = new URLSearchParams();
      if (query.includes('@') && query.includes('.')) params.set('email', query);
      else if (/^\+?\d/.test(query)) params.set('phone', query);
      else params.set('username', query);
      const r = await fetch(`${baseUrl}/scan/full?${params}`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm
        query={query} setQuery={setQuery}
        label="Hedef girdisi (her tip kabul edilir)"
        placeholder="e-posta, telefon, alan adı, kullanıcı adı veya görsel URL"
        mono
        chips={[
          ['mosint','E-posta (MOSINT)'],
          ['phone','Telefon'],
          ['darkweb','Dark Web'],
          ['domain','Domain'],
          ['igbio','IG Bio'],
          ['face','Yüz Tanıma'],
          ['geo','Geo Photo'],
        ]}
        options={options} setOptions={setOptions}
        onRun={runFetch}
      />
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Tüm modüller çalışıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={4} title="Sorgu" icon="search">
            <KV rows={[
              ['Girdi', typeof apiData.input === 'object' ? JSON.stringify(apiData.input) : (apiData.input || query)],
              ['Süre', apiData.took_ms != null ? `${apiData.took_ms} ms` : '—'],
              ['Karar', apiData.verdict || '—'],
            ]}/>
          </Card>
          {apiData.results?.mosint && (
            <Card span={4} title="E-posta (MOSINT)" icon="check"
                  right={<Pill kind={apiData.results.mosint.smtp_valid ? 'ok' : 'warn'}>{apiData.results.mosint.smtp_valid ? 'Geçerli' : 'Geçersiz'}</Pill>}>
              <Stat value={apiData.results.mosint.breaches?.length || 0} label="Sızıntı" kind={apiData.results.mosint.breaches?.length ? 'bad' : 'ok'}/>
            </Card>
          )}
          {apiData.results?.phone && (
            <Card span={4} title="Telefon" icon="phone">
              <KV rows={[
                ['Operatör', apiData.results.phone.carrier || '—'],
                ['Tip', apiData.results.phone.line_type || '—'],
              ]}/>
            </Card>
          )}
          {apiData.results?.social && (
            <Card span={6} title="Sosyal" icon="link">
              <TechBlock show={true} data={apiData.results.social}/>
            </Card>
          )}
          {apiData.results?.linkedin && (
            <Card span={6} title="LinkedIn" icon="link">
              <TechBlock show={true} data={apiData.results.linkedin}/>
            </Card>
          )}
          <Card span={12} title="Ham yanıt" icon="database">
            <TechBlock show={true} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>
          ⚠ API hatası: {apiError}
        </div>
      ) : (
        <EmptyState query={query} unified />
      )}
    </>
  );
}

/* ============ Shared form ============ *//* ============ Shared form ============ */
function ModuleForm({ label, placeholder, query, setQuery, chips = [], options, setOptions, mono = false, upload = false, onRun, onFileChange }) {
  return (
    <div className="form-card">
      <div className="form-grid">
        <div className="field">
          <label className="label">{label}</label>
          <input
            className={`input ${mono ? 'mono' : ''}`}
            placeholder={placeholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') document.getElementById('runBtn')?.click(); }}
          />
        </div>
        <div className="field">
          <label className="label">&nbsp;</label>
          <button id="runBtn" className="btn btn-primary"
            onClick={(e) => { e.preventDefault(); onRun?.(); window.__argosRun?.(); }}>
            {React.createElement(Ic.search)} Sorgula
          </button>
        </div>
      </div>
      {upload && (
        <div style={{marginTop:12, padding:'14px', border:'1px dashed var(--line-2)', borderRadius:10, display:'flex', alignItems:'center', gap:12, background:'rgba(255,255,255,0.015)'}}>
          <div style={{width:36, height:36, borderRadius:8, background:'var(--panel-2)', border:'1px solid var(--line)', display:'grid', placeItems:'center', color:'var(--muted)'}}>
            {React.createElement(Ic.camera)}
          </div>
          <div style={{flex:1, fontSize:13, color:'var(--muted)'}}>
            Görseli buraya sürükleyin veya seçin. JPEG / PNG / WEBP — maks. 12 MB.
            <input type="file" accept="image/*"
              onChange={(e) => onFileChange?.(e.target.files[0])}
              style={{display:'block', marginTop:8, fontSize:12, color:'var(--muted)'}} />
          </div>
        </div>
      )}
      {chips.length > 0 && (
        <div style={{marginTop:14}}>
          <div className="label" style={{marginBottom:8}}>Çalıştırılacak kontroller</div>
          <div className="row">
            {chips.map(([id, name]) => (
              <label key={id} className={`chip ${options[id] !== false ? 'on' : ''}`}>
                <input type="checkbox" checked={options[id] !== false} onChange={(e) => setOptions({ ...options, [id]: e.target.checked })}/>
                {options[id] !== false ? React.createElement(Ic.check, {style:{width:13,height:13}}) : <span style={{width:13,height:13,display:'inline-block',border:'1px solid currentColor',borderRadius:3,opacity:.4}}/>}
                {name}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState({ query, unified }) {
  return (
    <div className="empty">
      <div className="emoji">{React.createElement(Ic.search, {style:{width:22,height:22}})}</div>
      <div style={{fontSize:15, fontWeight:500, color:'#E4E4E7'}}>
        {unified ? 'Birleşik analiz için bir hedef girin' : 'Sorgu için bir değer girin'}
      </div>
      <div style={{fontSize:13, color:'var(--muted)', marginTop:6}}>
        {query ? <>Hazır: <span className="mono" style={{color:'#C4B5FD'}}>{query}</span> — <kbd className="kbd">Enter</kbd> ile çalıştır.</> :
                  <>Yukarıdan veri girin veya üst arama çubuğundan otomatik tip tespiti kullanın.</>}
      </div>
    </div>
  );
}

function NumStat({ label, value }) {
  return (
    <div style={{padding:'14px 16px', border:'1px solid var(--line)', borderRadius:10, background:'rgba(255,255,255,0.015)'}}>
      <div style={{fontSize:10.5, color:'var(--muted-2)', textTransform:'uppercase', letterSpacing:'0.08em'}}>{label}</div>
      <div style={{fontSize:17, marginTop:6, fontWeight:500, color:'#fff'}}>{value}</div>
    </div>
  );
}

function EvidenceTile({ title, text, badge }) {
  return (
    <div style={{padding:16, border:'1px solid var(--line)', borderRadius:10, background:'var(--panel-2)'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
        <div style={{fontSize:13, fontWeight:500, color:'#E4E4E7'}}>{title}</div>
        <Pill>{badge}</Pill>
      </div>
      <div style={{fontSize:12.5, color:'var(--muted)', lineHeight:1.6}}>{text}</div>
    </div>
  );
}

function NextStep({ title, desc, module }) {
  return (
    <div style={{padding:16, border:'1px solid var(--line)', borderRadius:10, background:'rgba(255,255,255,0.015)', cursor:'pointer', transition:'border-color .15s, background .15s'}}
         onMouseEnter={e=>{e.currentTarget.style.borderColor='rgba(124,58,237,0.30)';e.currentTarget.style.background='var(--accent-soft)'}}
         onMouseLeave={e=>{e.currentTarget.style.borderColor='var(--line)';e.currentTarget.style.background='rgba(255,255,255,0.015)'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
        <Pill kind="info">{module}</Pill>
        {React.createElement(Ic.arrowRight, {style:{width:15,height:15, color:'var(--muted)'}})}
      </div>
      <div style={{fontSize:13.5, fontWeight:500, color:'#E4E4E7', marginBottom:4}}>{title}</div>
      <div style={{fontSize:12.5, color:'var(--muted)', lineHeight:1.55}}>{desc}</div>
    </div>
  );
}

function EntityGraph() {
  // Hand-positioned, deterministic
  const nodes = [
    { x: 50, y: 50, label: 'ayşe demir',     center: true, glyph: 'A' },
    { x: 18, y: 22, label: 'ayse.demir@…',   glyph: '@' },
    { x: 82, y: 22, label: '+90 532 412…',   glyph: '☎' },
    { x: 16, y: 78, label: '@ayse.demir',    glyph: 'ig' },
    { x: 84, y: 78, label: 'kavakli-takim',  glyph: '🌐' },
    { x: 50, y: 90, label: '@ayse_d (tg)',   glyph: 'tg' },
    { x: 50, y: 12, label: 'Kavaklı Hold.',  glyph: '🏢' },
  ];
  const edges = [[0,1],[0,2],[0,3],[0,4],[0,5],[0,6],[1,2],[3,4]];
  return (
    <div className="graph">
      {edges.map(([a,b], i) => {
        const A = nodes[a], B = nodes[b];
        const dx = B.x - A.x, dy = B.y - A.y;
        const length = Math.sqrt(dx*dx + dy*dy);
        const angle = Math.atan2(dy, dx) * 180 / Math.PI;
        return (
          <div key={i} className="edge" style={{
            left: `${A.x}%`, top: `${A.y}%`,
            width: `${length}%`, transform: `rotate(${angle}deg)`,
          }}/>
        );
      })}
      {nodes.map((n, i) => (
        <div key={i} className={`node ${n.center ? 'center' : ''}`} style={{left:`${n.x}%`, top:`${n.y}%`}}>
          <div className="node-dot">{n.glyph}</div>
          <div className="node-label">{n.label}</div>
        </div>
      ))}
    </div>
  );
}

/* ============ MERSİS ============ */
function MersisModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!query) return;
    setFetching(true); setApiError(null);
    try {
      const r = await fetch(`${baseUrl}/tr/mersis?q=${encodeURIComponent(query)}`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm query={query} setQuery={setQuery}
        label="Firma adı veya vergi numarası" placeholder="örn. arcelik"
        options={options} setOptions={setOptions} onRun={runFetch}/>
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Sorgulanıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={6} title="Firma Bilgisi" icon="database">
            <KV rows={[
              ['Firma adı', apiData.results?.[0]?.company_name || apiData.company_name || '—'],
              ['Vergi no', apiData.results?.[0]?.tax_number || apiData.tax_number || '—'],
              ['MERSİS no', apiData.results?.[0]?.mersis_no || apiData.mersis_no || '—'],
              ['Durum', apiData.results?.[0]?.status || apiData.status || '—'],
              ['Adres', apiData.results?.[0]?.address || apiData.address || '—'],
              ['Tescil tarihi', apiData.results?.[0]?.registration_date || apiData.registration_date || '—'],
            ]}/>
          </Card>
          <Card span={6} title="Ham yanıt" icon="database">
            <TechBlock show={true} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>⚠ API hatası: {apiError}</div>
      ) : (
        <EmptyState query={query}/>
      )}
    </>
  );
}

/* ============ TC Kimlik ============ */
function TcModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [ad, setAd] = React.useState('');
  const [soyad, setSoyad] = React.useState('');
  const [dogumYili, setDogumYili] = React.useState('');
  const [tcNo, setTcNo] = React.useState('');
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!tcNo || !ad || !soyad || !dogumYili) return;
    setFetching(true); setApiError(null);
    try {
      const r = await fetch(`${baseUrl}/tr/tc?tc=${encodeURIComponent(tcNo)}&ad=${encodeURIComponent(ad)}&soyad=${encodeURIComponent(soyad)}&dogum_yili=${encodeURIComponent(dogumYili)}`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [tcNo, ad, soyad, dogumYili]);

  return (
    <>
      <div className="form-card">
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:12}}>
          <div className="field">
            <label className="label">Ad</label>
            <input className="input" placeholder="örn. Ayşe" value={ad} onChange={e=>setAd(e.target.value)}/>
          </div>
          <div className="field">
            <label className="label">Soyad</label>
            <input className="input" placeholder="örn. Demir" value={soyad} onChange={e=>setSoyad(e.target.value)}/>
          </div>
          <div className="field">
            <label className="label">Doğum Yılı</label>
            <input className="input mono" placeholder="örn. 1990" value={dogumYili} onChange={e=>setDogumYili(e.target.value)}/>
          </div>
          <div className="field">
            <label className="label">TC Kimlik No</label>
            <input className="input mono" placeholder="11 haneli" value={tcNo} onChange={e=>setTcNo(e.target.value)}
              onKeyDown={e=>{ if(e.key==='Enter') runFetch(); }}/>
          </div>
        </div>
        <button className="btn btn-primary" onClick={e=>{ e.preventDefault(); runFetch(); window.__argosRun?.(); }}>
          {React.createElement(Ic.search)} Doğrula
        </button>
      </div>
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Sorgulanıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={12} title="TC Kimlik Sonucu" icon="shield"
                right={<Pill kind={apiData.valid ? 'ok' : 'bad'}>{apiData.valid ? 'GEÇERLİ' : 'GEÇERSİZ'}</Pill>}>
            <Stat value={apiData.valid ? 'GEÇERLİ' : 'GEÇERSİZ'} label="Doğrulama sonucu" kind={apiData.valid ? 'ok' : 'bad'}/>
            <KV rows={[
              ['TC No', apiData.tc_no || '—'],
              ['Ad', apiData.ad || '—'],
              ['Soyad', apiData.soyad || '—'],
              ['Doğum yılı', apiData.dogum_yili || '—'],
              ['Kaynak', apiData.source || '—'],
            ]}/>
            <TechBlock show={tech} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>⚠ API hatası: {apiError}</div>
      ) : (
        <EmptyState query={tcNo}/>
      )}
    </>
  );
}

/* ============ TR Haberler ============ */
function HaberlerModule({ query, setQuery, tech, options, setOptions, ran, baseUrl }) {
  const [apiData, setApiData] = React.useState(null);
  const [apiError, setApiError] = React.useState(null);
  const [fetching, setFetching] = React.useState(false);

  const runFetch = async () => {
    if (!query) return;
    setFetching(true); setApiError(null);
    try {
      const r = await fetch(`${baseUrl}/tr/haberler?q=${encodeURIComponent(query)}&limit=20`);
      const d = await r.json();
      setApiData(d);
    } catch(e) { setApiError(e.message); }
    finally { setFetching(false); }
  };
  window.__activeRunFetch = runFetch;
  React.useEffect(() => { window.__activeRunFetch = runFetch; }, [query]);

  return (
    <>
      <ModuleForm query={query} setQuery={setQuery}
        label="Arama terimi" placeholder="örn. teknoloji, ahmet yılmaz"
        options={options} setOptions={setOptions} onRun={runFetch}/>
      {fetching ? (
        <div className="empty"><div style={{color:'var(--muted)'}}>Haberler aranıyor…</div></div>
      ) : apiData ? (
        <div className="results">
          <Card span={12} title="Haberler" icon="search"
                right={<Pill>{apiData.total} sonuç</Pill>}>
            <div className="list">
              {(apiData.results || []).map((r, i) => (
                <ListItem key={i}
                  icon={r.source?.[0]?.toUpperCase()}
                  title={r.title}
                  sub={r.source}
                  right={r.date?.slice(0, 10)}/>
              ))}
              {!apiData.results?.length && <div style={{fontSize:13,color:'var(--muted)'}}>Haber bulunamadı.</div>}
            </div>
            <TechBlock show={tech} data={apiData}/>
          </Card>
        </div>
      ) : apiError ? (
        <div style={{padding:'10px 14px', background:'rgba(248,113,113,0.08)',
          border:'1px solid rgba(248,113,113,0.20)', borderRadius:8, margin:16,
          fontSize:13, color:'#FCA5A5'}}>⚠ API hatası: {apiError}</div>
      ) : (
        <EmptyState query={query}/>
      )}
    </>
  );
}

Object.assign(window, {
  MosintModule, PhoneModule, DarkwebModule, DomainModule,
  IgBioModule, FaceModule, GeoModule, UnifiedModule,
  MersisModule, TcModule, HaberlerModule,
  ModuleForm, EmptyState, EntityGraph
});
