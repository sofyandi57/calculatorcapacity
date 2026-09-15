"""
pdf_export.py
Bangun laporan PDF ringkas dari state aplikasi (DATA) & hasil hitung (RESULT).
Tidak ada logika UI di sini — hanya penyusunan dokumen PDF (reportlab).
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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


def generate_pdf_bytes(DATA: Dict[str, Any], RESULT: Dict[str, Any], generated_by: str = "Guest") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#0f172a"))
    h2_style = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6,
                              textColor=colors.HexColor("#0f172a"))
    normal = styles["Normal"]

    story: List[Any] = []
    story.append(Paragraph("Laporan Kalkulator Kapasitas Infrastruktur", title_style))
    story.append(Paragraph(
        f"Dibuat: {datetime.now().strftime('%d %B %Y %H:%M')} · Oleh: {generated_by}", normal
    ))
    story.append(Spacer(1, 0.5 * cm))

    # --- Ringkasan Platform ---
    platform_agg = RESULT.get("platform_agg", [])
    if platform_agg:
        story.append(Paragraph("Ringkasan per Platform (vs Kapasitas Existing)", h2_style))
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
        col_widths = [3.4 * cm] + [1.65 * cm] * 12 + [2.3 * cm]
        story.append(_styled_table(header, rows, status_col=len(header) - 1, col_widths=col_widths, wrap_header=True))

    # --- Detail Infra Utama per Produk ---
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

    # --- Storage ---
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

    # --- Network cascade ---
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

    # --- Rekomendasi ---
    import calculator as calc
    rec_rows = []
    for a in platform_agg:
        for res_key, label in [("cpu", "CPU"), ("mem", "Memory"), ("storage", "Storage"), ("network", "Network")]:
            util = a[f"util_{res_key}_pct"]
            rec = calc.get_recommendation(util)
            if rec != "NORMAL":
                rec_rows.append([a["platform"], "-", label, _fmt(util, 1), rec])
    if rec_rows:
        story.append(Paragraph("Rekomendasi Kapasitas", h2_style))
        header = ["Platform", "Produk", "Resource", "Utilisasi %", "Rekomendasi"]
        story.append(_styled_table(header, rec_rows, status_col=4))

    # --- Renewal ---
    renewals = DATA.get("renewals", [])
    if renewals:
        story.append(Paragraph("Kalender Renewal / Due Date", h2_style))
        header = ["Platform", "Item/Komponen", "Vendor", "Jenis Event", "Tanggal", "Status", "Catatan"]
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
                r.get("jenis_event", ""), r.get("tanggal", ""), status, r.get("catatan", ""),
            ])
        story.append(_styled_table(header, rows, status_col=5))

    if not platform_agg:
        story.append(Paragraph("Belum ada data untuk dilaporkan.", normal))

    doc.build(story)
    return buffer.getvalue()
