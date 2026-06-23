import asyncio
import io
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER

# Colors
ACCENT = colors.HexColor("#2ecc71")
MUTED = colors.HexColor("#7ddfb2")
TEXT_MAIN = colors.HexColor("#1a1a1a")
PANEL = colors.HexColor("#f0f7f3")
DANGER = colors.HexColor("#e74c3c")
HEADER_BG = colors.HexColor("#1a2e22")

# Styles
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "FootprintTitle", parent=styles["Title"],
    fontSize=22, textColor=ACCENT, spaceAfter=6,
    alignment=TA_CENTER, fontName="Helvetica-Bold"
)
section_style = ParagraphStyle(
    "SectionHeader", parent=styles["Heading1"],
    fontSize=13, textColor=ACCENT, spaceBefore=14,
    spaceAfter=4, fontName="Helvetica-Bold"
)
normal_style = ParagraphStyle(
    "FootprintNormal", parent=styles["Normal"],
    fontSize=9, textColor=TEXT_MAIN, spaceAfter=3, fontName="Helvetica"
)
meta_style = ParagraphStyle(
    "MetaStyle", parent=styles["Normal"],
    fontSize=8, textColor=colors.HexColor("#5a7a5a"), fontName="Helvetica"
)


def _default_table_style():
    return TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PANEL),
        ("TEXTCOLOR", (0, 0), (0, -1), ACCENT),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT_MAIN),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c0d8c8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])


def _header_table_style():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), ACCENT),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), TEXT_MAIN),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c0d8c8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


# Safe wrappers
async def _safe_mosint(email, timeout):
    try:
        from app.routers.mosint_api import mosint_full
        return await mosint_full(email=email, timeout=timeout)
    except Exception as e:
        return {"error": str(e), "ok": False}


async def _safe_hibp(email, timeout):
    try:
        from app.services.hibp_service import hibp_breached_account
        return await hibp_breached_account(email, timeout)
    except Exception as e:
        return {"error": str(e), "ok": False}


async def _safe_instagram(username):
    try:
        from app.services.instagram_service import fetch_bio_instagram
        return await fetch_bio_instagram(username)
    except Exception as e:
        return {"error": str(e), "ok": False}


async def _safe_x(username):
    try:
        from app.services.x_fetch import fetch_x_profile_simple
        return await asyncio.to_thread(fetch_x_profile_simple, username)
    except Exception as e:
        return {"error": str(e), "ok": False}


async def _safe_phone(phone, timeout):
    try:
        from app.services.phone_service import phone_osint
        return await phone_osint(phone, timeout)
    except Exception as e:
        return {"error": str(e), "ok": False}


async def _collect_data(email, username, phone, timeout):
    tasks = {}
    if email:
        tasks["email"] = asyncio.create_task(_safe_mosint(email, timeout))
        tasks["hibp"] = asyncio.create_task(_safe_hibp(email, timeout))
    if username:
        tasks["instagram"] = asyncio.create_task(_safe_instagram(username))
        tasks["twitter"] = asyncio.create_task(_safe_x(username))
    if phone:
        tasks["phone"] = asyncio.create_task(_safe_phone(phone, timeout))

    results = {}
    for key, task in tasks.items():
        try:
            results[key] = await asyncio.wait_for(task, timeout=timeout)
        except Exception as e:
            results[key] = {"error": str(e)}
    return results


def _s(val, maxlen=120):
    """Safely convert to string and truncate."""
    if val is None:
        return "-"
    return str(val)[:maxlen]


