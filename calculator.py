"""
calculator.py
Semua rumus murni untuk Kalkulator Kapasitas Infrastruktur.
Tidak ada logika UI di sini — hanya fungsi hitung.
"""

from __future__ import annotations
from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# Status / traffic-light helpers
# ---------------------------------------------------------------------------

def status_resource(utilization_pct: float) -> str:
    """Status untuk CPU/Memory/Storage/Network (produk vs kuota).
    HIJAU <=70%, KUNING 70-90%, MERAH >90%
    """
    if utilization_pct <= 70:
        return "HIJAU"
    if utilization_pct <= 90:
        return "KUNING"
    return "MERAH"


def status_link(utilization_pct: float) -> str:
    """Status untuk link/member network.
    OK <=70%, WARNING 70-100%, OVER CAPACITY >100%
    """
    if utilization_pct <= 70:
        return "OK"
    if utilization_pct <= 100:
        return "WARNING"
    return "OVER CAPACITY"


def status_global(utilization_pct: float) -> str:
    """Status global vs kapasitas existing platform.
    OK <=80%, WARNING 80-100%, OVER CAPACITY >100%
    """
    if utilization_pct <= 80:
        return "OK"
    if utilization_pct <= 100:
        return "WARNING"
    return "OVER CAPACITY"


STATUS_COLOR = {
    "HIJAU": "#16a34a",
    "KUNING": "#f59e0b",
    "MERAH": "#dc2626",
    "OK": "#16a34a",
    "WARNING": "#f59e0b",
    "OVER CAPACITY": "#dc2626",
}


def safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


# ---------------------------------------------------------------------------
# INFRA UTAMA (TPS based) — CPU & Memory
# ---------------------------------------------------------------------------

def calc_required(tps: float, rasio: float) -> float:
    """Required = TPS x Rasio"""
    return tps * rasio


def calc_final(required_future: float, buffer_pct: float, ha_multiplier: float) -> float:
    """FINAL = Required@Future x (1 + Buffer%) x HA Multiplier"""
    return required_future * (1 + buffer_pct / 100.0) * ha_multiplier


