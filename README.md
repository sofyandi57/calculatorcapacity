# Kalkulator Kapasitas Infrastruktur

Aplikasi web Streamlit untuk sizing infrastruktur IT berbasis TPS (Transaction Per
Second). User cukup memasukkan kapasitas existing/sisa kapasitas platform (dari
snapshot atau rata-rata 3 bulan terakhir) beserta parameter sizing (TPS, rasio,
retensi, buffer, HA multiplier), dan sistem menghitung otomatis sisa kapasitas
dengan indikator traffic-light (Hijau/Kuning/Merah).

## Struktur File

- `app.py` — UI utama (navigasi sidebar, dashboard, form input, tabel editable).
- `calculator.py` — semua rumus perhitungan (murni Python, tanpa dependensi UI).
- `sample_data.py` — data contoh (preload) untuk demo/testing.
- `requirements.txt` — daftar dependensi.

## Cara Run Lokal

1. Buat virtual environment (opsional tapi disarankan):

   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependensi:

   ```bash
   pip install -r requirements.txt
   ```

3. Jalankan aplikasi:

   ```bash
   streamlit run app.py
   ```

4. Buka browser ke `http://localhost:8501`.

## Deploy ke Streamlit Community Cloud

1. Push repository ini ke GitHub.
2. Buka [share.streamlit.io](https://share.streamlit.io) dan login dengan akun GitHub.
3. Klik **New app**, pilih repository, branch, dan file utama `app.py`.
4. Klik **Deploy**. Streamlit Cloud akan otomatis membaca `requirements.txt`
   dan menginstall dependensi yang dibutuhkan.
5. Setelah deploy selesai, aplikasi dapat diakses melalui URL yang diberikan
   Streamlit Cloud.

## Catatan Perhitungan

Semua rumus mengikuti standar sizing berbasis TPS:

- `Required = TPS × Rasio`
- `FINAL = Required@Future × (1 + Buffer%) × HA Multiplier`
- `Storage (GB) = VolTrxHari × UkuranKB × RetensiHari × (1+Housekeeping%) / 1.048.576`
- `Network (Mbps) = TPS × (KB Request + KB Response) × 8 × (1+Overhead%) / 1000`

Status traffic-light:

- **Resource (CPU/Memory/Storage/Network) vs Kuota Produk**: Hijau ≤70%, Kuning 70–90%, Merah >90%.
- **Link/Member Network**: OK ≤70%, Warning 70–100%, Over Capacity >100%.
- **Global (vs Kapasitas Existing Platform)**: OK ≤80%, Warning 80–100%, Over Capacity >100%.

Layer 2 (per Produk, vs kuota internal) bisa berstatus Hijau meski Layer 1
(per Platform, vs kapasitas fisik existing) berstatus Merah — ini normal
karena kuota produk adalah alokasi internal, bukan batas fisik.
