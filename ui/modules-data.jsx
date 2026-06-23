/* Module registry and demo data — all Turkish facing copy */
const MODULES = [
  { id: 'unified',  name: 'Unified Analysis', short: 'Birleşik Analiz', icon: 'sparkle', desc: 'Tüm modüllerin sonuçlarını otomatik birleştirir ve varlık grafı çıkarır.', accepts: ['email','phone','domain','handle','image'], badge: 'AI' },
  { id: 'mosint',   name: 'MOSINT',           short: 'E-posta İstihbaratı', icon: 'mail',  desc: 'E-posta adresinden hesap bağlantıları, sızıntılar ve metadata.', accepts: ['email'] },
  { id: 'phone',    name: 'Telefon',          short: 'Telefon Numarası', icon: 'phone', desc: 'Operatör, hat tipi, mesajlaşma uygulamaları ve sosyal hesaplar.', accepts: ['phone'] },
  { id: 'darkweb',  name: 'Dark Web',         short: 'Dark Web Tarama', icon: 'spider', desc: 'Forum, market ve paste sitelerinde geçen referansları arar.', accepts: ['email','handle','domain'] },
  { id: 'domain',   name: 'Domain',           short: 'Alan Adı', icon: 'globe', desc: 'WHOIS, DNS, subdomain ve teknoloji yığını tespiti.', accepts: ['domain'] },
  { id: 'igbio',    name: 'IG Bio',           short: 'Instagram Bio', icon: 'instagram', desc: 'Kullanıcı adı, biyografi analizi ve dış link çıkarımı.', accepts: ['handle'] },
  { id: 'face',     name: 'Yüz Tanıma',       short: 'Yüz Tanıma', icon: 'face', desc: 'Görselden tespit edilen yüzleri açık kaynaklarla eşleştirir.', accepts: ['image'] },
  { id: 'geo',      name: 'Geo Photo',        short: 'Konum Çıkarımı', icon: 'pin', desc: 'EXIF, görsel ipuçları ve referans noktalarından konum tahmini.', accepts: ['image'] },
  { id: 'mersis',   name: 'MERSİS',           short: 'Firma Sorgula',  icon: 'database', desc: 'Firma adı veya vergi numarasıyla MERSİS kayıtlarını sorgular.', accepts: ['domain'] },
  { id: 'tc',       name: 'TC Kimlik',        short: 'TC Doğrulama',   icon: 'shield',   desc: 'Ad, soyad ve doğum yılıyla TC kimlik numarasını doğrular.', accepts: [] },
  { id: 'haberler', name: 'TR Haberler',      short: 'Haber Tarama',   icon: 'search',   desc: 'Türk haber kaynaklarında isim veya konu araması yapar.', accepts: ['handle'] },
];

const SECTIONS = [
  { title: 'Genel', items: ['unified'] },
  { title: 'Modüller', items: ['mosint','phone','darkweb','domain','igbio'] },
  { title: 'Görsel', items: ['face','geo'] },
  { title: 'Türkiye', items: ['mersis','tc','haberler'] },
];

/* ---------- Type detection ---------- */
function detectType(value) {
  const v = (value || '').trim();
  if (!v) return null;
  if (/^@?[a-z0-9_.]{2,30}$/i.test(v) && !v.includes('.') && !/^\+?\d/.test(v) && /^@/.test(v)) return 'handle';
  if (/^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$/i.test(v)) return 'email';
  if (/^\+?[0-9 ()\-]{7,}$/.test(v)) return 'phone';
  if (/^https?:\/\//i.test(v) && /\.(jpg|jpeg|png|webp|gif)(\?|$)/i.test(v)) return 'image';
  if (/^[a-z0-9-]+(\.[a-z0-9-]+)+$/i.test(v)) return 'domain';
  if (/^@[a-z0-9_.]+$/i.test(v)) return 'handle';
  return null;
}

const TYPE_LABEL = {
  email:  { code: 'EMAIL',   tr: 'E-posta',          cls: 't-email'  },
  phone:  { code: 'PHONE',   tr: 'Telefon',          cls: 't-phone'  },
  domain: { code: 'DOMAIN',  tr: 'Alan adı',         cls: 't-domain' },
  image:  { code: 'IMAGE',   tr: 'Görsel URL',       cls: 't-image'  },
  handle: { code: 'HANDLE',  tr: 'Kullanıcı adı',    cls: 't-handle' },
};

/* ---------- Module → demo query mapping ---------- */
const DEMO_QUERY = {
  unified: 'ayse.demir@outlook.com',
  mosint:  'ayse.demir@outlook.com',
  phone:   '+90 532 412 88 17',
  darkweb: 'ayse.demir',
  domain:  'kavakli-holding.com.tr',
  igbio:   '@ayse.demir',
  face:    'subject_42.jpg',
  geo:     'IMG_20240811_173204.jpg',
  mersis:  'arcelik',
  tc:      '',
  haberler:'teknoloji',
};

window.MODULES = MODULES;
window.SECTIONS = SECTIONS;
window.detectType = detectType;
window.TYPE_LABEL = TYPE_LABEL;
window.DEMO_QUERY = DEMO_QUERY;
