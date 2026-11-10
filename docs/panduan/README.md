# Panduan APEX2NEXT untuk Pengguna

APEX2NEXT membantu memindahkan aplikasi **Oracle APEX + Oracle Database** ke **Next.js + NestJS + PostgreSQL**.
Panduan ini ditulis untuk pemilik aplikasi, analis dan developer yang baru mengenal repo ini.

> **Posisi saat ini: alat bantu (toolkit), bukan konverter sekali klik.** Bagian yang bisa dibuat mekanis
> (pendataan, struktur database, pemindahan data, pemeriksaan) dikerjakan oleh alat. Bagian yang memerlukan
> keputusan manusia (logika bisnis PL/SQL, layar aplikasi) tetap dikerjakan developer, dengan panduan lengkap
> dari alat dan dengan bukti di akhir bahwa hasilnya sama dengan APEX.

## 1. Gambaran sederhana

Bayangkan pindah rumah:

| Pindah rumah | APEX2NEXT |
|---|---|
| Mendata semua barang per ruangan | **Inventaris**: semua halaman, region, item, tombol, proses dan hak akses aplikasi APEX |
| Membuat denah rumah baru yang ukurannya sama | **Rencana schema**: tabel, view, constraint Oracle diterjemahkan ke PostgreSQL |
| Mencocokkan denah dengan kondisi rumah lama yang sebenarnya | **Cek dictionary**: rencana dibandingkan dengan objek yang benar-benar terpasang di Oracle |
| Memisahkan barang yang bisa diangkut dari yang harus dibuat ulang | **Analisis PL/SQL**: mana yang mekanis, mana yang harus ditulis ulang |
| Memindahkan isi lemari dan menghitung ulang di tujuan | **Pindah data**: snapshot data dimuat dan dicek per baris (hash, jumlah, isi kolom) |
| Merakit ulang perabot custom sesuai denah | **Membangun aplikasi baru**: developer membuat halaman dan service mengikuti spesifikasi |
| Mencoba setiap ruangan sebelum serah terima | **Uji kesamaan**: alur kerja yang sama dijalankan di APEX dan di aplikasi baru, lalu hasilnya dibandingkan |

## 2. Apa yang bisa dan belum bisa (scope)

| Bagian | Status | Keterangan (angka dari pilot app 170134) |
|---|---|---|
| Membaca export APEX (format SQL, split files) | **Otomatis** | 19 halaman, 269 komponen terdata; tiap komponen punya status di matriks cakupan |
| Tabel, kolom, primary/unique/foreign key, check, index | **Otomatis** | 31 objek otomatis |
| Identity, view, kolom generated | **Dibantu** | 27 objek dikonversi lalu wajib direview (ditandai ASSISTED) |
| Package, trigger, data seed | **Manual** | 28 objek; alat memberi daftar temuan dan apa yang harus diputuskan |
| Cek rencana terhadap database Oracle asli | **Otomatis** | 12 pemeriksaan (REC-001 … REC-012) |
| Pindah data + verifikasi | **Otomatis** | sekali transaksi; tidak ada data tersimpan kalau satu pemeriksaan gagal |
| Fondasi web dan API (runtime bersama) | **Siap pakai** | paket `packages/runtime-api` dan `packages/runtime-web`: koneksi database, login akun lokal, pesan error gaya APEX, log akses, mesin laporan, form APEX, facet, grafik, kerangka halaman |
| Halaman Next.js dan API NestJS | **Manual, dipandu** | developer menulis bagian khusus aplikasi (halaman, definisi laporan, logika bisnis) di atas runtime bersama; contoh lengkap di `examples/f170134-target` |
| Uji kesamaan dengan APEX | **Manual per aplikasi** | metode dan contoh skrip tersedia (5 alur pilot identik) |
| Latihan migrasi, backup–restore, uji performa | **Contoh siap pakai** | skrip di `examples/f170134-target/rehearsal` untuk diadaptasi |
| Login | **Tersedia di runtime bersama** | akun lokal dengan ganti password wajib, kunci akun, audit |
| Interactive Grid, upload file, cetak PDF, email, REST data source, job, plug-in | **Belum didukung** | akan ditambahkan sesuai kebutuhan aplikasi nyata (lihat roadmap) |

