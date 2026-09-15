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
