"""
pdf_export.py
Bangun laporan PDF lengkap dari state aplikasi (DATA) & hasil hitung (RESULT):
Dashboard (ringkasan + gauge per platform), detail Infra/Storage/Network,
Riwayat Bulanan (grafik per produk), Forecast & Scenario (grafik per produk),
Rekomendasi, dan Renewal. Tidak ada logika UI Streamlit di sini.
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import calculator as calc

# Kalau ada Chromium hasil install lokal (mis. Playwright di sandbox dev), pakai itu
# supaya kaleido tidak perlu download Chrome sendiri. Di Streamlit Cloud baris ini
# tidak berefek (path tidak ada) dan kaleido akan pakai/​unduh Chrome miliknya sendiri.
if "BROWSER_PATH" not in os.environ:
    for _candidate in ("/opt/pw-browsers/chromium",):
        if os.path.isfile(_candidate):
            os.environ["BROWSER_PATH"] = _candidate
            break

STATUS_COLOR_HEX = {
    "HIJAU": colors.HexColor("#16a34a"),
    "KUNING": colors.HexColor("#f59e0b"),
    "MERAH": colors.HexColor("#dc2626"),
    "OK": colors.HexColor("#16a34a"),
    "WARNING": colors.HexColor("#f59e0b"),
    "OVER CAPACITY": colors.HexColor("#dc2626"),
    "NEED TO INCREASE": colors.HexColor("#dc2626"),
    "CONSIDER TO INCREASE": colors.HexColor("#f59e0b"),
    "UNDER UTILIZE": colors.HexColor("#3b82f6"),
    "NORMAL": colors.HexColor("#16a34a"),
    "SUDAH LEWAT": colors.HexColor("#dc2626"),
    "MENDEKATI": colors.HexColor("#f59e0b"),
    "AMAN": colors.HexColor("#16a34a"),
}


def _fmt(n: Any, dec: int = 2) -> str:
    try:
        return f"{float(n):,.{dec}f}"
    except (TypeError, ValueError):
        return str(n)


def _fig_to_image(fig: go.Figure, width_cm: float, height_cm: float) -> Optional[Image]:
    """Render figure plotly jadi gambar PNG untuk disisipkan ke PDF.
    Kalau gagal (mis. kaleido/Chrome tidak tersedia), kembalikan None supaya
    laporan tetap jadi tanpa chart itu, bukan gagal total."""
    try:
        img_bytes = fig.to_image(format="png", width=int(width_cm * 55), height=int(height_cm * 55), scale=1.5)
        return Image(io.BytesIO(img_bytes), width=width_cm * cm, height=height_cm * cm)
    except Exception:
        return None


def _gauge_fig(title: str, used: float, total: float) -> go.Figure:
    pct = calc.safe_div(used, total) * 100
    status = calc.status_global(pct)
    color = calc.STATUS_COLOR.get(status, "#6b7280")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "font": {"size": 26}},
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, 120]},
            "bar": {"color": color, "thickness": 0.75},
            "steps": [
                {"range": [0, 80], "color": "#dcfce7"},
                {"range": [80, 100], "color": "#fef3c7"},
                {"range": [100, 120], "color": "#fee2e2"},
            ],
            "threshold": {"line": {"color": "#0f172a", "width": 2}, "thickness": 0.8, "value": 100},
        },
    ))
    fig.update_layout(margin=dict(l=15, r=15, t=40, b=10), paper_bgcolor="white")
    return fig


_HEADER_STYLE = ParagraphStyle(
    "HeaderCell", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white,
)


def _styled_table(header: List[str], rows: List[List[Any]], status_col: int | None = None,
                   col_widths: List[float] | None = None, wrap_header: bool = False) -> Table:
    header_row = [Paragraph(h, _HEADER_STYLE) for h in header] if wrap_header else header
    data = [header_row] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if status_col is not None:
        for i, row in enumerate(rows, start=1):
            status_val = str(row[status_col])
            color = STATUS_COLOR_HEX.get(status_val)
            if color:
                style.append(("TEXTCOLOR", (status_col, i), (status_col, i), color))
                style.append(("FONTNAME", (status_col, i), (status_col, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------------------
# Helper akses data (mandiri, tanpa bergantung ke app.py agar tak circular import)
# ---------------------------------------------------------------------------

def _platform_names(data: Dict[str, Any]) -> List[str]:
    return [p["platform"] for p in data.get("platforms", [])]


def _produk_for_platform(data: Dict[str, Any], platform: str) -> List[str]:
    seen: List[str] = []
    for r in data.get("infra_utama", []):
        if r.get("platform") == platform and r.get("produk") not in seen:
            seen.append(r.get("produk"))
    return seen


def _infra_rows(data: Dict[str, Any], platform: str, produk: str) -> Dict[str, Any]:
    return {
        r["sistem"]: r for r in data.get("infra_utama", [])
        if r.get("platform") == platform and r.get("produk") == produk
    }


def _storage_row(data: Dict[str, Any], platform: str, produk: str) -> Optional[Dict[str, Any]]:
    for r in data.get("storage", []):
        if r.get("platform") == platform and r.get("produk") == produk:
            return r
    return None


def _network_row(data: Dict[str, Any], platform: str, produk: str) -> Optional[Dict[str, Any]]:
    for r in data.get("network", []):
        if r.get("platform") == platform and r.get("produk") == produk:
            return r
    return None


# ---------------------------------------------------------------------------
# Laporan utama
# ---------------------------------------------------------------------------

def generate_pdf_bytes(DATA: Dict[str, Any], RESULT: Dict[str, Any], generated_by: str = "Guest") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#0f172a"))
    h1_style = ParagraphStyle("H1Custom", parent=styles["Heading1"], fontSize=15, spaceBefore=4, spaceAfter=8,
                              textColor=colors.HexColor("#0f172a"))
    h2_style = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=6,
                              textColor=colors.HexColor("#1e293b"))
    normal = styles["Normal"]
    caption_style = ParagraphStyle("Caption", parent=normal, fontSize=8, textColor=colors.HexColor("#64748b"))

    generated_at = datetime.now().strftime("%d %B %Y, %H:%M:%S")
    story: List[Any] = []

    # === COVER ===
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("Laporan Kalkulator Kapasitas Infrastruktur", title_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"<b>Tanggal Generate:</b> {generated_at}", normal))
    story.append(Paragraph(f"<b>Dibuat oleh:</b> {generated_by}", normal))
    story.append(Paragraph(
        "Laporan ini mencakup: Dashboard, Detail Infra/Storage/Network, "
        "Riwayat Bulanan, Forecast &amp; Scenario, Rekomendasi, dan Renewal.", normal
    ))
    story.append(PageBreak())

    platform_agg = RESULT.get("platform_agg", [])

    # === DASHBOARD ===
    story.append(Paragraph("1. Dashboard", h1_style))
    story.append(Paragraph(f"Tanggal Generate: {generated_at}", caption_style))
    if not platform_agg:
        story.append(Paragraph("Belum ada data platform.", normal))
    else:
        for a in platform_agg:
            story.append(Paragraph(f"Platform: {a['platform']}", h2_style))
            metric_line = (
                f"Sisa CPU {_fmt(a['sisa_cpu'],1)} vCore ({_fmt(a['util_cpu_pct'],1)}% terpakai) &nbsp;·&nbsp; "
                f"Sisa Memory {_fmt(a['sisa_mem'],1)} GB ({_fmt(a['util_mem_pct'],1)}%) &nbsp;·&nbsp; "
                f"Sisa Storage {_fmt(a['sisa_storage'],1)} GB ({_fmt(a['util_storage_pct'],1)}%) &nbsp;·&nbsp; "
                f"Sisa Network {_fmt(a['sisa_network'],1)} Mbps ({_fmt(a['util_network_pct'],1)}%)"
            )
            story.append(Paragraph(metric_line, normal))
            gauge_imgs = []
            for label, total, existing in [
                ("CPU", a["total_cpu"], a["existing_cpu"]),
                ("Memory", a["total_mem"], a["existing_mem"]),
                ("Storage", a["total_storage"], a["existing_storage"]),
                ("Network", a["total_network"], a["existing_network"]),
            ]:
                img = _fig_to_image(_gauge_fig(label, total, existing), 5.8, 4.2)
                gauge_imgs.append(img if img else Paragraph(f"{label}: {_fmt(calc.safe_div(total, existing)*100,1)}%", normal))
            gt = Table([gauge_imgs], colWidths=[6.2 * cm] * 4)
            gt.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(gt)
            story.append(Spacer(1, 0.3 * cm))

        story.append(Paragraph(
            "Catatan: Status per Produk (vs Kuota Produk) bisa HIJAU meski status Platform "
            "(vs Kapasitas Existing) MERAH — kuota produk adalah alokasi internal, sedangkan status "
            "platform mencerminkan total pemakaian gabungan terhadap kapasitas fisik existing.", caption_style,
        ))

        col_widths = [3.4 * cm] + [1.65 * cm] * 12 + [2.3 * cm]
        header = ["Platform", "CPU Total", "CPU Existing", "Util% CPU", "Mem Total", "Mem Existing",
                  "Util% Mem", "Storage Total", "Storage Existing", "Util% Storage",
                  "Network Total", "Network Existing", "Util% Net", "Status"]
        rows = []
        for a in platform_agg:
            worst_status = a["status_cpu"]
            for k in ("status_mem", "status_storage", "status_network"):
                if a[k] == "OVER CAPACITY":
                    worst_status = "OVER CAPACITY"
            rows.append([
                a["platform"],
                _fmt(a["total_cpu"], 1), _fmt(a["existing_cpu"], 1), _fmt(a["util_cpu_pct"], 1),
                _fmt(a["total_mem"], 1), _fmt(a["existing_mem"], 1), _fmt(a["util_mem_pct"], 1),
                _fmt(a["total_storage"], 1), _fmt(a["existing_storage"], 1), _fmt(a["util_storage_pct"], 1),
                _fmt(a["total_network"], 1), _fmt(a["existing_network"], 1), _fmt(a["util_network_pct"], 1),
                worst_status,
            ])
        story.append(_styled_table(header, rows, status_col=len(header) - 1, col_widths=col_widths, wrap_header=True))
        story.append(PageBreak())

    # === DETAIL INFRA / STORAGE / NETWORK ===
    story.append(Paragraph("2. Detail Infra, Storage & Network", h1_style))
    story.append(Paragraph(f"Tanggal Generate: {generated_at}", caption_style))

    utama = RESULT.get("utama", [])
    if utama:
        story.append(Paragraph("Detail Infra Utama per Produk", h2_style))
        header = ["Platform", "Produk", "Sistem", "Cluster", "Current TPS", "Future TPS",
                  "Final CPU", "Util% CPU", "Final Mem", "Util% Mem", "Status"]
        rows = []
        for r in utama:
            worst = r["status_cpu"] if r["util_cpu_pct"] >= r["util_mem_pct"] else r["status_mem"]
            rows.append([
                r.get("platform", ""), r.get("produk", ""), r.get("sistem", ""),
                r.get("cluster_server", "-"),
                _fmt(r.get("current_tps"), 0), _fmt(r.get("future_tps"), 0),
                _fmt(r.get("final_cpu"), 2), _fmt(r.get("util_cpu_pct"), 1),
                _fmt(r.get("final_mem"), 2), _fmt(r.get("util_mem_pct"), 1),
                worst,
            ])
        story.append(_styled_table(header, rows, status_col=len(header) - 1))

    storage_rows = RESULT.get("storage", [])
    if storage_rows:
        story.append(Paragraph("Detail Storage per Produk", h2_style))
        header = ["Platform", "Produk", "Final Storage (GB)", "Util% Storage", "Status"]
        rows = [[
            r.get("platform", ""), r.get("produk", ""),
            _fmt(r.get("final_storage_gb"), 1), _fmt(r.get("util_storage_pct"), 1),
            r.get("status_storage", ""),
        ] for r in storage_rows]
        story.append(_styled_table(header, rows, status_col=4))

    cascade_rows = RESULT.get("cascade", [])
    if cascade_rows:
        story.append(Paragraph("Detail Network — Cascade ke Member/Link", h2_style))
        header = ["Platform", "Produk", "Link", "Alokasi %", "Bandwidth Dibutuhkan (Mbps)",
                   "Sisa (Mbps)", "Util% Link", "Status"]
        rows = [[
            r.get("platform", ""), r.get("produk", ""), r.get("nama_link", ""),
            _fmt(r.get("pct_alokasi"), 1), _fmt(r.get("bandwidth_member_mbps"), 2),
            _fmt(r.get("sisa_mbps"), 2), _fmt(r.get("util_link_pct"), 1), r.get("status_link", ""),
        ] for r in cascade_rows]
        story.append(_styled_table(header, rows, status_col=7))

    story.append(PageBreak())

    # === RIWAYAT BULANAN ===
    story.append(Paragraph("3. Riwayat Bulanan (Grafik)", h1_style))
    story.append(Paragraph(f"Tanggal Generate: {generated_at}", caption_style))

    monthly = DATA.get("monthly_history", [])
    any_monthly = False
    for plat in _platform_names(DATA):
        for produk in _produk_for_platform(DATA, plat):
            entries = [m for m in monthly if m.get("platform") == plat and m.get("produk") == produk]
            if not entries:
                continue
            any_monthly = True
            infra_rows = _infra_rows(DATA, plat, produk)
            db_row, eng_row = infra_rows.get("DB", {}), infra_rows.get("Engine", {})
            network_row = _network_row(DATA, plat, produk)
            storage_row = _storage_row(DATA, plat, produk)
            platform_obj = next((p for p in DATA["platforms"] if p["platform"] == plat), {})
            existing_network = float(platform_obj.get("network", 0) or 0)
            kuota_cpu = float(db_row.get("kuota_cpu", 0) or 0)
            kuota_mem = float(db_row.get("kuota_mem", 0) or 0)
            kuota_storage = float(storage_row.get("kuota_storage", 0) or 0) if storage_row else 0.0

            computed = []
            for e in entries:
                res = calc.calc_monthly_utilization(
                    e["tps_aktual"], db_row, eng_row, kuota_cpu, kuota_mem,
                    network_row, existing_network, e.get("vol_trx_aktual"), storage_row, kuota_storage,
                )
                computed.append({"bulan": e["bulan"], **res})

            story.append(Paragraph(f"{produk} — {plat}", h2_style))

            bulan_list = [c["bulan"] for c in computed]
            fig_tps = go.Figure(go.Bar(x=bulan_list, y=[c["tps_aktual"] for c in computed],
                                        marker_color="#2563eb"))
            fig_tps.update_layout(title="TPS Aktual per Bulan", margin=dict(l=20, r=20, t=40, b=20),
                                   paper_bgcolor="white")
            fig_util = go.Figure()
            fig_util.add_trace(go.Scatter(x=bulan_list, y=[c["util_cpu_pct"] for c in computed],
                                           name="CPU %", mode="lines+markers"))
            fig_util.add_trace(go.Scatter(x=bulan_list, y=[c["util_mem_pct"] for c in computed],
                                           name="Memory %", mode="lines+markers"))
            if all("util_network_pct" in c for c in computed):
                fig_util.add_trace(go.Scatter(x=bulan_list, y=[c["util_network_pct"] for c in computed],
                                               name="Network %", mode="lines+markers"))
            if all("util_storage_pct" in c for c in computed):
                fig_util.add_trace(go.Scatter(x=bulan_list, y=[c["util_storage_pct"] for c in computed],
                                               name="Storage %", mode="lines+markers"))
            fig_util.update_layout(title="Utilisasi (%) per Bulan", margin=dict(l=20, r=20, t=40, b=20),
                                    paper_bgcolor="white", legend=dict(orientation="h", y=-0.2))

            img_tps = _fig_to_image(fig_tps, 12.5, 6.5)
            img_util = _fig_to_image(fig_util, 12.5, 6.5)
            if img_tps and img_util:
                row_table = Table([[img_tps, img_util]], colWidths=[13 * cm, 13 * cm])
                row_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
                story.append(row_table)
            else:
                header = ["Bulan", "TPS Aktual", "Util% CPU", "Util% Mem", "Status CPU", "Status Mem"]
                rows = [[c["bulan"], _fmt(c["tps_aktual"], 0), _fmt(c["util_cpu_pct"], 1),
                         _fmt(c["util_mem_pct"], 1), c["status_cpu"], c["status_mem"]] for c in computed]
                story.append(_styled_table(header, rows))
            story.append(Spacer(1, 0.4 * cm))

    if not any_monthly:
        story.append(Paragraph("Belum ada data riwayat bulanan.", normal))

    story.append(PageBreak())

    # === FORECAST & SCENARIO ===
    story.append(Paragraph("4. Forecast & Scenario", h1_style))
    story.append(Paragraph(
        f"Tanggal Generate: {generated_at} · Asumsi default: kenaikan transaksi 10% per periode, "
        f"12 periode, linear dari Future TPS produk.", caption_style,
    ))

    any_forecast = False
    for plat in _platform_names(DATA):
        for produk in _produk_for_platform(DATA, plat):
            infra_rows = _infra_rows(DATA, plat, produk)
            db_row, eng_row = infra_rows.get("DB", {}), infra_rows.get("Engine", {})
            if not db_row or not eng_row:
                continue
            any_forecast = True
            network_row = _network_row(DATA, plat, produk)
            storage_row = _storage_row(DATA, plat, produk)
            platform_obj = next((p for p in DATA["platforms"] if p["platform"] == plat), {})
            existing_network = float(platform_obj.get("network", 0) or 0)
            kuota_cpu = float(db_row.get("kuota_cpu", 0) or 0)
            kuota_mem = float(db_row.get("kuota_mem", 0) or 0)
            kuota_storage = float(storage_row.get("kuota_storage", 0) or 0) if storage_row else 0.0
            base_tps = float(db_row.get("future_tps", 0) or 0)

            scenario_rows = calc.calc_linear_scenario(
                base_tps, 10.0, 12, db_row, eng_row, kuota_cpu, kuota_mem,
                network_row, existing_network, storage_row, kuota_storage,
            )
            breach = calc.find_breach_period(scenario_rows)
            max_cap = calc.calc_max_tps_capacity(db_row, eng_row, network_row, existing_network)

            story.append(Paragraph(f"{produk} — {plat}", h2_style))
            cap_text = (
                f"Kapasitas Maksimum: {_fmt(max_cap['max_tps'],0) if max_cap['max_tps'] != float('inf') else '∞'} TPS "
                f"(bottleneck: {max_cap['bottleneck_resource']})"
            )
            story.append(Paragraph(cap_text, normal))
            if breach:
                story.append(Paragraph(
                    f"⚠ Pada periode ke-{breach['periode']} (TPS ≈ {_fmt(breach['tps'],0)}), resource "
                    f"{breach['resource']} diperkirakan melewati 100% kapasitas ({_fmt(breach['utilisasi_pct'],1)}%).",
                    normal,
                ))
            else:
                st_ok = ParagraphStyle("OkNote", parent=normal, textColor=colors.HexColor("#16a34a"))
                story.append(Paragraph("Sampai periode ke-12, seluruh resource masih dalam batas kapasitas.", st_ok))

            periods = [r["periode"] for r in scenario_rows]
            fig_fc = go.Figure()
            fig_fc.add_trace(go.Scatter(x=periods, y=[r["util_cpu_pct"] for r in scenario_rows],
                                         name="CPU %", mode="lines+markers"))
            fig_fc.add_trace(go.Scatter(x=periods, y=[r["util_mem_pct"] for r in scenario_rows],
                                         name="Memory %", mode="lines+markers"))
            if all("util_network_pct" in r for r in scenario_rows):
                fig_fc.add_trace(go.Scatter(x=periods, y=[r["util_network_pct"] for r in scenario_rows],
                                             name="Network %", mode="lines+markers"))
            if all("util_storage_pct" in r for r in scenario_rows):
                fig_fc.add_trace(go.Scatter(x=periods, y=[r["util_storage_pct"] for r in scenario_rows],
                                             name="Storage %", mode="lines+markers"))
            fig_fc.add_hline(y=100, line_dash="dash", line_color="#dc2626")
            fig_fc.add_hline(y=70, line_dash="dot", line_color="#f59e0b")
            fig_fc.update_layout(title="Proyeksi Utilisasi (%) per Periode", margin=dict(l=20, r=20, t=40, b=20),
                                  paper_bgcolor="white", legend=dict(orientation="h", y=-0.2))
            img_fc = _fig_to_image(fig_fc, 20, 7.5)
            if img_fc:
                story.append(img_fc)
            else:
                header = ["Periode", "TPS", "Util% CPU", "Util% Mem", "Status CPU", "Status Mem"]
                rows = [[r["periode"], _fmt(r["tps"], 0), _fmt(r["util_cpu_pct"], 1), _fmt(r["util_mem_pct"], 1),
                         r["status_cpu"], r["status_mem"]] for r in scenario_rows]
                story.append(_styled_table(header, rows))
            story.append(Spacer(1, 0.4 * cm))

    if not any_forecast:
        story.append(Paragraph("Belum ada produk dengan Infra Utama lengkap untuk diproyeksikan.", normal))

    story.append(PageBreak())

    # === REKOMENDASI ===
    story.append(Paragraph("5. Rekomendasi Kapasitas", h1_style))
    story.append(Paragraph(f"Tanggal Generate: {generated_at}", caption_style))

    rec_rows = []
    for a in platform_agg:
        for res_key, label in [("cpu", "CPU"), ("mem", "Memory"), ("storage", "Storage"), ("network", "Network")]:
            util = a[f"util_{res_key}_pct"]
            rec = calc.get_recommendation(util)
            if rec != "NORMAL":
                rec_rows.append([a["platform"], "-", label, _fmt(util, 1), rec])
    if rec_rows:
        header = ["Platform", "Produk", "Resource", "Utilisasi %", "Rekomendasi"]
        story.append(_styled_table(header, rec_rows, status_col=4))
    else:
        story.append(Paragraph("Semua resource dalam rentang utilisasi normal (50%–80%).", normal))

    # === RENEWAL ===
    story.append(Paragraph("6. Kalender Renewal / Due Date", h1_style))
    story.append(Paragraph(f"Tanggal Generate: {generated_at}", caption_style))

    renewals = DATA.get("renewals", [])
    if renewals:
        header = ["Platform", "Item/Komponen", "Vendor", "Jenis Event", "Tanggal", "Status", "Progress",
                   "PIC", "Harga", "Risiko", "Product Impacted", "Catatan"]
        rows = []
        for r in renewals:
            try:
                tgl = datetime.fromisoformat(r["tanggal"]).date()
                rs = calc.calc_renewal_status(tgl)
                status = rs["status"]
            except Exception:
                status = "-"
            rows.append([
                r.get("platform", ""), r.get("item", ""), r.get("vendor", ""),
                r.get("jenis_event", ""), r.get("tanggal", ""), status,
                r.get("status_progress", "On Going"),
                r.get("pic", ""), r.get("harga", ""), r.get("risiko", ""),
                r.get("product_impacted", ""), r.get("catatan", ""),
            ])
        story.append(_styled_table(header, rows, status_col=5, wrap_header=True))
    else:
        story.append(Paragraph("Belum ada data renewal.", normal))

    # === RINGKASAN A-B-C ===
    story.append(PageBreak())
    story.append(Paragraph("7. Ringkasan A-B-C — Kebutuhan Infra vs Kapasitas Existing", h1_style))
    story.append(Paragraph(f"Tanggal Generate: {generated_at}", caption_style))

    breakdowns = RESULT.get("platform_breakdown", [])
    if not breakdowns:
        story.append(Paragraph("Belum ada data platform.", normal))
    for bd in breakdowns:
        story.append(Paragraph(f"Platform: {bd['platform']}", h2_style))

        story.append(Paragraph("A. Total FINAL Required (per kategori)", normal))
        header_a = ["Kategori", "CPU (vCPU)", "Memory (GB)", "Storage (GB)", "Network (Mbps)"]
        rows_a = [
            [c["kategori"], _fmt(c["cpu"], 1), _fmt(c["mem"], 1), _fmt(c["storage"], 1), _fmt(c["network"], 1)]
            for c in bd["categories"] + [bd["total_row"]]
        ]
        story.append(_styled_table(header_a, rows_a))
        story.append(Spacer(1, 0.2 * cm))

        story.append(Paragraph("B. Kapasitas Existing / Tersedia (isi manual)", normal))
        ex = bd["existing"]
        header_b = ["CPU (vCPU)", "Memory (GB)", "Storage (GB)", "Network (Mbps)"]
        rows_b = [[_fmt(ex["cpu"], 1), _fmt(ex["mem"], 1), _fmt(ex["storage"], 1), _fmt(ex["network"], 1)]]
        story.append(_styled_table(header_b, rows_b))
        story.append(Spacer(1, 0.2 * cm))

        story.append(Paragraph("C. Analisis Gap & Utilization", normal))
        g = bd["gap"]
        header_c = ["Resource", "Total Required", "Existing", "Sisa", "Utilization %", "Status"]
        rows_c = [
            ["CPU", _fmt(g["total_cpu"], 1), _fmt(g["existing_cpu"], 1), _fmt(g["sisa_cpu"], 1),
             _fmt(g["util_cpu_pct"], 1), g["status_cpu"]],
            ["Memory", _fmt(g["total_mem"], 1), _fmt(g["existing_mem"], 1), _fmt(g["sisa_mem"], 1),
             _fmt(g["util_mem_pct"], 1), g["status_mem"]],
            ["Storage", _fmt(g["total_storage"], 1), _fmt(g["existing_storage"], 1), _fmt(g["sisa_storage"], 1),
             _fmt(g["util_storage_pct"], 1), g["status_storage"]],
            ["Network", _fmt(g["total_network"], 1), _fmt(g["existing_network"], 1), _fmt(g["sisa_network"], 1),
             _fmt(g["util_network_pct"], 1), g["status_network"]],
        ]
        story.append(_styled_table(header_c, rows_c, status_col=5))

        bar_fig = go.Figure()
        bar_fig.add_trace(go.Bar(name="Total Required",
                                  x=["CPU", "Memory", "Storage", "Network"],
                                  y=[g["total_cpu"], g["total_mem"], g["total_storage"], g["total_network"]]))
        bar_fig.add_trace(go.Bar(name="Existing Capacity",
                                  x=["CPU", "Memory", "Storage", "Network"],
                                  y=[g["existing_cpu"], g["existing_mem"], g["existing_storage"], g["existing_network"]]))
        bar_fig.update_layout(barmode="group", width=700, height=380, margin=dict(t=30, b=10, l=10, r=10),
                               legend=dict(orientation="h", yanchor="bottom", y=1.02))
        bar_img = _fig_to_image(bar_fig, 16, 8.5)
        if bar_img:
            story.append(bar_img)
        story.append(Spacer(1, 0.4 * cm))

    doc.build(story)
    return buffer.getvalue()
