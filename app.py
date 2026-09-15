"""
app.py
Kalkulator Kapasitas Infrastruktur — UI Streamlit.
Semua rumus/hitung ada di calculator.py. File ini hanya UI & state management.
"""

import io
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculator as calc
import sample_data

# ---------------------------------------------------------------------------
# PAGE CONFIG & CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Kalkulator Kapasitas Infrastruktur",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    .block-container { padding-top: 2rem; padding-bottom: 3rem; }

    .metric-card {
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        margin-bottom: 0.5rem;
    }
    .metric-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.25rem;
    }
    .metric-value {
        font-size: 1.9rem;
        font-weight: 700;
        color: #111827;
        line-height: 1.1;
    }
    .metric-sub {
        font-size: 0.85rem;
        color: #6b7280;
        margin-top: 0.15rem;
    }
    .badge {
        display: inline-block;
        padding: 0.15rem 0.65rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        color: white;
        letter-spacing: 0.02em;
    }
    .note-box {
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        font-size: 0.88rem;
        color: #075985;
        margin: 0.8rem 0 1.2rem 0;
    }
    .warn-box {
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-radius: 10px;
        padding: 0.7rem 1rem;
        font-size: 0.85rem;
        color: #92400e;
        margin: 0.5rem 0;
    }
    section[data-testid="stSidebar"] { background: #f9fafb; }
    h1, h2, h3 { color: #111827; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# STATE INIT
# ---------------------------------------------------------------------------

if "data" not in st.session_state:
    st.session_state["data"] = sample_data.get_sample_state()

DATA = st.session_state["data"]


def fmt(n, dec=2):
    try:
        return f"{n:,.{dec}f}"
    except (TypeError, ValueError):
        return str(n)


def badge(status: str) -> str:
    color = calc.STATUS_COLOR.get(status, "#6b7280")
    return f'<span class="badge" style="background:{color}">{status}</span>'


def gauge_chart(title: str, used: float, total: float, unit: str) -> go.Figure:
    pct = calc.safe_div(used, total) * 100
    status = calc.status_global(pct)
    color = calc.STATUS_COLOR.get(status, "#6b7280")
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            number={"suffix": "%", "font": {"size": 30}},
            title={"text": title, "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 120], "tickwidth": 1},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 80], "color": "#dcfce7"},
                    {"range": [80, 100], "color": "#fef3c7"},
                    {"range": [100, 120], "color": "#fee2e2"},
                ],
                "threshold": {
                    "line": {"color": "#111827", "width": 3},
                    "thickness": 0.8,
                    "value": 100,
                },
            },
        )
    )
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def get_platform_names():
    return [p["platform"] for p in DATA["platforms"]] or ["(belum ada platform)"]


# ---------------------------------------------------------------------------
# COMPUTE ENGINE — jalankan semua rumus dari calculator.py
# ---------------------------------------------------------------------------

def compute_all():
    utama_calc = calc.calc_infra_utama(DATA["infra_utama"])
    storage_calc = calc.calc_storage(DATA["storage"])
    network_calc = calc.calc_network(DATA["network"])
    pendukung_calc = calc.calc_pendukung(DATA["pendukung"])

    # cascade network -> member, per baris network (per produk)
    cascade_calc = []
    for net_row in network_calc:
        members = [
            m for m in DATA["network_members"]
            if m.get("platform") == net_row.get("platform") and m.get("produk") == net_row.get("produk")
        ]
        rows = calc.calc_cascade(net_row["final_network_mbps"], members)
        for r in rows:
            r["produk"] = net_row.get("produk")
            r["platform"] = net_row.get("platform")
        cascade_calc.extend(rows)

    # aggregate per platform (Layer 1)
    platform_agg = []
    for p in DATA["platforms"]:
        pname = p["platform"]
        u_rows = [r for r in utama_calc if r.get("platform") == pname]
        s_rows = [r for r in storage_calc if r.get("platform") == pname]
        pd_rows = [r for r in pendukung_calc if r.get("platform") == pname]
        net_rows = [r for r in network_calc if r.get("platform") == pname]
        total_net = sum(r["final_network_mbps"] for r in net_rows)

        agg = calc.aggregate_platform(
            pname,
            {"cpu": p["cpu"], "memory": p["memory"], "storage": p["storage"], "network": p["network"]},
            u_rows,
            pd_rows,
            s_rows,
            total_net,
        )
        platform_agg.append(agg)

    return {
        "utama": utama_calc,
        "storage": storage_calc,
        "network": network_calc,
        "pendukung": pendukung_calc,
        "cascade": cascade_calc,
        "platform_agg": platform_agg,
    }


