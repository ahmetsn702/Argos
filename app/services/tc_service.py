"""TC Kimlik No doğrulama — NVI SOAP servisi."""
import re
import httpx
from bs4 import BeautifulSoup

_NVI_URL = "https://tckimlik.nvi.gov.tr/Service/KPSPublic.asmx"
_TIMEOUT = 15.0

_SOAP_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <TCKimlikNoDogrula xmlns="http://tckimlik.nvi.gov.tr/WS">
      <TCKimlikNo>{tc_no}</TCKimlikNo>
      <Ad>{ad}</Ad>
      <Soyad>{soyad}</Soyad>
      <DogumYili>{dogum_yili}</DogumYili>
    </TCKimlikNoDogrula>
  </soap:Body>
</soap:Envelope>"""


def _validate_tc(tc_no: str) -> bool:
    return bool(re.fullmatch(r"\d{11}", tc_no))


def _tr_upper(s: str) -> str:
    table = str.maketrans({
        'ı':'I', 'i':'İ', 'ş':'Ş', 'ğ':'Ğ', 'ü':'Ü', 'ö':'Ö', 'ç':'Ç',
        'I':'I', 'İ':'İ', 'Ş':'Ş', 'Ğ':'Ğ', 'Ü':'Ü', 'Ö':'Ö', 'Ç':'Ç',
    })
    return s.translate(table).upper()


async def verify_tc(tc_no: str, ad: str, soyad: str, dogum_yili: int) -> dict:
    if not _validate_tc(tc_no):
        return {"valid": False, "tc_no": tc_no, "ad": ad, "soyad": soyad,
                "dogum_yili": dogum_yili, "error": "TC kimlik no 11 haneli rakam olmalı", "source": "nvi"}
    body = _SOAP_TEMPLATE.format(
        tc_no=tc_no,
        ad=_tr_upper(ad),
        soyad=_tr_upper(soyad),
        dogum_yili=dogum_yili,
    )
    print(f"[tc_service] REQUEST BODY:\n{body}")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, verify=False) as client:
            r = await client.post(
                _NVI_URL,
                content=body.encode("utf-8"),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "http://tckimlik.nvi.gov.tr/WS/TCKimlikNoDogrula",
                },
            )
        print(f"[tc_service] RESPONSE STATUS: {r.status_code}")
        print(f"[tc_service] RESPONSE TEXT: {r.text}")
        soup = BeautifulSoup(r.text, "xml")
        result_tag = soup.find("TCKimlikNoDogrulaResult")
        valid = result_tag is not None and result_tag.get_text(strip=True).lower() == "true"
        return {"valid": valid, "tc_no": tc_no, "ad": ad, "soyad": soyad,
                "dogum_yili": dogum_yili, "source": "nvi"}
    except Exception as e:
        import traceback
        print(f"[tc_service] EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"valid": False, "tc_no": tc_no, "ad": ad, "soyad": soyad,
                "dogum_yili": dogum_yili, "error": str(e), "source": "nvi"}