def calc_infra_utama_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Hitung satu baris infra utama (DB atau Engine) untuk CPU & Memory.

    row wajib berisi:
      current_tps, future_tps,
      rasio_cpu, rasio_mem,
      buffer_pct, ha_multiplier,
      kuota_cpu, kuota_mem
    """
    current_tps = float(row.get("current_tps", 0) or 0)
    future_tps = float(row.get("future_tps", 0) or 0)
    rasio_cpu = float(row.get("rasio_cpu", 0) or 0)
    rasio_mem = float(row.get("rasio_mem", 0) or 0)
    buffer_pct = float(row.get("buffer_pct", 0) or 0)
    ha_multiplier = float(row.get("ha_multiplier", 1) or 1)
    kuota_cpu = float(row.get("kuota_cpu", 0) or 0)
    kuota_mem = float(row.get("kuota_mem", 0) or 0)

    req_cpu_current = calc_required(current_tps, rasio_cpu)
    req_cpu_future = calc_required(future_tps, rasio_cpu)
    req_mem_current = calc_required(current_tps, rasio_mem)
    req_mem_future = calc_required(future_tps, rasio_mem)

    final_cpu = calc_final(req_cpu_future, buffer_pct, ha_multiplier)
    final_mem = calc_final(req_mem_future, buffer_pct, ha_multiplier)

    util_cpu = safe_div(final_cpu, kuota_cpu) * 100
    util_mem = safe_div(final_mem, kuota_mem) * 100

    result = dict(row)
    result.update({
        "req_cpu_current": req_cpu_current,
        "req_cpu_future": req_cpu_future,
        "req_mem_current": req_mem_current,
        "req_mem_future": req_mem_future,
        "final_cpu": final_cpu,
        "final_mem": final_mem,
        "util_cpu_pct": util_cpu,
        "util_mem_pct": util_mem,
        "status_cpu": status_resource(util_cpu),
        "status_mem": status_resource(util_mem),
    })
    return result


def calc_infra_utama(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [calc_infra_utama_row(r) for r in rows]


# ---------------------------------------------------------------------------
# STORAGE (retensi based)
# ---------------------------------------------------------------------------

def calc_storage_gb(vol_trx_hari: float, ukuran_kb: float, retensi_hari: float,
                     housekeeping_pct: float) -> float:
    """Storage (GB) = VolTrxHari x UkuranKB x RetensiHari x (1+Housekeeping%) / 1,048,576"""
    return (vol_trx_hari * ukuran_kb * retensi_hari * (1 + housekeeping_pct / 100.0)) / 1_048_576.0


def calc_storage_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """row wajib berisi:
    vol_trx_current, vol_trx_future, ukuran_kb, retensi_hari,
    housekeeping_pct, buffer_pct, replication_multiplier, kuota_storage
    """
    vol_current = float(row.get("vol_trx_current", 0) or 0)
    vol_future = float(row.get("vol_trx_future", 0) or 0)
    ukuran_kb = float(row.get("ukuran_kb", 0) or 0)
    retensi_hari = float(row.get("retensi_hari", 0) or 0)
    housekeeping_pct = float(row.get("housekeeping_pct", 0) or 0)
    buffer_pct = float(row.get("buffer_pct", 0) or 0)
    replication_multiplier = float(row.get("replication_multiplier", 1) or 1)
    kuota_storage = float(row.get("kuota_storage", 0) or 0)

    storage_current = calc_storage_gb(vol_current, ukuran_kb, retensi_hari, housekeeping_pct)
    storage_future = calc_storage_gb(vol_future, ukuran_kb, retensi_hari, housekeeping_pct)

    final_storage = storage_future * (1 + buffer_pct / 100.0) * replication_multiplier

    util_pct = safe_div(final_storage, kuota_storage) * 100

    result = dict(row)
    result.update({
        "storage_current_gb": storage_current,
        "storage_future_gb": storage_future,
        "final_storage_gb": final_storage,
        "util_storage_pct": util_pct,
        "status_storage": status_resource(util_pct),
    })
    return result


def calc_storage(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [calc_storage_row(r) for r in rows]


# ---------------------------------------------------------------------------
# NETWORK (TPS -> bandwidth) + cascade ke member/link
# ---------------------------------------------------------------------------

def calc_network_required(tps: float, kb_req: float, kb_resp: float, overhead_pct: float) -> float:
    """Network Required (Mbps) = TPS x (KB Req + KB Resp) x 8 x (1+Overhead%) / 1000"""
    return tps * (kb_req + kb_resp) * 8 * (1 + overhead_pct / 100.0) / 1000.0


def calc_network_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """row wajib berisi:
    current_tps, future_tps, kb_req, kb_resp, overhead_pct, buffer_pct, ha_multiplier
    """
    current_tps = float(row.get("current_tps", 0) or 0)
    future_tps = float(row.get("future_tps", 0) or 0)
    kb_req = float(row.get("kb_req", 0) or 0)
    kb_resp = float(row.get("kb_resp", 0) or 0)
    overhead_pct = float(row.get("overhead_pct", 0) or 0)
    buffer_pct = float(row.get("buffer_pct", 0) or 0)
    ha_multiplier = float(row.get("ha_multiplier", 1) or 1)

    req_current = calc_network_required(current_tps, kb_req, kb_resp, overhead_pct)
    req_future = calc_network_required(future_tps, kb_req, kb_resp, overhead_pct)

    final_network = req_future * (1 + buffer_pct / 100.0) * ha_multiplier

    result = dict(row)
    result.update({
        "req_network_current_mbps": req_current,
        "req_network_future_mbps": req_future,
        "final_network_mbps": final_network,
    })
    return result


def calc_network(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [calc_network_row(r) for r in rows]


def calc_cascade_row(final_network_mbps: float, row: Dict[str, Any]) -> Dict[str, Any]:
    """row wajib berisi: nama_link, pct_alokasi, existing_bandwidth"""
    pct_alokasi = float(row.get("pct_alokasi", 0) or 0)
    existing_bandwidth = float(row.get("existing_bandwidth", 0) or 0)

    bandwidth_member = final_network_mbps * (pct_alokasi / 100.0)
    sisa = existing_bandwidth - bandwidth_member
    util_pct = safe_div(bandwidth_member, existing_bandwidth) * 100

    result = dict(row)
    result.update({
        "bandwidth_member_mbps": bandwidth_member,
        "sisa_mbps": sisa,
        "util_link_pct": util_pct,
        "status_link": status_link(util_pct),
    })
    return result


def calc_cascade(final_network_mbps: float, members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [calc_cascade_row(final_network_mbps, m) for m in members]


# ---------------------------------------------------------------------------
# INFRA PENDUKUNG (non-TPS)
# ---------------------------------------------------------------------------

def calc_pendukung_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """row wajib berisi: cpu, memory, storage, buffer_pct, ha_multiplier"""
    cpu = float(row.get("cpu", 0) or 0)
    memory = float(row.get("memory", 0) or 0)
    storage = float(row.get("storage", 0) or 0)
    buffer_pct = float(row.get("buffer_pct", 0) or 0)
    ha_multiplier = float(row.get("ha_multiplier", 1) or 1)

    final_cpu = cpu * (1 + buffer_pct / 100.0) * ha_multiplier
    final_mem = memory * (1 + buffer_pct / 100.0) * ha_multiplier
    final_storage = storage * (1 + buffer_pct / 100.0) * ha_multiplier

    result = dict(row)
    result.update({
        "final_cpu": final_cpu,
        "final_mem": final_mem,
        "final_storage": final_storage,
    })
    return result


def calc_pendukung(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [calc_pendukung_row(r) for r in rows]


# ---------------------------------------------------------------------------
# AGGREGATION per Platform (Layer 1) vs Kapasitas Existing
# ---------------------------------------------------------------------------

def calc_max_tps_resource(kuota_or_existing: float, per_tps_factor: float) -> float:
    """Kapasitas Maksimum TPS untuk satu resource = kuota (atau existing) / FINAL-per-TPS.
    FINAL-per-TPS sudah termasuk buffer% dan HA Multiplier."""
    if per_tps_factor <= 0:
        return float("inf")
    return kuota_or_existing / per_tps_factor


def calc_max_tps_capacity(
    db_row: Dict[str, Any],
    eng_row: Dict[str, Any],
    network_row: Dict[str, Any] | None,
    existing_network: float,
) -> Dict[str, Any]:
    """Hitung Kapasitas Maksimum Transaksi (TPS) suatu produk — TPS tertinggi yang
    masih bisa ditampung sebelum salah satu resource (CPU/Memory/Network) mencapai
    100% dari kuota/kapasitas existing-nya. Storage tidak dihitung di sini karena
    didorong oleh volume transaksi/hari, bukan TPS langsung.

    db_row & eng_row: baris infra_utama (sistem DB & Engine) milik produk yang sama.
    network_row: baris network produk (boleh None jika belum diisi).
    """
    rasio_cpu_total = float(db_row.get("rasio_cpu", 0) or 0) + float(eng_row.get("rasio_cpu", 0) or 0)
    rasio_mem_total = float(db_row.get("rasio_mem", 0) or 0) + float(eng_row.get("rasio_mem", 0) or 0)
    buffer_pct = float(db_row.get("buffer_pct", 0) or 0)
    ha_multiplier = float(db_row.get("ha_multiplier", 1) or 1)
    kuota_cpu = float(db_row.get("kuota_cpu", 0) or 0)
    kuota_mem = float(db_row.get("kuota_mem", 0) or 0)

    factor_cpu = rasio_cpu_total * (1 + buffer_pct / 100.0) * ha_multiplier
    factor_mem = rasio_mem_total * (1 + buffer_pct / 100.0) * ha_multiplier

    per_resource = {
        "CPU": calc_max_tps_resource(kuota_cpu, factor_cpu),
        "Memory": calc_max_tps_resource(kuota_mem, factor_mem),
    }

    if network_row:
        kb_req = float(network_row.get("kb_req", 0) or 0)
        kb_resp = float(network_row.get("kb_resp", 0) or 0)
        overhead_pct = float(network_row.get("overhead_pct", 0) or 0)
        net_buffer_pct = float(network_row.get("buffer_pct", 0) or 0)
        net_ha = float(network_row.get("ha_multiplier", 1) or 1)
        factor_net = (
            (kb_req + kb_resp) * 8 * (1 + overhead_pct / 100.0) / 1000.0
            * (1 + net_buffer_pct / 100.0) * net_ha
        )
        per_resource["Network"] = calc_max_tps_resource(float(existing_network or 0), factor_net)

    bottleneck_resource = min(per_resource, key=per_resource.get)
    max_tps = per_resource[bottleneck_resource]

    return {
        "per_resource": per_resource,
        "bottleneck_resource": bottleneck_resource,
        "max_tps": max_tps,
    }


# ---------------------------------------------------------------------------
# RIWAYAT BULANAN (actual TPS per bulan -> utilisasi)
# ---------------------------------------------------------------------------

def calc_monthly_utilization(
    tps_aktual: float,
    db_row: Dict[str, Any],
    eng_row: Dict[str, Any],
    kuota_cpu: float,
    kuota_mem: float,
    network_row: Dict[str, Any] | None = None,
    existing_network: float = 0.0,
    vol_trx_aktual: float | None = None,
    storage_row: Dict[str, Any] | None = None,
    kuota_storage: float = 0.0,
) -> Dict[str, Any]:
    """Hitung utilisasi CPU/Memory/(Network)/(Storage) dari satu TPS aktual bulan
    tertentu, memakai rasio/buffer/HA/kuota yang sedang aktif di Infra Utama produk.
    Dipakai untuk grafik Riwayat Bulanan (bukan proyeksi forecast)."""
    rasio_cpu_total = float(db_row.get("rasio_cpu", 0) or 0) + float(eng_row.get("rasio_cpu", 0) or 0)
    rasio_mem_total = float(db_row.get("rasio_mem", 0) or 0) + float(eng_row.get("rasio_mem", 0) or 0)
    buffer_pct = float(db_row.get("buffer_pct", 0) or 0)
    ha_multiplier = float(db_row.get("ha_multiplier", 1) or 1)

    final_cpu = tps_aktual * rasio_cpu_total * (1 + buffer_pct / 100.0) * ha_multiplier
    final_mem = tps_aktual * rasio_mem_total * (1 + buffer_pct / 100.0) * ha_multiplier
    util_cpu = safe_div(final_cpu, kuota_cpu) * 100
    util_mem = safe_div(final_mem, kuota_mem) * 100

    result = {
        "tps_aktual": tps_aktual,
        "final_cpu": final_cpu,
        "final_mem": final_mem,
        "util_cpu_pct": util_cpu,
        "util_mem_pct": util_mem,
        "status_cpu": status_resource(util_cpu),
        "status_mem": status_resource(util_mem),
    }

    if network_row:
        kb_req = float(network_row.get("kb_req", 0) or 0)
        kb_resp = float(network_row.get("kb_resp", 0) or 0)
        overhead_pct = float(network_row.get("overhead_pct", 0) or 0)
        net_buffer_pct = float(network_row.get("buffer_pct", 0) or 0)
        net_ha = float(network_row.get("ha_multiplier", 1) or 1)
        req_net = calc_network_required(tps_aktual, kb_req, kb_resp, overhead_pct)
        final_net = req_net * (1 + net_buffer_pct / 100.0) * net_ha
        util_net = safe_div(final_net, existing_network) * 100
        result.update({
            "final_network": final_net,
            "util_network_pct": util_net,
            "status_network": status_resource(util_net),
        })

    if storage_row and vol_trx_aktual is not None:
        ukuran_kb = float(storage_row.get("ukuran_kb", 0) or 0)
        retensi_hari = float(storage_row.get("retensi_hari", 0) or 0)
        housekeeping_pct = float(storage_row.get("housekeeping_pct", 0) or 0)
        sto_buffer_pct = float(storage_row.get("buffer_pct", 0) or 0)
        replication_multiplier = float(storage_row.get("replication_multiplier", 1) or 1)
        storage_gb = calc_storage_gb(vol_trx_aktual, ukuran_kb, retensi_hari, housekeeping_pct)
        final_storage = storage_gb * (1 + sto_buffer_pct / 100.0) * replication_multiplier
        util_storage = safe_div(final_storage, kuota_storage) * 100
        result.update({
            "vol_trx_aktual": vol_trx_aktual,
            "final_storage": final_storage,
            "util_storage_pct": util_storage,
            "status_storage": status_resource(util_storage),
        })

    return result


# ---------------------------------------------------------------------------
# FORECAST & SCENARIO (linear)
# ---------------------------------------------------------------------------

def calc_linear_scenario(
    base_tps: float,
    growth_pct_per_period: float,
    n_periods: int,
    db_row: Dict[str, Any],
    eng_row: Dict[str, Any],
    kuota_cpu: float,
    kuota_mem: float,
    network_row: Dict[str, Any] | None,
    existing_network: float,
    storage_row: Dict[str, Any] | None,
    kuota_storage: float,
) -> List[Dict[str, Any]]:
    """Simulasi linear: TPS(n) = base_tps x (1 + growth% x n), n = 0..n_periods.
    Volume transaksi storage diasumsikan naik proporsional dengan TPS.
    Mengembalikan satu baris hasil per periode, lengkap dengan status traffic-light.
    """
    rasio_cpu_total = float(db_row.get("rasio_cpu", 0) or 0) + float(eng_row.get("rasio_cpu", 0) or 0)
    rasio_mem_total = float(db_row.get("rasio_mem", 0) or 0) + float(eng_row.get("rasio_mem", 0) or 0)
    buffer_pct = float(db_row.get("buffer_pct", 0) or 0)
    ha_multiplier = float(db_row.get("ha_multiplier", 1) or 1)

    vol_trx_base = float(storage_row.get("vol_trx_current", 0) or 0) if storage_row else 0.0
    ukuran_kb = float(storage_row.get("ukuran_kb", 0) or 0) if storage_row else 0.0
    retensi_hari = float(storage_row.get("retensi_hari", 0) or 0) if storage_row else 0.0
    housekeeping_pct = float(storage_row.get("housekeeping_pct", 0) or 0) if storage_row else 0.0
    sto_buffer_pct = float(storage_row.get("buffer_pct", 0) or 0) if storage_row else 0.0
    replication_multiplier = float(storage_row.get("replication_multiplier", 1) or 1) if storage_row else 1.0

    results = []
    for n in range(0, n_periods + 1):
        growth_factor = 1 + (growth_pct_per_period / 100.0) * n
        tps_n = base_tps * growth_factor

        final_cpu = tps_n * rasio_cpu_total * (1 + buffer_pct / 100.0) * ha_multiplier
        final_mem = tps_n * rasio_mem_total * (1 + buffer_pct / 100.0) * ha_multiplier
        util_cpu = safe_div(final_cpu, kuota_cpu) * 100
        util_mem = safe_div(final_mem, kuota_mem) * 100

        row = {
            "periode": n,
            "tps": tps_n,
            "final_cpu": final_cpu,
            "final_mem": final_mem,
            "util_cpu_pct": util_cpu,
            "util_mem_pct": util_mem,
            "status_cpu": status_resource(util_cpu),
            "status_mem": status_resource(util_mem),
        }

        if network_row:
            kb_req = float(network_row.get("kb_req", 0) or 0)
            kb_resp = float(network_row.get("kb_resp", 0) or 0)
            overhead_pct = float(network_row.get("overhead_pct", 0) or 0)
            net_buffer_pct = float(network_row.get("buffer_pct", 0) or 0)
            net_ha = float(network_row.get("ha_multiplier", 1) or 1)
            req_net = calc_network_required(tps_n, kb_req, kb_resp, overhead_pct)
            final_net = req_net * (1 + net_buffer_pct / 100.0) * net_ha
            util_net = safe_div(final_net, existing_network) * 100
            row.update({
                "final_network": final_net,
                "util_network_pct": util_net,
                "status_network": status_resource(util_net),
            })

        if storage_row:
            vol_trx_n = vol_trx_base * growth_factor
            storage_n = calc_storage_gb(vol_trx_n, ukuran_kb, retensi_hari, housekeeping_pct)
            final_storage = storage_n * (1 + sto_buffer_pct / 100.0) * replication_multiplier
            util_storage = safe_div(final_storage, kuota_storage) * 100
            row.update({
                "final_storage": final_storage,
                "util_storage_pct": util_storage,
                "status_storage": status_resource(util_storage),
            })

        results.append(row)

    return results


def find_breach_period(scenario_rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Cari periode pertama di mana salah satu resource melewati 100% kuota/kapasitas.
    Return None jika sampai akhir periode tidak ada yang breach."""
    resource_keys = [k for k in ("util_cpu_pct", "util_mem_pct", "util_network_pct", "util_storage_pct")]
    for row in scenario_rows:
        for key in resource_keys:
            if key in row and row[key] > 100:
                return {
                    "periode": row["periode"],
                    "tps": row["tps"],
                    "resource": key.replace("util_", "").replace("_pct", "").upper(),
                    "utilisasi_pct": row[key],
                }
    return None