**Yang dibutuhkan agar hasilnya bisa dipercaya:** bahan dari environment non-produksi, review oleh orang yang
paham aplikasinya, dan uji kesamaan sebelum aplikasi baru dipakai.

## 3. Siapa melakukan apa

| Peran | Tugas |
|---|---|
| Pemilik aplikasi | Menyediakan bahan, memilih alur kerja penting yang diuji, memutuskan perbedaan yang boleh diterima, tanda tangan |
| Developer | Menjalankan alat, membangun halaman dan service, menjalankan uji |
| DBA / operasional | Menyediakan salinan non-produksi, database PostgreSQL uji, backup dan server |

## 4. Bahan yang perlu disiapkan

1. **Export aplikasi APEX** dalam format SQL dengan opsi *Split into multiple files* (App Builder → Export).
   Diekstrak ke satu folder, misalnya `f216180/`.
2. **Script DDL schema**: script instalasi (Supporting Objects atau export schema) yang berisi tabel, view,
   package dan trigger aplikasi.
3. **Hasil query dictionary** (CSV) dari SQL Workshop, lihat langkah 1.
4. **Database PostgreSQL uji yang boleh dihapus** (bukan produksi).
5. **Daftar 3–5 alur kerja penting** beserta user uji per role.

Jangan memasukkan export, script, CSV data atau password ke Git. Simpan di luar folder repo.

## 5. Langkah penggunaan

Semua perintah dijalankan dari folder repo. Satu pintu masuk: `tools/apex2next`.

### Langkah 0 — Cek perangkat

```bash
tools/apex2next doctor
```

Yang wajib berstatus `[OK]`: Python 3.12+, Node, pnpm dan psycopg. Kalau ada yang kurang, ikuti
[setup](../development/setup.md).

### Langkah 1 — Ambil query untuk SQL Workshop

```bash
tools/apex2next queries --out ../kerja/queries
```

- `dictionary_inventory_apex_workshop.sql`:
  - ubah awalan nama objek di baris `with p as (select 'APX\_DEMO\_%' prefix from dual)` sesuai aplikasi Anda;
  - jalankan di **SQL Workshop → SQL Commands** sebagai schema aplikasi, lalu download hasilnya sebagai CSV;
  - query ini hanya membaca dan membutuhkan Oracle 23ai atau lebih baru.
- `example_snapshot_f170134_apex_workshop.sql` adalah contoh query snapshot data pilot. Untuk aplikasi lain, daftar
  tabel dan view-nya perlu disesuaikan oleh developer. Pembuatan otomatis query ini ada di roadmap.

### Langkah 2 — Inventaris halaman

```bash
tools/apex2next inventory ../bahan/f216180 --out ../kerja/inventory
```

Hasilnya adalah jumlah halaman dan komponen per jenis, serta `apex-page-inventory.json`. File ini menjadi daftar periksa: setiap
komponen nanti harus punya status (diimplementasikan, diadaptasi, atau tidak berlaku).

### Langkah 3 — Rencana schema PostgreSQL

```bash
tools/apex2next schema-plan ../bahan/install.sql --apex-export ../bahan/f216180/application \
  --out ../kerja/schema
```

Baca `schema-conversion-report.md` terlebih dahulu. Setiap objek diberi status:
- **AUTOMATIC**: sudah aman dipakai;
- **ASSISTED**: sudah dikonversi, tapi harus direview;
- **MANUAL**: harus ditulis tangan.

File SQL hasilnya (`0001_schema.sql`, dll.) adalah migration untuk PostgreSQL.

### Langkah 4 — Cocokkan dengan database Oracle asli

```bash
tools/apex2next dictionary-check --plan ../kerja/schema/schema-plan.json --install ../bahan/install.sql \
  --dictionary ../bahan/dictionary.csv --out ../kerja/dictionary
```

Hasil `Reconciled: True` berarti script yang dipakai sama dengan yang terpasang di Oracle. Kalau ada perbedaan
(misalnya view diubah langsung di database), laporan menunjukkan objeknya. Ambil teks yang terpasang lalu ulangi
langkah 3 dengan `--overrides`.

### Langkah 5 — Analisis PL/SQL

```bash
tools/apex2next plsql ../bahan/install.sql --out ../kerja/plsql
```

