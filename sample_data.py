"""
sample_data.py
Data contoh (preload) untuk Kalkulator Kapasitas Infrastruktur.
Mengikuti contoh Payment Switching pada spesifikasi.
"""

from __future__ import annotations
import copy


def get_sample_state() -> dict:
    """Return dict state awal (deep-copied) yang siap dipakai sebagai
    st.session_state["data"]."""

    state = {
        "platforms": [
            {
                "platform": "Payment Switching",
                "cpu": 200.0,
                "memory": 1024.0,
                "storage": 40000.0,
                "network": 500.0,
                "sumber": "Snapshot Current",
            }
        ],
        "infra_utama": [
            {
                "platform": "Payment Switching",
                "produk": "Core Banking - Payment Switching",
                "sistem": "DB",
                "kategori": "Utama",
                "current_tps": 500.0,
                "future_tps": 1200.0,
                "rasio_cpu": 0.004,
                "rasio_mem": 0.02,
                "rasio_storage": 0.05,
                "buffer_pct": 20.0,
                "ha_multiplier": 2.0,
                "kuota_cpu": 45.0,
                "kuota_mem": 180.0,
            },
            {
                "platform": "Payment Switching",
                "produk": "Core Banking - Payment Switching",
                "sistem": "Engine",
                "kategori": "Utama",
                "current_tps": 500.0,
                "future_tps": 1200.0,
                "rasio_cpu": 0.008,
                "rasio_mem": 0.03,
                "rasio_storage": 0.005,
                "buffer_pct": 20.0,
                "ha_multiplier": 2.0,
                "kuota_cpu": 45.0,
                "kuota_mem": 180.0,
            },
        ],
        "storage": [
            {
                "platform": "Payment Switching",
                "produk": "Core Banking - Payment Switching",
                "vol_trx_current": 43_200_000.0,
                "vol_trx_future": 103_680_000.0,
                "ukuran_kb": 2.0,
                "retensi_hari": 90.0,
                "housekeeping_pct": 15.0,
                "buffer_pct": 20.0,
                "replication_multiplier": 2.0,
                "kuota_storage": 60000.0,
            }
        ],
        "network": [
            {
                "platform": "Payment Switching",
                "produk": "Core Banking - Payment Switching",
                "current_tps": 500.0,
                "future_tps": 1200.0,
                "kb_req": 1.5,
                "kb_resp": 2.5,
                "overhead_pct": 15.0,
                "buffer_pct": 30.0,
                "ha_multiplier": 2.0,
            }
        ],
        "network_members": [
            {
                "platform": "Payment Switching",
                "produk": "Core Banking - Payment Switching",
                "nama_link": "ISP-1",
                "pct_alokasi": 60.0,
                "existing_bandwidth": 500.0,
            },
            {
                "platform": "Payment Switching",
                "produk": "Core Banking - Payment Switching",
                "nama_link": "ISP-2",
                "pct_alokasi": 40.0,
                "existing_bandwidth": 500.0,
            },
        ],
        "pendukung": [
            {
                "platform": "Payment Switching",
                "nama": "Load Balancer",
                "fungsi": "Cluster",
                "cpu": 4.0,
                "memory": 16.0,
                "storage": 200.0,
                "buffer_pct": 20.0,
                "ha_multiplier": 2.0,
            }
        ],
        "monthly_history": [
            {"platform": "Payment Switching", "produk": "Core Banking - Payment Switching",
             "bulan": "Juni 2026", "tps_aktual": 950.0, "vol_trx_aktual": 38_500_000.0},
            {"platform": "Payment Switching", "produk": "Core Banking - Payment Switching",
             "bulan": "Juli 2026", "tps_aktual": 1050.0, "vol_trx_aktual": 40_800_000.0},
            {"platform": "Payment Switching", "produk": "Core Banking - Payment Switching",
             "bulan": "Agustus 2026", "tps_aktual": 1150.0, "vol_trx_aktual": 43_200_000.0},
        ],
    }
    return copy.deepcopy(state)


def get_empty_state() -> dict:
    return {
        "platforms": [],
        "infra_utama": [],
        "storage": [],
        "network": [],
        "network_members": [],
        "pendukung": [],
        "monthly_history": [],
    }
