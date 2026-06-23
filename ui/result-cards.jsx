/* Reusable card primitives */
const { Ic } = window;

function Card({ span = 6, title, icon, right, children, className = '' }) {
  return (
    <div className={`card span-${span} ${className}`}>
      <div className="card-head">
        <div className="card-title">
          {icon ? React.createElement(Ic[icon] || Ic.layers) : null}
          <span>{title}</span>
        </div>
        {right}
      </div>
      {children}
    </div>
  );
}

function Pill({ kind = '', children }) {
  return <span className={`badge-pill ${kind}`}>{children}</span>;
}

function KV({ rows }) {
  return (
    <dl className="kv">
      {rows.map(([k, v], i) => (
        <React.Fragment key={i}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function Summary({ title = 'Özet', children }) {
  return (
    <div className="summary-box">
      <div className="ic">{React.createElement(Ic.sparkle)}</div>
      <div>
        <div className="summary-title">{title}</div>
        <div className="summary-text">{children}</div>
      </div>
    </div>
  );
}

function TechBlock({ data, show }) {
  if (!show) return null;
  const lines = JSON.stringify(data, null, 2)
    .split('\n')
    .map((line, i) => {
      const colored = line
        .replace(/("[^"]+")(\s*:)/g, '<span class="k">$1</span>$2')
        .replace(/:\s*("[^"]*")/g, ': <span class="s">$1</span>')
        .replace(/:\s*(true|false|null)/g, ': <span class="n">$1</span>')
        .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="n">$1</span>');
      return <div key={i} dangerouslySetInnerHTML={{ __html: colored || '&nbsp;' }} />;
    });
  return <div className="tech-block">{lines}</div>;
}

function Stat({ value, label, kind = '' }) {
  return (
    <div className="stat">
      <div className={`stat-num ${kind}`}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function ListItem({ icon, title, sub, right, badge, badgeKind }) {
  return (
    <div className="list-item">
      {icon !== undefined && <div className="list-icon">{icon}</div>}
      <div className="list-body">
        <div className="list-title">
          {title}
          {badge && <Pill kind={badgeKind}>{badge}</Pill>}
        </div>
        {sub && <div className="list-sub">{sub}</div>}
      </div>
      {right && <div className="list-meta">{right}</div>}
    </div>
  );
}

function Heat({ value = 0, max = 10 }) {
  return (
    <div className="heat">
      {Array.from({ length: max }, (_, i) => {
        const ratio = (i + 1) / max;
        const filled = i < value;
        const intensity = filled ? Math.min(4, Math.ceil(ratio * 4)) : 0;
        return <span key={i} className={filled ? `h${intensity}` : ''} />;
      })}
    </div>
  );
}

window.Card = Card;
window.Pill = Pill;
window.KV = KV;
window.Summary = Summary;
window.TechBlock = TechBlock;
window.Stat = Stat;
window.ListItem = ListItem;
window.Heat = Heat;
