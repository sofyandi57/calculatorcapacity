"""
app.py
Kalkulator Kapasitas Infrastruktur — UI Streamlit.
Alur terpandu: Produk -> Infra (DB/Engine, CPU, Memori) & Storage -> Network -> Dashboard & Export.
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
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    #MainMenu, footer, header { visibility: hidden; }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }

    /* App header */
    .app-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.25rem;
    }
    .app-header .logo {
        font-size: 1.9rem;
    }
    .app-header h1 {
        font-size: 1.5rem;
        font-weight: 800;
        color: #0f172a;
        margin: 0;
    }
    .app-sub {
        color: #64748b;
        font-size: 0.92rem;
        margin: 0 0 1.4rem 0;
    }

    /* Tabs styled as horizontal steps */
    div[data-testid="stTabs"] button[role="tab"] {
        font-weight: 600;
        font-size: 0.95rem;
        padding: 0.6rem 1.1rem;
        color: #64748b;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: #0f172a;
        border-bottom: 3px solid #2563eb;
    }

    /* Cards */
    .card {
        background: #ffffff;
        border: 1px solid #e6e9ef;
        border-radius: 16px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(15,23,42,0.04);
    }
    .card-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.6rem;
    }
    .section-label {
        font-size: 0.78rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin: 1.4rem 0 0.5rem 0;
    }

    /* Metric cards on dashboard */
    .metric-card {
        border-radius: 16px;
        padding: 1.1rem 1.3rem;
        background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
        border: 1px solid #e6e9ef;
        box-shadow: 0 1px 3px rgba(15,23,42,0.05);
        margin-bottom: 0.5rem;
        height: 100%;
    }
    .metric-title {
        font-size: 0.78rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.35rem;
    }
    .metric-value {
        font-size: 1.7rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.15;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 0.1rem;
    }

    .badge {
        display: inline-block;
        padding: 0.18rem 0.7rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 800;
        color: white;
        letter-spacing: 0.03em;
    }

    .note-box {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 12px;
        padding: 0.85rem 1.1rem;
        font-size: 0.86rem;
        color: #1e40af;
        margin: 0.6rem 0 1.2rem 0;
    }
    .warn-box {
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-radius: 12px;
        padding: 0.65rem 1rem;
        font-size: 0.84rem;
        color: #92400e;
        margin: 0.4rem 0;
    }
    .empty-box {
        text-align: center;
        padding: 2.2rem 1rem;
        color: #94a3b8;
        border: 1.5px dashed #e2e8f0;
        border-radius: 14px;
        font-size: 0.9rem;
    }

    .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-bottom: 0.6rem;
    }
    .pill {
        background: #f1f5f9;
        color: #334155;
        border-radius: 999px;
        padding: 0.3rem 0.8rem;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .pill b { color: #0f172a; }

    h1, h2, h3 { color: #0f172a; }
    div[data-testid="stMetric"] { background: transparent; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# STATE INIT
# ---------------------------------------------------------------------------

if "data" not in st.session_state:
    st.session_state["data"] = sample_data.get_sample_state()

DATA = st.session_state["data"]
DATA.setdefault("pendukung", [])
DATA.setdefault("network_members", [])


def fmt(n, dec=2):
    try:
        return f"{n:,.{dec}f}"
    except (TypeError, ValueError):
        return str(n)


def badge(status: str) -> str:
    color = calc.STATUS_COLOR.get(status, "#6b7280")
    return f'<span class="badge" style="background:{color}">{status}</span>'


def gauge_chart(title: str, used: float, total: float) -> go.Figure:
    pct = calc.safe_div(used, total) * 100
    status = calc.status_global(pct)
    color = calc.STATUS_COLOR.get(status, "#6b7280")
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            number={"suffix": "%", "font": {"size": 26}},
            title={"text": title, "font": {"size": 13, "color": "#64748b"}},
            gauge={
                "axis": {"range": [0, 120], "tickwidth": 1, "tickcolor": "#cbd5e1"},
                "bar": {"color": color, "thickness": 0.75},
                "bgcolor": "white",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 80], "color": "#dcfce7"},
                    {"range": [80, 100], "color": "#fef3c7"},
                    {"range": [100, 120], "color": "#fee2e2"},
                ],
                "threshold": {"line": {"color": "#0f172a", "width": 2}, "thickness": 0.8, "value": 100},
            },
        )
    )
    fig.update_layout(height=190, margin=dict(l=15, r=15, t=35, b=5), paper_bgcolor="rgba(0,0,0,0)")
    return fig


# ---------------------------------------------------------------------------
# DATA HELPERS — upsert kecil untuk model per-produk
# ---------------------------------------------------------------------------

def platform_names():
    return [p["platform"] for p in DATA["platforms"]]


def produk_for_platform(platform):
    seen = []
    for r in DATA["infra_utama"]:
        if r.get("platform") == platform and r.get("produk") not in seen:
            seen.append(r.get("produk"))
    return seen


def upsert_platform(nama, cpu, memory, storage, network, sumber):
    for p in DATA["platforms"]:
        if p["platform"] == nama:
            p.update({"cpu": cpu, "memory": memory, "storage": storage, "network": network, "sumber": sumber})
            return
    DATA["platforms"].append({
        "platform": nama, "cpu": cpu, "memory": memory, "storage": storage,
        "network": network, "sumber": sumber,
    })


def delete_platform(nama):
    DATA["platforms"] = [p for p in DATA["platforms"] if p["platform"] != nama]
    for key in ("infra_utama", "storage", "network", "network_members", "pendukung"):
        DATA[key] = [r for r in DATA[key] if r.get("platform") != nama]


def upsert_produk_tps(platform, produk, current_tps, future_tps):
    """Pastikan 2 baris infra_utama (DB & Engine) ada untuk produk ini, update TPS-nya."""
    existing = {r["sistem"]: r for r in DATA["infra_utama"] if r.get("platform") == platform and r.get("produk") == produk}
    for sistem in ("DB", "Engine"):
        if sistem in existing:
            existing[sistem]["current_tps"] = current_tps
            existing[sistem]["future_tps"] = future_tps
        else:
            DATA["infra_utama"].append({
                "platform": platform, "produk": produk, "sistem": sistem, "kategori": "Utama",
                "current_tps": current_tps, "future_tps": future_tps,
                "rasio_cpu": 0.0, "rasio_mem": 0.0, "rasio_storage": 0.0,
                "buffer_pct": 20.0, "ha_multiplier": 2.0, "kuota_cpu": 0.0, "kuota_mem": 0.0,
            })


def delete_produk(platform, produk):
    for key in ("infra_utama", "storage", "network", "network_members"):
        DATA[key] = [r for r in DATA[key] if not (r.get("platform") == platform and r.get("produk") == produk)]


def get_infra_rows(platform, produk):
    return {r["sistem"]: r for r in DATA["infra_utama"] if r.get("platform") == platform and r.get("produk") == produk}


def get_storage_row(platform, produk):
    for r in DATA["storage"]:
        if r.get("platform") == platform and r.get("produk") == produk:
            return r
    return None


def upsert_storage_row(platform, produk, values):
    row = get_storage_row(platform, produk)
    if row:
        row.update(values)
    else:
        DATA["storage"].append({"platform": platform, "produk": produk, **values})


def get_network_row(platform, produk):
    for r in DATA["network"]:
        if r.get("platform") == platform and r.get("produk") == produk:
            return r
    return None


def upsert_network_row(platform, produk, values):
    row = get_network_row(platform, produk)
    if row:
        row.update(values)
    else:
        DATA["network"].append({"platform": platform, "produk": produk, **values})


# ---------------------------------------------------------------------------
# COMPUTE ENGINE
# ---------------------------------------------------------------------------

def compute_all():
    utama_calc = calc.calc_infra_utama(DATA["infra_utama"])
    storage_calc = calc.calc_storage(DATA["storage"])
    network_calc = calc.calc_network(DATA["network"])
    pendukung_calc = calc.calc_pendukung(DATA["pendukung"])

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
            u_rows, pd_rows, s_rows, total_net,
        )
        platform_agg.append(agg)

    return {
        "utama": utama_calc, "storage": storage_calc, "network": network_calc,
        "pendukung": pendukung_calc, "cascade": cascade_calc, "platform_agg": platform_agg,
    }


RESULT = compute_all()


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="app-header"><span class="logo">📊</span><h1>Kalkulator Kapasitas Infrastruktur</h1></div>
    <p class="app-sub">Sizing infrastruktur IT berbasis TPS — isi Produk, lalu Infra & Storage, lalu Network, dan lihat hasilnya di Dashboard.</p>
    """,
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4 = st.tabs([
    "1️⃣  Produk & Kapasitas",
    "2️⃣  Infra (DB / Engine · CPU · Memori) & Storage",
    "3️⃣  Network",
    "4️⃣  Dashboard & Export",
])