Hasilnya adalah jumlah statement dan daftar temuan, misalnya pemakaian `SYSDATE`, paket `DBMS_*`, SQL dinamis dan
`%TYPE`. Setiap temuan disertai arahan yang perlu diputuskan. Kode keluar 2 berarti ada bagian yang harus ditulis
ulang sebagai service. Daftar ini dipakai untuk memperkirakan pekerjaan developer.

### Langkah 6 — Bangun aplikasi target (developer)

Mulailah dari contoh `examples/f170134-target`:
- `apps/api` (NestJS);
- `apps/web` (Next.js);
- `db/migrations`;
- `ui/coverage.json` (matriks cakupan).

Developer membuat halaman dan service mengikuti inventaris, lalu menandai setiap komponen di matriks cakupan.
CI menolak kalau ada komponen yang belum diberi status.

### Langkah 7 — Pindahkan dan cek data

1. Jalankan query snapshot di SQL Workshop, lalu download CSV-nya.
2. Siapkan database PostgreSQL uji yang sudah berisi migration (`pnpm db:migrate` di proyek target).
3. Muat datanya:

```bash
tools/apex2next load-data ../bahan/snapshot.csv --plan ../kerja/schema/schema-plan.json \
  --database-url postgresql://user:pass@localhost:5432/db_uji --out ../kerja/data
```

`Committed: True` berarti semua pemeriksaan lulus: hash per baris, jumlah baris, isi setiap kolom, view dan
nomor identity. Kalau satu pemeriksaan gagal, **tidak ada data yang tersimpan**. Laporan menunjukkan
penyebabnya.

### Langkah 8 — Uji kesamaan dengan APEX

Untuk setiap alur kerja penting:
1. Jalankan alurnya di APEX dan catat pesan yang muncul.
2. Ambil snapshot data sebelum dan sesudahnya.
3. Jalankan alur yang sama di aplikasi baru.
4. Bandingkan pesan, isi tabel dan isi view.

Contoh lengkapnya ada di `examples/f170134-target/parity/journey.py`, dan hasilnya di
[WP9.6](../migration/wp9.6-data-parity-f170134.md).

### Langkah 9 — Latihan migrasi dan penilaian kesiapan

- **Latihan migrasi:** `examples/f170134-target/rehearsal/rehearse.py`. Isinya muat data, uji kegagalan, backup dan
  restore.
- **Uji performa:** `examples/f170134-target/rehearsal/perf.py`.
- **Penilaian 12 gate:**

```bash
tools/apex2next assess ../kerja/pilot-input.json --out ../kerja/kesiapan.json
```

Contoh isian ada di `docs/migration/wp9.7/f170134/pilot-input.json`. Hasil penilaiannya:
- `QUALIFIED`: semua gate lulus;
- `CONDITIONAL`: ada catatan yang masih harus diputuskan;
- `INCOMPLETE`: masih ada bukti yang belum ada;
- `BLOCKED`: ada gate yang gagal.

## 6. Cara membaca hasil

| Tanda | Arti | Tindakan |
|---|---|---|
| PASS / `[OK]` | Lulus dengan bukti | Lanjut |
| WARN / ASSISTED | Sudah dikerjakan, perlu review atau keputusan | Review, lalu catat keputusannya |
| MANUAL | Alat tidak mengonversi | Masuk daftar kerja developer |
| FAIL / UNSUPPORTED | Gagal atau belum didukung | Harus diselesaikan sebelum lanjut |
| NOT_VERIFIED | Bukti belum ada | Lengkapi bukti |

Prinsip repo ini: **tidak ada data atau fungsi yang hilang diam-diam**. Setiap objek harus punya status, dan
setiap klaim "sama dengan APEX" harus punya bukti.

## 7. Aturan keamanan

- Jalankan query di salinan **non-produksi** bila memungkinkan. Semua query hanya membaca.
- Database tujuan untuk uji harus **boleh dihapus**. Skrip latihan menghapus schema `app` dan `iam` di database
  yang diberikan.
- Export, script, CSV data, backup dan password **tidak boleh masuk Git**. Yang disimpan di repo hanya laporan dan
  hash.
- Password sementara akun dikirim ke email kantor pemiliknya dan kedaluwarsa dalam 72 jam.

## 8. Roadmap pengembangan

Urutan ini disusun agar setiap tahap bisa diuji terhadap hasil yang sudah terbukti (pilot 170134), sebelum
dipakai pada aplikasi nyata.

