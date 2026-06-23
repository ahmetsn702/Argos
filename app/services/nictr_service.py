import httpx
import re
from datetime import datetime
from bs4 import BeautifulSoup


NICTR_URL = "https://whois.nic.tr/cgi-bin/whois.cgi?query={domain}"


async def query_nictr(domain: str) -> dict:
    domain = domain.strip().lower()
    if not domain.endswith(".tr"):
        return None

    url = NICTR_URL.format(domain=domain)

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        return {
            "error": str(exc),
            "domain": domain,
            "source": "nic.tr",
        }

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # NIC.tr sonuçları genelde <pre> veya düz metin olarak gelir.
    # Önce <pre> bloğunu deneriz; yoksa sayfadaki tüm metni normalize ederiz.
    pre = soup.find("pre")
    text = pre.get_text() if pre else soup.get_text()
    text = " ".join(text.split())  # fazla boşlukları temizle

    def _find(patterns, src):
        for pat in patterns:
            m = re.search(pat, src, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    registrant = _find(
        [
            r"Registrant\s*[:\-]\s*([^\n]+)",
            r"Ad[ /]Name\s*[:\-]\s*([^\n]+)",
            r"Organization\s*[:\-]\s*([^\n]+)",
        ],
        text,
    )

    registrar = _find(
        [
            r"Registrar\s*[:\-]\s*([^\n]+)",
            r"Registrar Name\s*[:\-]\s*([^\n]+)",
        ],
        text,
    )

    created = _find(
        [
            r"Created\s*(?:on)?\s*[:\-]\s*([^\n]+)",
            r"Registration Date\s*[:\-]\s*([^\n]+)",
            r"Domain Registration Date\s*[:\-]\s*([^\n]+)",
        ],
        text,
    )

    expires = _find(
        [
            r"Expires\s*(?:on)?\s*[:\-]\s*([^\n]+)",
            r"Expiration Date\s*[:\-]\s*([^\n]+)",
            r"Domain Expiration Date\s*[:\-]\s*([^\n]+)",
        ],
        text,
    )

    # Nameserver(ler): tek veya çoklu satır olabilir
    ns_patterns = [
        r"Name Server\s*[:\-]\s*([^\n]+)",
        r"Nameserver\s*[:\-]\s*([^\n]+)",
        r"Name Servers?\s*[:\-]\s*([^\n]+)",
        r"NS\s*[:\-]\s*([^\n]+)",
    ]
    nameservers = []
    for pat in ns_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            candidate = m.group(1).strip()
            # Birden fazla NS virgül/boşluk/noktalı virgülle ayrılmış olabilir
            for part in re.split(r"[,;\s]+", candidate):
                part = part.strip().rstrip(".")
                if part and part not in nameservers:
                    nameservers.append(part)

    # Tarihleri ISO formatına çevirmeye çalış (çeşitli formatları dene)
    def _to_iso(val):
        if not val:
            return None
        for fmt in (
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%d/%m/%Y",
            "%Y.%m.%d",
            "%Y/%m/%d",
            "%d-%b-%Y",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                return datetime.strptime(val, fmt).isoformat()
            except ValueError:
                continue
        return val

    return {
        "domain": domain,
        "registrant": registrant,
        "registrar": registrar,
        "created": _to_iso(created),
        "expires": _to_iso(expires),
        "nameservers": nameservers,
        "source": "nic.tr",
    }