def _build_header(story, email, username, phone):
    story.append(Paragraph("FOOTPRINT OSINT RAPORU", title_style))
    story.append(Paragraph(
        f"Olusturulma: {datetime.now().strftime('%d.%m.%Y %H:%M:%S UTC+3')}", meta_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
    story.append(Spacer(1, 8))

    target_rows = []
    if email:
        target_rows.append(["E-posta", email])
    if username:
        target_rows.append(["Kullanici Adi", username])
    if phone:
        target_rows.append(["Telefon", phone])

    if target_rows:
        t = Table(target_rows, colWidths=[4 * cm, 13 * cm])
        t.setStyle(_default_table_style())
        story.append(t)
    story.append(Spacer(1, 12))


def _build_email_section(story, data):
    story.append(Paragraph("E-POSTA ANALIZI", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    story.append(Spacer(1, 4))

    mosint = data.get("email", {})
    if mosint.get("error"):
        story.append(Paragraph(f"Hata: {mosint['error']}", normal_style))
    else:
        rows = []
        # Extract from mosint sources
        sources = mosint.get("sources", {})
        abstract = sources.get("abstract_email", {})
        if abstract.get("ok"):
            rows.append(["Teslim Edilebilir", _s(abstract.get("deliverable"))])
            rows.append(["SMTP Gecerli", _s(abstract.get("is_smtp_valid"))])
            rows.append(["Ucretsiz Email", _s(abstract.get("is_free_email"))])
            rows.append(["Tek Kullanimlik", _s(abstract.get("is_disposable"))])
            rows.append(["Saglayici", _s(abstract.get("provider"))])

        gravatar = sources.get("gravatar", {})
        if gravatar.get("exists"):
            rows.append(["Gravatar", "Mevcut"])

        mx = sources.get("mx", {})
        servers = mx.get("servers", [])
        if servers:
            mx_str = ", ".join(s.get("host", "") for s in servers[:3])
            rows.append(["MX Sunuculari", _s(mx_str)])

        rows.append(["Verdict", _s(mosint.get("verdict"))])

        if rows:
            t = Table(rows, colWidths=[5 * cm, 12 * cm])
            t.setStyle(_default_table_style())
            story.append(t)

    # HIBP
    hibp = data.get("hibp", {})
    story.append(Spacer(1, 6))
    story.append(Paragraph("Veri Ihlali Kontrolu (HIBP)", section_style))
    if hibp.get("error"):
        story.append(Paragraph(f"HIBP kontrol edilemedi: {hibp.get('error','')}", normal_style))
    elif isinstance(hibp, dict) and hibp.get("breaches"):
        breaches = hibp["breaches"]
        breach_rows = [["Ihlal Adi", "Tarih", "Etkilenen Veri"]]
        for b in breaches[:15]:
            breach_rows.append([
                _s(b.get("Name", "?"), 30),
                _s(b.get("BreachDate", "?"), 12),
                _s(", ".join(b.get("DataClasses", [])), 60)
            ])
        t = Table(breach_rows, colWidths=[5 * cm, 3 * cm, 9 * cm])
        t.setStyle(_header_table_style())
        story.append(t)
    else:
        story.append(Paragraph("Bilinen bir veri ihlali bulunamadi.", normal_style))
    story.append(Spacer(1, 10))


def _build_social_section(story, data):
    story.append(Paragraph("SOSYAL MEDYA", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    story.append(Spacer(1, 4))

    platforms = [
        ("Instagram", data.get("instagram", {})),
        ("X (Twitter)", data.get("twitter", {})),
    ]

    rows = [["Platform", "Durum", "Gorunen Ad", "Bio"]]
    for name, pdata in platforms:
        if not pdata or pdata.get("error"):
            rows.append([name, _s(pdata.get("error", "Hata")), "-", "-"])
            continue
        status = _s(pdata.get("status", pdata.get("exists", "?")))
        display = _s(pdata.get("display_name", pdata.get("full_name", "")), 30)
        bio = _s(pdata.get("bio", pdata.get("biography", "")), 80)
        rows.append([name, status, display, bio])

    if len(rows) > 1:
        t = Table(rows, colWidths=[3 * cm, 2.5 * cm, 4.5 * cm, 7 * cm])
        t.setStyle(_header_table_style())
        story.append(t)
    story.append(Spacer(1, 10))


def _build_phone_section(story, data):
    phone_data = data.get("phone", {})
    if not phone_data:
        return
    story.append(Paragraph("TELEFON ANALIZI", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    story.append(Spacer(1, 4))

    rows = []
    # numverify
    nv = phone_data.get("numverify", {})
    if nv.get("ok"):
        rows.append(["Gecerli", _s(nv.get("valid"))])
        rows.append(["Ulke", _s(nv.get("country"))])
        rows.append(["Operator", _s(nv.get("carrier"))])
        rows.append(["Hat Tipi", _s(nv.get("line_type"))])

    # abstract
    ab = phone_data.get("abstract", {})
    if ab.get("ok"):
        rows.append(["Operator (Abstract)", _s(ab.get("carrier"))])
        rows.append(["Hat Tipi (Abstract)", _s(ab.get("line_type"))])
        rows.append(["Ulke", _s(ab.get("country"))])
        rows.append(["Sehir", _s(ab.get("city"))])
        rows.append(["Zaman Dilimi", _s(ab.get("timezone"))])

    if rows:
        t = Table(rows, colWidths=[5 * cm, 12 * cm])
        t.setStyle(_default_table_style())
        story.append(t)
    story.append(Spacer(1, 10))


def _build_verdict_section(story, data, email, username, phone):
    story.append(PageBreak())
    story.append(Paragraph("OZET", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 8))

    findings = []
    if data.get("email") and not data["email"].get("error"):
        findings.append(("E-posta analizi tamamlandi", ACCENT))
    hibp = data.get("hibp", {})
    if isinstance(hibp, dict) and hibp.get("breaches"):
        count = len(hibp["breaches"])
        findings.append((f"{count} veri ihlali tespit edildi", DANGER))
    elif isinstance(hibp, dict) and not hibp.get("error"):
        findings.append(("Veri ihlali bulunamadi", ACCENT))
    if data.get("instagram", {}).get("status") == "exists":
        findings.append(("Instagram profili bulundu", ACCENT))
    if data.get("twitter", {}).get("status") == "exists":
        findings.append(("X (Twitter) profili bulundu", ACCENT))
    if data.get("phone") and not data["phone"].get("error"):
        findings.append(("Telefon dogrulandi", ACCENT))

    for text, color in findings:
        style = ParagraphStyle("vi", parent=normal_style, textColor=color, fontSize=10, spaceBefore=4)
        story.append(Paragraph(f"- {text}", style))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Bu rapor Footprint OSINT v4.0 tarafindan otomatik olarak olusturulmustur. "
        "Bilgiler kamuya acik kaynaklardan derlenmektedir.",
        ParagraphStyle("disc", parent=normal_style, textColor=colors.HexColor("#888888"), fontSize=7)
    ))


async def generate_osint_report(
    email: Optional[str] = None,
    username: Optional[str] = None,
    phone: Optional[str] = None,
    timeout: float = 20.0
) -> bytes:
    data = await _collect_data(email, username, phone, timeout)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title="Footprint OSINT Raporu", author="Footprint v4.0",
    )

    story = []
    _build_header(story, email, username, phone)

    if email:
        _build_email_section(story, data)
    if username:
        _build_social_section(story, data)
    if phone:
        _build_phone_section(story, data)

    _build_verdict_section(story, data, email, username, phone)
    doc.build(story)
    return buf.getvalue()