def aggregate_platform(
    platform_name: str,
    existing: Dict[str, float],
    infra_utama_rows: List[Dict[str, Any]],
    pendukung_rows: List[Dict[str, Any]],
    storage_rows: List[Dict[str, Any]],
    network_final_mbps: float,
) -> Dict[str, Any]:
    """Agregasi total kebutuhan (FINAL) suatu platform terhadap kapasitas existing.

    existing: {"cpu": ..., "memory": ..., "storage": ..., "network": ...}
    infra_utama_rows/pendukung_rows/storage_rows: hanya baris milik platform ini (sudah dihitung
        atau akan dihitung ulang oleh fungsi ini bila belum memiliki key final_*).
    """
    utama_calc = [r if "final_cpu" in r else calc_infra_utama_row(r) for r in infra_utama_rows]
    pendukung_calc = [r if "final_cpu" in r else calc_pendukung_row(r) for r in pendukung_rows]
    storage_calc = [r if "final_storage_gb" in r else calc_storage_row(r) for r in storage_rows]

    total_cpu = sum(r["final_cpu"] for r in utama_calc) + sum(r["final_cpu"] for r in pendukung_calc)
    total_mem = sum(r["final_mem"] for r in utama_calc) + sum(r["final_mem"] for r in pendukung_calc)
    total_storage = sum(r["final_storage_gb"] for r in storage_calc) + sum(
        r["final_storage"] for r in pendukung_calc
    )
    total_network = network_final_mbps

    existing_cpu = float(existing.get("cpu", 0) or 0)
    existing_mem = float(existing.get("memory", 0) or 0)
    existing_storage = float(existing.get("storage", 0) or 0)
    existing_network = float(existing.get("network", 0) or 0)

    def sisa_util(total, existing_val):
        sisa = existing_val - total
        util = safe_div(total, existing_val) * 100
        return sisa, util

    sisa_cpu, util_cpu = sisa_util(total_cpu, existing_cpu)
    sisa_mem, util_mem = sisa_util(total_mem, existing_mem)
    sisa_storage, util_storage = sisa_util(total_storage, existing_storage)
    sisa_network, util_network = sisa_util(total_network, existing_network)

    return {
        "platform": platform_name,
        "existing_cpu": existing_cpu,
        "existing_mem": existing_mem,
        "existing_storage": existing_storage,
        "existing_network": existing_network,
        "total_cpu": total_cpu,
        "total_mem": total_mem,
        "total_storage": total_storage,
        "total_network": total_network,
        "sisa_cpu": sisa_cpu,
        "sisa_mem": sisa_mem,
        "sisa_storage": sisa_storage,
        "sisa_network": sisa_network,
        "util_cpu_pct": util_cpu,
        "util_mem_pct": util_mem,
        "util_storage_pct": util_storage,
        "util_network_pct": util_network,
        "status_cpu": status_global(util_cpu),
        "status_mem": status_global(util_mem),
        "status_storage": status_global(util_storage),
        "status_network": status_global(util_network),
    }