| Tahap | Tujuan | Hasil | Selesai bila |
|---|---|---|---|
| **R1 — Alat bantu** (selesai) | Satu pintu untuk alat yang sudah ada | `tools/apex2next`, panduan ini | Langkah 0–5, 7 dan 9 bisa dijalankan dari satu perintah |
| **R2 — Runtime bersama** (selesai 10 Nov 2026) | Fondasi aplikasi target tidak ditulis ulang per aplikasi | `packages/runtime-api` dan `packages/runtime-web`: form APEX, Interactive Report, facet, pesan dan error gaya APEX, hak akses tombol, cek versi data (lost update), login akun lokal | Tercapai: app 170134 berjalan di atas paket tersebut; 63 tes API, 3 tes runtime web, 12 tes e2e dan J-01…J-05 tetap lulus |
| **R3 — Generator** (sedang dikerjakan) | Mengurangi pekerjaan manual terbesar | Slice awal tersedia: registry halaman/komponen, route inventory read-only, metadata form/report, navigation/LOV/authorization fail-closed, serta SQL conversion plan berisi target SQL + findings. Query tidak dieksekusi. Belum: generator form/report yang executable, LOV query adapter, tombol/navigation behavior, snapshot query generator dan integrasi query runtime | Seluruh output R3 di-generate ulang dari export 170134 dan lulus parity + E2E; setiap fitur executable punya test dan review keamanan |
| **R4 — Aplikasi nyata pertama** (usulan: FRITS) | Menguji alat pada aplikasi yang dipakai user | Komponen yang dibutuhkan FRITS ditambahkan; pemilahan PL/SQL menjadi template service; koneksi langsung ke database non-produksi; pemindahan data bertahap untuk volume besar | Alur kerja penting FRITS identik dengan APEX; gate WP9 lulus |
| **R5 — Konverter** | Satu perintah dari export sampai aplikasi | `apex2next convert` dengan laporan "dibuat otomatis vs TODO"; template deploy (Docker, Cloudflare Tunnel); komponen lanjutan (Interactive Grid, upload, PDF, email, REST, job) sesuai kebutuhan; opsi login eksternal (Entra ID, Keycloak) | Aplikasi kedua (mis. SIPP) dikonversi dengan porsi manual yang terukur di laporan |

Target yang realistis untuk R5 tetap **konverter + daftar TODO**, bukan 100% otomatis. Logika PL/SQL yang kompleks
selalu memerlukan review manusia. Ukuran keberhasilannya adalah porsi komponen yang dibuat otomatis di matriks
cakupan, dan bukti kesamaan perilaku.

## 9. Pertanyaan umum

**Apakah aplikasi APEX lama diubah?** Tidak. Alat hanya membaca. Data uji yang dibuat saat uji kesamaan
dicatat dan diputuskan pemiliknya.

**Apakah bisa sekali klik?** Belum. Lihat roadmap R3–R5.

**Berapa lama untuk satu aplikasi?** Tergantung jumlah halaman, komponen dan PL/SQL. Langkah 2, 3 dan 5 memberi
angka untuk memperkirakannya. Belum ada patokan dari aplikasi nyata. Aplikasi pertama di tahap R4 akan
menjadi patokan itu.

**Data pribadi?** Nyatakan klasifikasi data sebelum data keluar dari Oracle. Gunakan salinan non-produksi
atau data yang sudah dianonimkan.

## 10. Istilah

| Istilah | Arti |
|---|---|
| Export APEX | File SQL berisi definisi aplikasi (halaman, komponen), bukan datanya |
| Schema | Kumpulan tabel, view dan objek database milik aplikasi |
| PL/SQL | Bahasa program di dalam Oracle (package, trigger) yang berisi logika bisnis |
| Snapshot | Salinan data pada satu titik waktu, diambil dengan satu query yang konsisten |
| Migration | Script yang membuat struktur database PostgreSQL |
| Uji kesamaan (parity) | Bukti bahwa aplikasi baru berperilaku sama dengan APEX untuk alur yang sama |
| Matriks cakupan | Daftar semua komponen APEX beserta statusnya di aplikasi baru |
| Gate | Syarat kesiapan (12 buah) yang harus lulus sebelum go-live |
