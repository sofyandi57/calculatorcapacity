# Kalkulator Kapasitas Infrastruktur

Aplikasi web Streamlit untuk sizing infrastruktur IT berbasis TPS (Transaction Per
Second). User cukup memasukkan kapasitas existing/sisa kapasitas platform (dari
snapshot atau rata-rata 3 bulan terakhir) beserta parameter sizing (TPS, rasio,
retensi, buffer, HA multiplier), dan sistem menghitung otomatis sisa kapasitas
dengan indikator traffic-light (Hijau/Kuning/Merah).

## Struktur File

- `app.py` — UI utama (sidebar 3 halaman: Setting, Capacity & Renewal, Login User).
- `calculator.py` — semua rumus perhitungan (murni Python, tanpa dependensi UI).
- `db.py` — lapisan persistensi: Supabase (PostgreSQL) dengan fallback otomatis ke SQLite lokal.
- `sample_data.py` — data contoh (preload) untuk demo/testing.
- `requirements.txt` — daftar dependensi.

## Database & Persistensi

Aplikasi ini menyimpan seluruh data (platform, produk, infra, storage, network,
riwayat bulanan, renewal) ke database, bukan hanya session memory. Prioritas koneksi:

1. **Supabase (PostgreSQL)** — kalau `SUPABASE_DB_URL` terisi di secrets/env var dan bisa diakses.
2. **SQLite lokal** (`local_data.db`) — fallback otomatis kalau Supabase gagal/belum dikonfigurasi.

### Setup Supabase (opsional, untuk persistensi lintas-sesi yang lebih baik)

1. Buat project gratis di [supabase.com](https://supabase.com).
2. Di dashboard Supabase, buka **Project Settings → Database** dan salin **Connection string** (mode "Session" atau "Transaction").
3. Salin `.streamlit/secrets.toml.example` menjadi `.streamlit/secrets.toml` (file ini di-gitignore, jangan di-commit), lalu isi:

   ```toml
   SUPABASE_DB_URL = "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"
   ```

4. Jalankan ulang aplikasi. Tabel (`app_state`, `users`, `activity_log`) dibuat otomatis saat pertama kali konek.
5. Cek status koneksi di sidebar menu **⚙️ Setting**.

Kalau `SUPABASE_DB_URL` tidak diisi atau gagal konek, aplikasi tetap jalan normal
dengan fallback SQLite — tidak ada error yang menghentikan aplikasi.

Untuk deploy di **Streamlit Community Cloud**, isi secret yang sama lewat
**App settings → Secrets** di dashboard Streamlit Cloud (bukan file lokal).

### Login & Log Aktivitas

- Menu **👤 Login User** di sidebar: daftar akun baru atau login dengan akun yang ada.
- Tanpa login, aksi tercatat sebagai user **Guest**.
- Menu **⚙️ Setting** menampilkan status koneksi database, daftar pengguna terdaftar,
  dan log aktivitas terakhir (siapa mengubah apa, kapan).

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