# ---------------------------------------------------------------------------
# TAB 1 — PRODUK & KAPASITAS
# ---------------------------------------------------------------------------

with tab1:
    st.markdown('<div class="section-label">Platform & Kapasitas Existing</div>', unsafe_allow_html=True)
    st.caption("Kapasitas existing diisi manual — dari snapshot saat ini, atau rata-rata pemakaian 3 bulan terakhir.")

    with st.container(border=True):
        c0, c1, c2, c3, c4 = st.columns([2, 1, 1, 1, 1])
        nama_p = c0.text_input("Nama Platform", key="np_nama", placeholder="Contoh: Payment Switching")
        cpu_p = c1.number_input("CPU (vCore)", min_value=0.0, step=1.0, key="np_cpu")
        mem_p = c2.number_input("Memory (GB)", min_value=0.0, step=1.0, key="np_mem")
        sto_p = c3.number_input("Storage (GB)", min_value=0.0, step=1.0, key="np_sto")
        net_p = c4.number_input("Network (Mbps)", min_value=0.0, step=1.0, key="np_net")
        sumber_p = st.radio("Sumber data", ["Snapshot Current", "Rata-rata 3 Bulan"], horizontal=True, key="np_sumber")
        if st.button("💾 Simpan Platform", width='stretch', type="primary"):
            if not nama_p.strip():
                st.error("Nama platform wajib diisi.")
            else:
                upsert_platform(nama_p.strip(), cpu_p, mem_p, sto_p, net_p, sumber_p)
                st.success(f"Platform '{nama_p}' tersimpan.")
                st.rerun()

    if DATA["platforms"]:
        for p in DATA["platforms"]:
            with st.container(border=True):
                cc1, cc2 = st.columns([5, 1])
                cc1.markdown(
                    f"**{p['platform']}** &nbsp;·&nbsp; "
                    f"<span class='pill'>CPU <b>{fmt(p['cpu'],0)}</b> vCore</span> "
                    f"<span class='pill'>Mem <b>{fmt(p['memory'],0)}</b> GB</span> "
                    f"<span class='pill'>Storage <b>{fmt(p['storage'],0)}</b> GB</span> "
                    f"<span class='pill'>Net <b>{fmt(p['network'],0)}</b> Mbps</span> "
                    f"<span class='pill'>{p.get('sumber','')}</span>",
                    unsafe_allow_html=True,
                )
                if cc2.button("🗑️ Hapus", key=f"del_plat_{p['platform']}", width='stretch'):
                    delete_platform(p["platform"])
                    st.rerun()
    else:
        st.markdown('<div class="empty-box">Belum ada platform. Isi form di atas untuk mulai.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">Produk (berbasis TPS)</div>', unsafe_allow_html=True)

    if not DATA["platforms"]:
        st.info("Tambahkan platform terlebih dahulu sebelum menambah produk.")
    else:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1.4, 1.6, 1, 1])
            plat_sel = c1.selectbox("Platform", platform_names(), key="prod_platform")
            nama_produk = c2.text_input("Nama Produk", key="prod_nama", placeholder="Contoh: Core Banking - Payment Switching")
            cur_tps = c3.number_input("Current TPS", min_value=0.0, step=1.0, key="prod_cur_tps")
            fut_tps = c4.number_input("Future TPS", min_value=0.0, step=1.0, key="prod_fut_tps")
            if st.button("💾 Simpan Produk", width='stretch', type="primary"):
                if not nama_produk.strip():
                    st.error("Nama produk wajib diisi.")
                elif cur_tps < 0 or fut_tps < 0:
                    st.error("TPS tidak boleh negatif.")
                else:
                    upsert_produk_tps(plat_sel, nama_produk.strip(), cur_tps, fut_tps)
                    st.success(f"Produk '{nama_produk}' tersimpan di platform '{plat_sel}'.")
                    st.rerun()

        any_produk = False
        for plat in platform_names():
            produks = produk_for_platform(plat)
            for produk in produks:
                any_produk = True
                rows = get_infra_rows(plat, produk)
                cur_tps_show = next(iter(rows.values()))["current_tps"] if rows else 0
                fut_tps_show = next(iter(rows.values()))["future_tps"] if rows else 0
                with st.container(border=True):
                    cc1, cc2 = st.columns([5, 1])
                    cc1.markdown(
                        f"**{produk}** <span class='pill'>{plat}</span> "
                        f"<span class='pill'>Current <b>{fmt(cur_tps_show,0)}</b> TPS</span> "
                        f"<span class='pill'>Future <b>{fmt(fut_tps_show,0)}</b> TPS</span>",
                        unsafe_allow_html=True,
                    )
                    if cc2.button("🗑️ Hapus", key=f"del_prod_{plat}_{produk}", width='stretch'):
                        delete_produk(plat, produk)
                        st.rerun()
        if not any_produk:
            st.markdown('<div class="empty-box">Belum ada produk. Isi form di atas untuk menambah produk.</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# TAB 2 — INFRA (DB/ENGINE, CPU, MEMORI) & STORAGE
# ---------------------------------------------------------------------------

with tab2:
    all_pairs = [(plat, produk) for plat in platform_names() for produk in produk_for_platform(plat)]

    if not all_pairs:
        st.markdown('<div class="empty-box">Tambahkan Produk di tab 1 terlebih dahulu.</div>', unsafe_allow_html=True)
    else:
        labels = [f"{produk}  ·  {plat}" for plat, produk in all_pairs]
        pick = st.selectbox("Pilih Produk", labels, key="infra_pick")
        idx = labels.index(pick)
        plat_sel, produk_sel = all_pairs[idx]
        rows = get_infra_rows(plat_sel, produk_sel)
        db_row = rows.get("DB", {})
        eng_row = rows.get("Engine", {})

        st.markdown('<div class="section-label">Infra Utama — Database & Sistem/Engine</div>', unsafe_allow_html=True)
        with st.container(border=True):
            colA, colB = st.columns(2)
            with colA:
                st.markdown("**🗄️ Database (DB)**")
                db_cpu = st.number_input("Rasio CPU / TPS", min_value=0.0, step=0.001, format="%.4f",
                                          value=float(db_row.get("rasio_cpu", 0.0)), key="db_cpu")
                db_mem = st.number_input("Rasio Memory (GB) / TPS", min_value=0.0, step=0.001, format="%.4f",
                                          value=float(db_row.get("rasio_mem", 0.0)), key="db_mem")
            with colB:
                st.markdown("**⚙️ Sistem / Engine**")
                eng_cpu = st.number_input("Rasio CPU / TPS", min_value=0.0, step=0.001, format="%.4f",
                                           value=float(eng_row.get("rasio_cpu", 0.0)), key="eng_cpu")
                eng_mem = st.number_input("Rasio Memory (GB) / TPS", min_value=0.0, step=0.001, format="%.4f",
                                           value=float(eng_row.get("rasio_mem", 0.0)), key="eng_mem")

            st.markdown("**Parameter Bersama (DB & Engine)**")
            c1, c2, c3, c4 = st.columns(4)
            buffer_pct = c1.number_input("Buffer (%)", min_value=0.0, max_value=100.0, step=1.0,
                                          value=float(db_row.get("buffer_pct", 20.0)), key="infra_buffer")
            ha_mult = c2.number_input("HA Multiplier", min_value=1.0, max_value=5.0, step=1.0,
                                       value=float(db_row.get("ha_multiplier", 2.0)), key="infra_ha")
            kuota_cpu = c3.number_input("Kuota CPU Produk", min_value=0.0, step=1.0,
                                         value=float(db_row.get("kuota_cpu", 0.0)), key="infra_kcpu")
            kuota_mem = c4.number_input("Kuota Memory Produk", min_value=0.0, step=1.0,
                                         value=float(db_row.get("kuota_mem", 0.0)), key="infra_kmem")

            if st.button("💾 Simpan Infra Utama", width='stretch', type="primary"):
                for sistem, rc, rm in (("DB", db_cpu, db_mem), ("Engine", eng_cpu, eng_mem)):
                    target = rows.get(sistem)
                    target.update({
                        "rasio_cpu": rc, "rasio_mem": rm, "buffer_pct": buffer_pct,
                        "ha_multiplier": ha_mult, "kuota_cpu": kuota_cpu, "kuota_mem": kuota_mem,
                    })
                st.success("Infra Utama tersimpan.")
                st.rerun()

        # preview hasil hitung
        rows_after = get_infra_rows(plat_sel, produk_sel)
        if rows_after:
            res = calc.calc_infra_utama(list(rows_after.values()))
            total_cpu = sum(r["final_cpu"] for r in res)
            total_mem = sum(r["final_mem"] for r in res)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("FINAL CPU (DB+Engine)", f"{fmt(total_cpu)} vCore")
            k2.metric("FINAL Memory (DB+Engine)", f"{fmt(total_mem)} GB")
            util_cpu = calc.safe_div(total_cpu, kuota_cpu) * 100
            util_mem = calc.safe_div(total_mem, kuota_mem) * 100
            k3.markdown(f"Utilisasi CPU vs Kuota<br>{badge(calc.status_resource(util_cpu))} {fmt(util_cpu)}%", unsafe_allow_html=True)
            k4.markdown(f"Utilisasi Memory vs Kuota<br>{badge(calc.status_resource(util_mem))} {fmt(util_mem)}%", unsafe_allow_html=True)

        st.markdown('<div class="section-label">Storage</div>', unsafe_allow_html=True)
        srow = get_storage_row(plat_sel, produk_sel) or {}
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            vol_cur = c1.number_input("Volume Trx/Hari (Current)", min_value=0.0, step=1000.0,
                                       value=float(srow.get("vol_trx_current", 0.0)), key="sto_volcur")
            vol_fut = c2.number_input("Volume Trx/Hari (Future)", min_value=0.0, step=1000.0,
                                       value=float(srow.get("vol_trx_future", 0.0)), key="sto_volfut")
            ukuran_kb = c3.number_input("Ukuran Data/Trx (KB)", min_value=0.0, step=0.1,
                                         value=float(srow.get("ukuran_kb", 0.0)), key="sto_kb")
            c4, c5, c6, c7 = st.columns(4)
            retensi = c4.number_input("Retensi (hari)", min_value=0.0, step=1.0,
                                       value=float(srow.get("retensi_hari", 90.0)), key="sto_retensi")
            housekeeping = c5.number_input("Housekeeping Buffer (%)", min_value=0.0, max_value=100.0, step=1.0,
                                            value=float(srow.get("housekeeping_pct", 15.0)), key="sto_hk")
            sto_buffer = c6.number_input("Buffer (%)", min_value=0.0, max_value=100.0, step=1.0,
                                          value=float(srow.get("buffer_pct", 20.0)), key="sto_buffer")
            replication = c7.number_input("Replication/HA Multiplier", min_value=1.0, max_value=5.0, step=1.0,
                                           value=float(srow.get("replication_multiplier", 2.0)), key="sto_repl")
            kuota_storage = st.number_input("Kuota Storage Produk (GB)", min_value=0.0, step=100.0,
                                             value=float(srow.get("kuota_storage", 0.0)), key="sto_kuota")

            if st.button("💾 Simpan Storage", width='stretch', type="primary"):
                upsert_storage_row(plat_sel, produk_sel, {
                    "vol_trx_current": vol_cur, "vol_trx_future": vol_fut, "ukuran_kb": ukuran_kb,
                    "retensi_hari": retensi, "housekeeping_pct": housekeeping, "buffer_pct": sto_buffer,
                    "replication_multiplier": replication, "kuota_storage": kuota_storage,
                })
                st.success("Storage tersimpan.")
                st.rerun()

        srow_after = get_storage_row(plat_sel, produk_sel)
        if srow_after:
            res_s = calc.calc_storage_row(srow_after)
            k1, k2, k3 = st.columns(3)
            k1.metric("FINAL Storage", f"{fmt(res_s['final_storage_gb'])} GB")
            k2.metric("Storage @ Future (raw)", f"{fmt(res_s['storage_future_gb'])} GB")
            k3.markdown(f"Utilisasi vs Kuota<br>{badge(res_s['status_storage'])} {fmt(res_s['util_storage_pct'])}%", unsafe_allow_html=True)

        with st.expander("➕ Infra Pendukung (opsional) — Load Balancer, Monitoring, Backup, Firewall"):
            with st.form("form_pendukung", clear_on_submit=True):
                c1, c2, c3, c4 = st.columns(4)
                nama_pd = c1.text_input("Nama Komponen")
                fungsi_pd = c2.text_input("Fungsi")
                cpu_pd = c3.number_input("CPU (vCore)", min_value=0.0, step=1.0)
                mem_pd = c4.number_input("Memory (GB)", min_value=0.0, step=1.0)
                c5, c6, c7 = st.columns(3)
                storage_pd = c5.number_input("Storage (GB)", min_value=0.0, step=10.0)
                buffer_pd = c6.number_input("Buffer (%)", min_value=0.0, max_value=100.0, step=1.0, value=20.0)
                ha_pd = c7.number_input("HA Multiplier", min_value=1.0, max_value=5.0, step=1.0, value=2.0)
                if st.form_submit_button("Tambah Komponen Pendukung", width='stretch'):
                    if nama_pd.strip():
                        DATA["pendukung"].append({
                            "platform": plat_sel, "nama": nama_pd.strip(), "fungsi": fungsi_pd,
                            "cpu": cpu_pd, "memory": mem_pd, "storage": storage_pd,
                            "buffer_pct": buffer_pd, "ha_multiplier": ha_pd,
                        })
                        st.success(f"Komponen '{nama_pd}' ditambahkan ke platform '{plat_sel}'.")
                        st.rerun()

            pendukung_this = [x for x in DATA["pendukung"] if x.get("platform") == plat_sel]
            for i, pd_item in enumerate(pendukung_this):
                cc1, cc2 = st.columns([5, 1])
                cc1.markdown(
                    f"**{pd_item['nama']}** ({pd_item.get('fungsi','')}) — "
                    f"CPU {fmt(pd_item['cpu'],0)} vCore, Mem {fmt(pd_item['memory'],0)} GB, "
                    f"Storage {fmt(pd_item['storage'],0)} GB"
                )
                if cc2.button("🗑️", key=f"del_pendukung_{plat_sel}_{i}"):
                    DATA["pendukung"].remove(pd_item)
                    st.rerun()


# ---------------------------------------------------------------------------
# TAB 3 — NETWORK
# ---------------------------------------------------------------------------

with tab3:
    all_pairs = [(plat, produk) for plat in platform_names() for produk in produk_for_platform(plat)]

    if not all_pairs:
        st.markdown('<div class="empty-box">Tambahkan Produk di tab 1 terlebih dahulu.</div>', unsafe_allow_html=True)
    else:
        labels = [f"{produk}  ·  {plat}" for plat, produk in all_pairs]
        pick = st.selectbox("Pilih Produk", labels, key="net_pick")
        idx = labels.index(pick)
        plat_sel, produk_sel = all_pairs[idx]
        infra_rows = get_infra_rows(plat_sel, produk_sel)
        cur_tps = next(iter(infra_rows.values()))["current_tps"] if infra_rows else 0
        fut_tps = next(iter(infra_rows.values()))["future_tps"] if infra_rows else 0

        st.markdown('<div class="section-label">TPS → Bandwidth</div>', unsafe_allow_html=True)
        nrow = get_network_row(plat_sel, produk_sel) or {}
        with st.container(border=True):
            st.caption(f"Current TPS **{fmt(cur_tps,0)}** · Future TPS **{fmt(fut_tps,0)}** (mengikuti data Produk di tab 1)")
            c1, c2, c3 = st.columns(3)
            kb_req = c1.number_input("Bandwidth / Trx Request (KB)", min_value=0.0, step=0.1,
                                      value=float(nrow.get("kb_req", 0.0)), key="net_kbreq")
            kb_resp = c2.number_input("Bandwidth / Trx Response (KB)", min_value=0.0, step=0.1,
                                       value=float(nrow.get("kb_resp", 0.0)), key="net_kbresp")
            overhead = c3.number_input("Overhead Protokol (%)", min_value=0.0, max_value=100.0, step=1.0,
                                        value=float(nrow.get("overhead_pct", 15.0)), key="net_overhead")
            c4, c5 = st.columns(2)
            net_buffer = c4.number_input("Buffer (%)", min_value=0.0, max_value=100.0, step=1.0,
                                          value=float(nrow.get("buffer_pct", 30.0)), key="net_buffer")
            net_ha = c5.number_input("HA Multiplier", min_value=1.0, max_value=5.0, step=1.0,
                                      value=float(nrow.get("ha_multiplier", 2.0)), key="net_ha")

            if st.button("💾 Simpan Network", width='stretch', type="primary"):
                upsert_network_row(plat_sel, produk_sel, {
                    "current_tps": cur_tps, "future_tps": fut_tps,
                    "kb_req": kb_req, "kb_resp": kb_resp, "overhead_pct": overhead,
                    "buffer_pct": net_buffer, "ha_multiplier": net_ha,
                })
                st.success("Parameter Network tersimpan.")
                st.rerun()

        nrow_after = get_network_row(plat_sel, produk_sel)
        final_net = 0.0
        if nrow_after:
            res_n = calc.calc_network_row(nrow_after)
            final_net = res_n["final_network_mbps"]
            k1, k2 = st.columns(2)
            k1.metric("FINAL Bandwidth", f"{fmt(final_net)} Mbps")
            k2.metric("Required @ Future (raw)", f"{fmt(res_n['req_network_future_mbps'])} Mbps")

        st.markdown('<div class="section-label">Cascade ke Member / Link</div>', unsafe_allow_html=True)
        with st.form("form_link", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            nama_link = c1.text_input("Nama Link")
            pct_alokasi = c2.number_input("% Alokasi Trafik", min_value=0.0, max_value=100.0, step=5.0)
            existing_bw = c3.number_input("Existing Bandwidth @ Member (Mbps)", min_value=0.0, step=10.0)
            if st.form_submit_button("Tambah Link", width='stretch'):
                if nama_link.strip():
                    DATA["network_members"].append({
                        "platform": plat_sel, "produk": produk_sel, "nama_link": nama_link.strip(),
                        "pct_alokasi": pct_alokasi, "existing_bandwidth": existing_bw,
                    })
                    st.success(f"Link '{nama_link}' ditambahkan.")
                    st.rerun()

        members = [m for m in DATA["network_members"] if m.get("platform") == plat_sel and m.get("produk") == produk_sel]
        total_pct = sum(m["pct_alokasi"] for m in members)
        if members and abs(total_pct - 100) > 0.01:
            st.markdown(
                f'<div class="warn-box">⚠️ Total alokasi link = {fmt(total_pct,1)}%, idealnya 100%.</div>',
                unsafe_allow_html=True,
            )

        if members:
            cascade_rows = calc.calc_cascade(final_net, members)
            for i, r in enumerate(cascade_rows):
                with st.container(border=True):
                    cc1, cc2, cc3 = st.columns([3, 3, 1])
                    cc1.markdown(
                        f"**{r['nama_link']}** — alokasi {fmt(r['pct_alokasi'],1)}% · "
                        f"existing {fmt(r['existing_bandwidth'],0)} Mbps"
                    )
                    cc2.markdown(
                        f"Bandwidth dibutuhkan **{fmt(r['bandwidth_member_mbps'])}** Mbps · "
                        f"Sisa **{fmt(r['sisa_mbps'])}** Mbps · {badge(r['status_link'])} {fmt(r['util_link_pct'])}%",
                        unsafe_allow_html=True,
                    )
                    if cc3.button("🗑️", key=f"del_link_{plat_sel}_{produk_sel}_{i}"):
                        DATA["network_members"].remove(members[i])
                        st.rerun()
        else:
            st.markdown('<div class="empty-box">Belum ada link/member. Tambahkan di form atas.</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# TAB 4 — DASHBOARD & EXPORT
# ---------------------------------------------------------------------------

with tab4:
    if not DATA["platforms"]:
        st.markdown('<div class="empty-box">Belum ada data. Mulai dari tab 1.</div>', unsafe_allow_html=True)
    else:
        platform_pick = st.selectbox("Pilih Platform", platform_names(), key="dash_platform")
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
                                <span style="color:#94a3b8;font-size:0.78rem"> · {fmt(util)}% terpakai</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            g1, g2, g3, g4 = st.columns(4)
            g1.plotly_chart(gauge_chart("CPU", agg["total_cpu"], agg["existing_cpu"]), width='stretch')
            g2.plotly_chart(gauge_chart("Memory", agg["total_mem"], agg["existing_mem"]), width='stretch')
            g3.plotly_chart(gauge_chart("Storage", agg["total_storage"], agg["existing_storage"]), width='stretch')
            g4.plotly_chart(gauge_chart("Network", agg["total_network"], agg["existing_network"]), width='stretch')

        st.markdown(
            """
            <div class="note-box">
            💡 Status per Produk (vs Kuota Produk) bisa <b>HIJAU</b> meski status Platform (vs Kapasitas
            Existing) <b>MERAH</b> — kuota produk adalah alokasi internal, sedangkan status platform
            mencerminkan total pemakaian gabungan terhadap kapasitas fisik existing.
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("📋 Detail per Platform"):
            df_l1 = pd.DataFrame(RESULT["platform_agg"])
            if not df_l1.empty:
                st.dataframe(df_l1.round(2), width='stretch', hide_index=True)

        with st.expander("📋 Detail per Produk (Infra Utama)"):
            df_l2 = pd.DataFrame(RESULT["utama"])
            if not df_l2.empty:
                st.dataframe(df_l2.round(2), width='stretch', hide_index=True)

        over_rows = []
        for _, row in pd.DataFrame(RESULT["platform_agg"]).iterrows():
            for res, label in [("cpu", "CPU"), ("mem", "Memory"), ("storage", "Storage"), ("network", "Network")]:
                if row[f"status_{res}"] == "OVER CAPACITY":
                    over_rows.append({
                        "Platform": row["platform"], "Resource": label,
                        "Total Kebutuhan": row[f"total_{res}"], "Existing": row[f"existing_{res}"],
                        "Utilisasi %": row[f"util_{res}_pct"],
                    })
        if over_rows:
            st.markdown("#### 🔴 Resource OVER CAPACITY")
            st.dataframe(pd.DataFrame(over_rows).round(2), width='stretch', hide_index=True)

        st.markdown('<div class="section-label">Export & Reset</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)

        with c1:
            json_bytes = json.dumps(DATA, indent=2, ensure_ascii=False).encode("utf-8")
            st.download_button("⬇️ Download JSON", data=json_bytes, file_name="kapasitas_infrastruktur.json",
                                mime="application/json", width='stretch')

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
            st.download_button("⬇️ Download Excel", data=buffer.getvalue(), file_name="kapasitas_infrastruktur.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')

        with c3:
            if st.button("🔄 Reset ke Data Contoh", width='stretch'):
                st.session_state["data"] = sample_data.get_sample_state()
                st.rerun()

        with st.expander("Upload / Load JSON"):
            uploaded = st.file_uploader("Load state dari file JSON", type=["json"])
            if uploaded is not None:
                try:
                    loaded = json.load(uploaded)
                    st.session_state["data"] = loaded
                    st.success("Data berhasil dimuat.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal memuat file: {e}")