RESULT = compute_all()


# ---------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------------------------------------------

st.sidebar.markdown("## 📊 Kalkulator Kapasitas\nInfrastruktur")
PAGE = st.sidebar.radio(
    "Navigasi",
    [
        "1. Dashboard",
        "2. Input Platform & Kapasitas",
        "3. Input Infra Utama (TPS)",
        "4. Input Storage",
        "5. Input Network",
        "6. Input Pendukung",
        "7. Gap Analysis & Export",
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Semua nilai dihitung otomatis dari rumus baku sizing infrastruktur berbasis TPS."
)


# ---------------------------------------------------------------------------
# PAGE 1 — DASHBOARD
# ---------------------------------------------------------------------------

if PAGE == "1. Dashboard":
    st.title("Dashboard Kapasitas Infrastruktur")

    if not DATA["platforms"]:
        st.info("Belum ada platform. Silakan tambahkan di menu 'Input Platform & Kapasitas'.")
    else:
        platform_pick = st.selectbox("Pilih Platform", get_platform_names())
        agg = next((a for a in RESULT["platform_agg"] if a["platform"] == platform_pick), None)

        if agg:
            cols = st.columns(4)
            metrics = [
                ("CPU", agg["sisa_cpu"], agg["existing_cpu"], agg["util_cpu_pct"], agg["status_cpu"], "vCore"),
                ("Memory", agg["sisa_mem"], agg["existing_mem"], agg["util_mem_pct"], agg["status_mem"], "GB"),
                ("Storage", agg["sisa_storage"], agg["existing_storage"], agg["util_storage_pct"], agg["status_storage"], "GB"),
                ("Network", agg["sisa_network"], agg["existing_network"], agg["util_network_pct"], agg["status_network"], "Mbps"),
            ]
            for col, (label, sisa, total, util, status, unit) in zip(cols, metrics):
                with col:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-title">Sisa {label}</div>
                            <div class="metric-value">{fmt(sisa)} {unit}</div>
                            <div class="metric-sub">dari {fmt(total)} {unit} existing</div>
                            <div style="margin-top:0.5rem">{badge(status)}
                                <span style="color:#6b7280;font-size:0.8rem"> · {fmt(util)}% terpakai</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.markdown("### Gauge Utilisasi")
            g1, g2, g3, g4 = st.columns(4)
            g1.plotly_chart(gauge_chart("CPU", agg["total_cpu"], agg["existing_cpu"], "vCore"), width='stretch')
            g2.plotly_chart(gauge_chart("Memory", agg["total_mem"], agg["existing_mem"], "GB"), width='stretch')
            g3.plotly_chart(gauge_chart("Storage", agg["total_storage"], agg["existing_storage"], "GB"), width='stretch')
            g4.plotly_chart(gauge_chart("Network", agg["total_network"], agg["existing_network"], "Mbps"), width='stretch')

        st.markdown(
            """
            <div class="note-box">
            💡 <b>Catatan Edukatif:</b> Status Layer 2 (per Produk, vs Kuota Produk) bisa berstatus
            <b>HIJAU</b> meskipun Layer 1 (per Platform, vs Kapasitas Existing) berstatus <b>MERAH</b>.
            Ini terjadi karena kuota per produk adalah alokasi internal, sedangkan status platform
            mencerminkan total pemakaian gabungan seluruh produk terhadap kapasitas fisik existing.
            Selalu periksa kedua layer sebelum mengambil keputusan sizing.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Layer 1 — Ringkasan per Platform")
        df_l1 = pd.DataFrame(RESULT["platform_agg"])
        if not df_l1.empty:
            show_cols = [
                "platform", "existing_cpu", "total_cpu", "util_cpu_pct", "status_cpu",
                "existing_mem", "total_mem", "util_mem_pct", "status_mem",
                "existing_storage", "total_storage", "util_storage_pct", "status_storage",
                "existing_network", "total_network", "util_network_pct", "status_network",
            ]
            st.dataframe(df_l1[show_cols].round(2), width='stretch', hide_index=True)

        st.markdown("### Layer 2 — Ringkasan per Produk (Infra Utama)")
        df_l2 = pd.DataFrame(RESULT["utama"])
        if not df_l2.empty:
            show_cols2 = [
                "platform", "produk", "sistem", "current_tps", "future_tps",
                "final_cpu", "util_cpu_pct", "status_cpu",
                "final_mem", "util_mem_pct", "status_mem",
            ]
            st.dataframe(df_l2[show_cols2].round(2), width='stretch', hide_index=True)
        else:
            st.info("Belum ada data Infra Utama.")


# ---------------------------------------------------------------------------
# PAGE 2 — INPUT PLATFORM & KAPASITAS
# ---------------------------------------------------------------------------

elif PAGE == "2. Input Platform & Kapasitas":
    st.title("Input Platform & Kapasitas Existing")
    st.caption(
        "Masukkan kapasitas existing platform secara manual — dari snapshot saat ini "
        "atau dari rata-rata pemakaian 3 bulan terakhir."
    )

    sumber_mode = st.radio(
        "Sumber Data Kapasitas",
        ["Pakai snapshot (current)", "Pakai rata-rata 3 bulan"],
        horizontal=True,
    )

    with st.form("form_platform", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nama = st.text_input("Nama Platform")
            cpu = st.number_input("CPU Existing (vCore)", min_value=0.0, step=1.0)
            memory = st.number_input("Memory Existing (GB)", min_value=0.0, step=1.0)
        with c2:
            storage = st.number_input("Storage Existing (GB)", min_value=0.0, step=1.0)
            network = st.number_input("Network Existing (Mbps)", min_value=0.0, step=1.0)
        submitted = st.form_submit_button("Tambah Platform", width='stretch')

        if submitted:
            if not nama.strip():
                st.error("Nama platform wajib diisi.")
            else:
                DATA["platforms"].append({
                    "platform": nama.strip(),
                    "cpu": cpu,
                    "memory": memory,
                    "storage": storage,
                    "network": network,
                    "sumber": sumber_mode,
                })
                st.success(f"Platform '{nama}' ditambahkan.")
                st.rerun()

    st.markdown("### Daftar Platform")
    if DATA["platforms"]:
        df = pd.DataFrame(DATA["platforms"])
        edited = st.data_editor(
            df,
            width='stretch',
            num_rows="dynamic",
            hide_index=True,
            key="editor_platforms",
        )
        DATA["platforms"] = edited.to_dict("records")
    else:
        st.info("Belum ada platform.")


# ---------------------------------------------------------------------------
# PAGE 3 — INPUT INFRA UTAMA (TPS)
# ---------------------------------------------------------------------------

elif PAGE == "3. Input Infra Utama (TPS)":
    st.title("Input Infra Utama (Berbasis TPS)")
    st.caption("Per produk, pecah 2 baris: Sistem = DB dan Engine.")

    if DATA["infra_utama"]:
        df = pd.DataFrame(DATA["infra_utama"])
    else:
        df = pd.DataFrame(columns=[
            "platform", "produk", "sistem", "kategori", "current_tps", "future_tps",
            "rasio_cpu", "rasio_mem", "rasio_storage", "buffer_pct", "ha_multiplier",
            "kuota_cpu", "kuota_mem",
        ])

    edited = st.data_editor(
        df,
        width='stretch',
        num_rows="dynamic",
        hide_index=True,
        key="editor_utama",
        column_config={
            "sistem": st.column_config.SelectboxColumn(options=["DB", "Engine"]),
            "kategori": st.column_config.SelectboxColumn(options=["Utama", "Pendukung"]),
            "current_tps": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "future_tps": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "buffer_pct": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f"),
            "ha_multiplier": st.column_config.NumberColumn(min_value=1.0, max_value=5.0, format="%.1f"),
        },
    )
    DATA["infra_utama"] = edited.to_dict("records")

    # validasi ringan
    for r in DATA["infra_utama"]:
        if float(r.get("current_tps", 0) or 0) < 0 or float(r.get("future_tps", 0) or 0) < 0:
            st.markdown('<div class="warn-box">⚠️ TPS tidak boleh negatif.</div>', unsafe_allow_html=True)
            break

    st.markdown("### Hasil Perhitungan")
    result_rows = calc.calc_infra_utama(DATA["infra_utama"])
    if result_rows:
        df_res = pd.DataFrame(result_rows)
        cols = [
            "platform", "produk", "sistem", "req_cpu_future", "final_cpu", "util_cpu_pct", "status_cpu",
            "req_mem_future", "final_mem", "util_mem_pct", "status_mem",
        ]
        st.dataframe(df_res[cols].round(2), width='stretch', hide_index=True)


# ---------------------------------------------------------------------------
# PAGE 4 — INPUT STORAGE
# ---------------------------------------------------------------------------

elif PAGE == "4. Input Storage":
    st.title("Input Storage")
    st.caption("Perhitungan storage berbasis volume transaksi harian dan retensi.")

    if DATA["storage"]:
        df = pd.DataFrame(DATA["storage"])
    else:
        df = pd.DataFrame(columns=[
            "platform", "produk", "vol_trx_current", "vol_trx_future", "ukuran_kb",
            "retensi_hari", "housekeeping_pct", "buffer_pct", "replication_multiplier",
            "kuota_storage",
        ])

    edited = st.data_editor(
        df,
        width='stretch',
        num_rows="dynamic",
        hide_index=True,
        key="editor_storage",
        column_config={
            "buffer_pct": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f"),
            "housekeeping_pct": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f"),
            "replication_multiplier": st.column_config.NumberColumn(min_value=1.0, max_value=5.0, format="%.1f"),
        },
    )
    DATA["storage"] = edited.to_dict("records")

    st.markdown("### Hasil Perhitungan")
    result_rows = calc.calc_storage(DATA["storage"])
    if result_rows:
        df_res = pd.DataFrame(result_rows)
        cols = [
            "platform", "produk", "storage_current_gb", "storage_future_gb",
            "final_storage_gb", "util_storage_pct", "status_storage",
        ]
        st.dataframe(df_res[cols].round(2), width='stretch', hide_index=True)


# ---------------------------------------------------------------------------
# PAGE 5 — INPUT NETWORK
# ---------------------------------------------------------------------------

elif PAGE == "5. Input Network":
    st.title("Input Network")

    st.markdown("#### Bagian 1 — TPS → Bandwidth (per Produk)")
    if DATA["network"]:
        df = pd.DataFrame(DATA["network"])
    else:
        df = pd.DataFrame(columns=[
            "platform", "produk", "current_tps", "future_tps", "kb_req", "kb_resp",
            "overhead_pct", "buffer_pct", "ha_multiplier",
        ])

    edited = st.data_editor(
        df,
        width='stretch',
        num_rows="dynamic",
        hide_index=True,
        key="editor_network",
        column_config={
            "overhead_pct": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f"),
            "buffer_pct": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f"),
            "ha_multiplier": st.column_config.NumberColumn(min_value=1.0, max_value=5.0, format="%.1f"),
        },
    )
    DATA["network"] = edited.to_dict("records")

    result_rows = calc.calc_network(DATA["network"])
    if result_rows:
        df_res = pd.DataFrame(result_rows)
        cols = ["platform", "produk", "req_network_future_mbps", "final_network_mbps"]
        st.dataframe(df_res[cols].round(2), width='stretch', hide_index=True)

    st.markdown("---")
    st.markdown("#### Bagian 2 — Cascade ke Member / Link")

    if DATA["network_members"]:
        df_m = pd.DataFrame(DATA["network_members"])
    else:
        df_m = pd.DataFrame(columns=["platform", "produk", "nama_link", "pct_alokasi", "existing_bandwidth"])

    edited_m = st.data_editor(
        df_m,
        width='stretch',
        num_rows="dynamic",
        hide_index=True,
        key="editor_network_members",
        column_config={
            "pct_alokasi": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f"),
        },
    )
    DATA["network_members"] = edited_m.to_dict("records")

    # validasi total alokasi per produk idealnya 100%
    if DATA["network_members"]:
        df_check = pd.DataFrame(DATA["network_members"])
        totals = df_check.groupby(["platform", "produk"])["pct_alokasi"].sum()
        for (plat, prod), total_pct in totals.items():
            if abs(total_pct - 100) > 0.01:
                st.markdown(
                    f'<div class="warn-box">⚠️ Total alokasi link untuk <b>{prod}</b> ({plat}) = '
                    f'{total_pct:.1f}%, idealnya 100%.</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("### Hasil Cascade")
    cascade_all = []
    for net_row in result_rows:
        members = [
            m for m in DATA["network_members"]
            if m.get("platform") == net_row.get("platform") and m.get("produk") == net_row.get("produk")
        ]
        rows = calc.calc_cascade(net_row["final_network_mbps"], members)
        for r in rows:
            r["produk"] = net_row.get("produk")
            r["platform"] = net_row.get("platform")
        cascade_all.extend(rows)

    if cascade_all:
        df_c = pd.DataFrame(cascade_all)
        cols_c = [
            "platform", "produk", "nama_link", "pct_alokasi", "existing_bandwidth",
            "bandwidth_member_mbps", "sisa_mbps", "util_link_pct", "status_link",
        ]
        st.dataframe(df_c[cols_c].round(2), width='stretch', hide_index=True)


# ---------------------------------------------------------------------------
# PAGE 6 — INPUT PENDUKUNG
# ---------------------------------------------------------------------------

elif PAGE == "6. Input Pendukung":
    st.title("Input Infra Pendukung (Non-TPS)")
    st.caption("Komponen seperti Load Balancer, Monitoring, Backup, Firewall.")

    if DATA["pendukung"]:
        df = pd.DataFrame(DATA["pendukung"])
    else:
        df = pd.DataFrame(columns=[
            "platform", "nama", "fungsi", "cpu", "memory", "storage", "buffer_pct", "ha_multiplier",
        ])

    edited = st.data_editor(
        df,
        width='stretch',
        num_rows="dynamic",
        hide_index=True,
        key="editor_pendukung",
        column_config={
            "buffer_pct": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f"),
            "ha_multiplier": st.column_config.NumberColumn(min_value=1.0, max_value=5.0, format="%.1f"),
        },
    )
    DATA["pendukung"] = edited.to_dict("records")

    st.markdown("### Hasil Perhitungan")
    result_rows = calc.calc_pendukung(DATA["pendukung"])
    if result_rows:
        df_res = pd.DataFrame(result_rows)
        cols = ["platform", "nama", "fungsi", "final_cpu", "final_mem", "final_storage"]
        st.dataframe(df_res[cols].round(2), width='stretch', hide_index=True)


# ---------------------------------------------------------------------------
# PAGE 7 — GAP ANALYSIS & EXPORT
# ---------------------------------------------------------------------------

elif PAGE == "7. Gap Analysis & Export":
    st.title("Gap Analysis & Export")

    df_agg = pd.DataFrame(RESULT["platform_agg"])
    if df_agg.empty:
        st.info("Belum ada data untuk dianalisis.")
    else:
        st.markdown("### Ringkasan Total vs Kapasitas Existing")
        st.dataframe(
            df_agg[[
                "platform", "total_cpu", "existing_cpu", "status_cpu",
                "total_mem", "existing_mem", "status_mem",
                "total_storage", "existing_storage", "status_storage",
                "total_network", "existing_network", "status_network",
            ]].round(2),
            width='stretch',
            hide_index=True,
        )

        over_rows = []
        for _, row in df_agg.iterrows():
            for res, label in [("cpu", "CPU"), ("mem", "Memory"), ("storage", "Storage"), ("network", "Network")]:
                if row[f"status_{res}"] == "OVER CAPACITY":
                    over_rows.append({
                        "Platform": row["platform"],
                        "Resource": label,
                        "Total Kebutuhan": row[f"total_{res}"],
                        "Existing": row[f"existing_{res}"],
                        "Utilisasi %": row[f"util_{res}_pct"],
                    })

        if over_rows:
            st.markdown("### 🔴 Resource OVER CAPACITY")
            st.dataframe(pd.DataFrame(over_rows).round(2), width='stretch', hide_index=True)
        else:
            st.success("Tidak ada resource yang OVER CAPACITY saat ini.")

    st.markdown("---")
    st.markdown("### Export & Reset")

    c1, c2, c3 = st.columns(3)

    with c1:
        json_bytes = json.dumps(DATA, indent=2, ensure_ascii=False).encode("utf-8")
        st.download_button(
            "⬇️ Download JSON",
            data=json_bytes,
            file_name="kapasitas_infrastruktur.json",
            mime="application/json",
            width='stretch',
        )

    with c2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame(DATA["platforms"]).to_excel(writer, sheet_name="Platforms", index=False)
            pd.DataFrame(RESULT["utama"]).to_excel(writer, sheet_name="Infra Utama", index=False)
            pd.DataFrame(RESULT["storage"]).to_excel(writer, sheet_name="Storage", index=False)
            pd.DataFrame(RESULT["network"]).to_excel(writer, sheet_name="Network", index=False)
            pd.DataFrame(RESULT["cascade"]).to_excel(writer, sheet_name="Network Cascade", index=False)
            pd.DataFrame(RESULT["pendukung"]).to_excel(writer, sheet_name="Pendukung", index=False)
            pd.DataFrame(RESULT["platform_agg"]).to_excel(writer, sheet_name="Gap Analysis", index=False)
        st.download_button(
            "⬇️ Download Excel",
            data=buffer.getvalue(),
            file_name="kapasitas_infrastruktur.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width='stretch',
        )

    with c3:
        if st.button("🔄 Reset ke Data Contoh", width='stretch'):
            st.session_state["data"] = sample_data.get_sample_state()
            st.rerun()

    st.markdown("---")
    st.markdown("### Upload / Load JSON")
    uploaded = st.file_uploader("Load state dari file JSON", type=["json"])
    if uploaded is not None:
        try:
            loaded = json.load(uploaded)
            st.session_state["data"] = loaded
            st.success("Data berhasil dimuat.")
            st.rerun()
        except Exception as e:
            st.error(f"Gagal memuat file: {e}")
