/* App shell: sidebar + smart bar + module switching */
const { Ic, MODULES, SECTIONS, detectType, TYPE_LABEL, DEMO_QUERY } = window;
const { MosintModule, PhoneModule, DarkwebModule, DomainModule, IgBioModule, FaceModule, GeoModule, UnifiedModule, MersisModule, TcModule, HaberlerModule } = window;

const MODULE_RENDERERS = {
  mosint:  MosintModule,
  phone:   PhoneModule,
  darkweb: DarkwebModule,
  domain:  DomainModule,
  igbio:   IgBioModule,
  face:    FaceModule,
  geo:     GeoModule,
  unified: UnifiedModule,
  mersis:  MersisModule,
  tc:      TcModule,
  haberler:HaberlerModule,
};

/* type → preferred module suggestion */
const TYPE_TO_MODULE = {
  email:  'mosint',
  phone:  'phone',
  domain: 'domain',
  handle: 'igbio',
  image:  'face',
};

function App() {
  const [activeId, setActiveId] = React.useState('unified');
  const [smartValue, setSmartValue] = React.useState('');
  const [moduleQuery, setModuleQuery] = React.useState(DEMO_QUERY['unified']);
  const [tech, setTech] = React.useState(false);
  const [options, setOptions] = React.useState({});
  const [loading, setLoading] = React.useState(false);
  const [ran, setRan] = React.useState(false);
  const [smartFocused, setSmartFocused] = React.useState(false);

  const active = MODULES.find(m => m.id === activeId);
  const Renderer = MODULE_RENDERERS[activeId];

  // When switching module, reset query to the module's demo and mark "ran"
  React.useEffect(() => {
    setModuleQuery(DEMO_QUERY[activeId] || '');
    setRan(true); // we keep the canned results visible per module
  }, [activeId]);

  // Smart bar live type
  const detected = detectType(smartValue);

  // Run callback wired up via window so the form button inside the form can fire it
  window.__argosRun = () => {
    window.__activeRunFetch?.();
  };

  const baseUrl = window.location.origin;
  window.__argosBaseUrl = baseUrl;

  const runSmart = () => {
    const v = smartValue.trim();
    if (!v) return;
    const det = detectType(v);
    const target = det ? TYPE_TO_MODULE[det] : 'unified';
    setActiveId(target);
    setModuleQuery(v);
    setSmartValue('');
    setLoading(true); setRan(false);
    setTimeout(() => { setLoading(false); setRan(true); }, 650);
  };

  // Keyboard shortcut: ⌘K / Ctrl+K focuses smart bar
  React.useEffect(() => {
    const h = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        document.getElementById('smart-input')?.focus();
      }
    };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, []);

  return (
    <div className="app">
      {/* ----------- Sidebar ----------- */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">A</div>
          <div>
            <div className="brand-name">Argos</div>
            <div className="brand-tag">OSINT Platform</div>
          </div>
        </div>

        <nav className="nav">
          {SECTIONS.map((sec) => (
            <div key={sec.title}>
              <div className="nav-section">{sec.title}</div>
              {sec.items.map((id) => {
                const m = MODULES.find(mm => mm.id === id);
                if (!m) return null;
                return (
                  <div
                    key={m.id}
                    className={`nav-item ${activeId === m.id ? 'active' : ''}`}
                    onClick={() => setActiveId(m.id)}
                  >
                    <span className="ic">{React.createElement(Ic[m.icon] || Ic.layers)}</span>
                    <span>{m.short || m.name}</span>
                    {m.badge && <span className="badge">{m.badge}</span>}
                  </div>
                );
              })}
            </div>
          ))}

          <div className="nav-section" style={{marginTop:8}}>Çalışma alanı</div>
          <div className="nav-item">
            <span className="ic">{React.createElement(Ic.history)}</span>
            <span>Geçmiş sorgular</span>
            <span className="badge">42</span>
          </div>
          <div className="nav-item">
            <span className="ic">{React.createElement(Ic.bookmark)}</span>
            <span>Kayıtlı vakalar</span>
          </div>
          <div className="nav-item">
            <span className="ic">{React.createElement(Ic.settings)}</span>
            <span>Ayarlar</span>
          </div>
        </nav>

        <div className="sidebar-foot">
          <div className="avatar">MS</div>
          <div className="foot-meta">
            <div className="foot-name">Mehmet Soylu</div>
            <div className="foot-role"><span className="dot"/> Analist · Çevrimiçi</div>
          </div>
        </div>
      </aside>

      {/* ----------- Main ----------- */}
      <main className="main">
        <div className="topbar">
          <div className="smartbar">
            {React.createElement(Ic.search, {style:{width:16,height:16}})}
            <input
              id="smart-input"
              placeholder={smartFocused ? 'e-posta, telefon, alan adı, kullanıcı adı veya görsel URL…' : 'Akıllı arama — herhangi bir hedef yapıştır (⌘K)'}
              value={smartValue}
              onChange={(e) => setSmartValue(e.target.value)}
              onFocus={() => setSmartFocused(true)}
              onBlur={() => setSmartFocused(false)}
              onKeyDown={(e) => { if (e.key === 'Enter') runSmart(); }}
            />
            {detected ? (
              <span className={`type-pill ${TYPE_LABEL[detected].cls}`}>
                <span className="pdot"/> {TYPE_LABEL[detected].tr}
              </span>
            ) : smartValue.trim() ? (
              <span className="type-pill">tip belirsiz</span>
            ) : (
              <span className="kbd">⌘K</span>
            )}
            {detected && (
              <button
                className="btn btn-primary"
                style={{padding:'6px 12px', fontSize:12, height:30}}
                onClick={runSmart}
              >
                {MODULES.find(m => m.id === TYPE_TO_MODULE[detected])?.short || 'Çalıştır'}
                {React.createElement(Ic.arrowRight, {style:{width:13,height:13}})}
              </button>
            )}
          </div>

          <div className="top-actions">
            <button className="icon-btn" title="Bildirimler">{React.createElement(Ic.bell, {style:{width:16,height:16}})}</button>
            <button className="icon-btn" title="Dışa aktar">{React.createElement(Ic.download, {style:{width:16,height:16}})}</button>
            <button className="icon-btn" title="Filtrele">{React.createElement(Ic.filter, {style:{width:16,height:16}})}</button>
          </div>
        </div>

        <div className="content">
          <div className="module-header">
            <div className="module-title">
              <div className="module-icon">{React.createElement(Ic[active.icon] || Ic.layers, {style:{width:22,height:22}})}</div>
              <div>
                <h1 className="module-name">
                  {active.name}
                  {active.badge && (
                    <span style={{
                      marginLeft:10, fontSize:11, fontWeight:600,
                      verticalAlign:'middle',
                      padding:'3px 8px', borderRadius:5,
                      background:'rgba(124,58,237,0.20)', color:'#C4B5FD',
                      border:'1px solid rgba(124,58,237,0.30)',
                      letterSpacing:'0.04em'
                    }}>{active.badge}</span>
                  )}
                </h1>
                <p className="module-desc">{active.desc}</p>
              </div>
            </div>

            <div className={`toggle ${tech ? 'on' : ''}`} onClick={() => setTech(!tech)}>
              <span className="sw"/>
              <span>Teknik Detaylar</span>
            </div>
          </div>

          {loading ? (
            <div className="empty" style={{paddingTop:60, paddingBottom:60}}>
              <div className="emoji"><span className="spin"/></div>
              <div style={{fontSize:15, fontWeight:500, color:'#E4E4E7'}}>Sorgu çalıştırılıyor</div>
              <div style={{fontSize:13, color:'var(--muted)', marginTop:6}} className="mono">
                {moduleQuery || smartValue}
              </div>
            </div>
          ) : (
            React.createElement(Renderer, {
              query: moduleQuery,
              setQuery: setModuleQuery,
              tech,
              options, setOptions,
              ran,
              baseUrl,
            })
          )}
        </div>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
