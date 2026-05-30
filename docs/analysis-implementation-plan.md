# coralX — Rencana Implementasi Analisa Data

> Dokumen ini adalah panduan implementasi langkah-demi-langkah. Tiap tugas dibuat **mandiri**:
> ada tujuan, file yang disentuh, signature fungsi, rumus, titik integrasi, dan kriteria selesai.
> Dirancang agar bisa dieksekusi di VSCode oleh model AI mana pun (termasuk yang lebih murah)
> tanpa perlu keputusan arsitektur tambahan.
>
> Kerjakan **berurutan per fase**. Jangan loncat fase — fase berikutnya mengandalkan fase sebelumnya.

---

## 0. Prinsip Desain (WAJIB dibaca dulu)

coralX menyajikan analisa secara **berlapis** agar memudahkan user awam tapi tidak menghasilkan
kesimpulan menyesatkan:

- **Lapis 1 — Data mentah**: selalu tersedia (sheet `Raw Points`, `Per Image`, `Per Station`). Jangan diubah/dihapus.
- **Lapis 2 — Analisa inti**: ON otomatis. Semua user butuh (tutupan, CI, Mortality Index, kategori kesehatan, keanekaragaman).
- **Lapis 3 — Analisa lanjutan**: ON/OFF (opt-in) **dengan guardrail** — hanya boleh jalan kalau prasyarat data terpenuhi
  (cukup stasiun, desain sampling konsisten, metadata lengkap). Kalau tidak, tampilkan alasan, jangan paksa jalan.

**Aturan emas**: setiap analisa lanjutan harus memvalidasi asumsinya **sebelum** menghasilkan angka.
Lebih baik menolak menghitung + memberi alasan, daripada mengeluarkan angka yang terlihat meyakinkan tapi rapuh.

### Konvensi kode (ikuti gaya yang sudah ada)
- Python 3.10+, **type hints wajib**, gunakan `dataclass` untuk model.
- Fungsi analisa murni (pure function) diletakkan di `src/core/`, tanpa dependensi ke PyQt.
- Jangan tambah dependensi tanpa perlu. Stack inti (numpy, pandas, scipy) **sudah cukup** untuk hampir semua analisa.
- Tiap fungsi baru wajib punya docstring singkat berisi rumus & asumsi.
- Tiap fungsi baru wajib punya unit test di `tests/` (lihat bagian Testing).

### Peta file yang akan disentuh
| File | Peran |
|---|---|
| `src/core/analysis.py` | Fungsi analisa ekologi murni (tambah fungsi baru di sini) |
| `src/core/statistics.py` | Agregasi per-image / per-station / per-project |
| `src/core/exporter.py` | Penulisan sheet Excel/CSV |
| `src/core/validation.py` | **(BARU)** validasi metadata & konsistensi sampling |
| `src/core/multivariate.py` | **(BARU)** Bray-Curtis, ordinasi, PERMANOVA, SIMPER |
| `src/core/comparison.py` | **(BARU)** uji statistik antar grup + bootstrap |
| `src/models/project.py` | Model data (rujukan, jarang diubah) |
| `src/ui/main_window.py` | Menu + toggle analisa lanjutan |
| `src/ui/analysis_dialog.py` | **(BARU)** dialog pengaturan analisa lanjutan + guardrail |
| `tests/` | Unit test |

### Cara membaca data (penting untuk semua fungsi)
- Daftar label satu gambar: `[p.label for p in annotation.points if p.label]`
- Grup bentik ada di `project.coral_groups` = `[{"name": "Hard Coral", "codes": ["CB","CE",...]}, ...]`
- Resolusi grup **harus by name** dengan fallback: cari grup `name == "Hard Coral"`, `"Dead Coral"`, `"Algae"`.
  Kalau grup tak ada, fungsi mengembalikan `None` (bukan error).
- Gunakan **proporsi/persentase**, bukan hitungan mentah, saat membandingkan antar stasiun (jumlah titik bisa beda).

---

## FASE 0 — Fondasi: Validasi (prasyarat semua lapis 3)

Tujuan: memastikan analisa lanjutan tidak jalan di atas data yang tidak layak.

### Tugas 0.1 — Modul validasi metadata
**File baru:** `src/core/validation.py`

```python
from dataclasses import dataclass
from src.models.project import Project

@dataclass
class ValidationResult:
    ok: bool
    reasons: list[str]          # alasan kenapa tidak ok (kosong jika ok)
    warnings: list[str]         # peringatan non-blok

def validate_metadata_completeness(project: Project) -> dict[str, ValidationResult]:
    """
    Periksa kelengkapan metadata per kebutuhan analisa.
    Return dict dengan kunci: 'temporal', 'spatial', 'area', 'depth'.
    - 'temporal' ok jika >=2 stasiun punya field date valid (ISO-8601) dengan tanggal berbeda.
    - 'spatial'  ok jika >=3 stasiun punya GPS lat/lon valid (bukan None/0).
    - 'area'     ok jika setidaknya 1 annotation punya scale calibration (scale_factor terisi).
    - 'depth'    ok jika >=3 stasiun punya depth_m terisi (>0).
    Tiap result memuat reasons (stasiun mana yang kurang) untuk ditampilkan ke user.
    """
```

**Kriteria selesai:** fungsi mengembalikan struktur lengkap; tidak pernah melempar exception meski metadata kosong.

### Tugas 0.2 — Validasi konsistensi desain sampling
**File:** `src/core/validation.py`

```python
def validate_sampling_consistency(project: Project) -> ValidationResult:
    """
    Bandingkan desain sampling antar stasiun/gambar.
    ok = True jika:
      - semua gambar memakai point_distribution yang sama (project.point_distribution dipakai konsisten), DAN
      - jumlah titik berlabel per gambar tidak berbeda jauh (rasio max/min titik <= 2.0).
    Jika campur metode atau jumlah titik timpang -> ok=False, reasons menjelaskan.
    warnings jika ada gambar dengan titik berlabel < 25 (kurang untuk estimasi tutupan andal).
    """
```

**Catatan rumus:** jumlah titik berlabel per gambar = `len([p for p in ann.points if p.label])`.

**Kriteria selesai:** mengembalikan `ok=False` + alasan jelas saat metode dicampur atau jumlah titik timpang.

### Tugas 0.3 — Fungsi gerbang (gate) untuk Bray-Curtis & multivariat
**File:** `src/core/validation.py`

```python
def can_run_multivariate(project: Project) -> ValidationResult:
    """
    Gerbang khusus analisa multivariat (Bray-Curtis, nMDS, PERMANOVA).
    ok = True jika SEMUA terpenuhi:
      - jumlah stasiun (atau unit sampel) >= 4
      - validate_sampling_consistency(project).ok == True
    Jika tidak -> ok=False dengan reasons yang spesifik & actionable.
    """
```

**Kriteria selesai:** dipakai sebagai syarat enable tombol di UI (Fase 3 & dialog).

---

## FASE 1 — Lapis 2: Analisa Inti (ON otomatis)

Semua fungsi di sini **murni**, ditaruh di `src/core/analysis.py`, lalu di-wire ke summary & export.

### Tugas 1.1 — Mortality Index
**File:** `src/core/analysis.py`

```python
def mortality_index(labels: list[str], coral_groups: list[dict]) -> float | None:
    """
    Mortality Index (MI) = dead / (live_hard_coral + dead)
      dead = jumlah titik berkode grup 'Dead Coral' (mis. DC, DCA)
      live_hard_coral = jumlah titik berkode grup 'Hard Coral'
    Range 0..1 (semakin tinggi = semakin banyak kematian karang).
    Return None jika (live + dead) == 0 atau grup tak ditemukan.
    """
```
Gunakan helper resolusi grup by name (buat sekali, pakai ulang):
```python
def _codes_of_group(coral_groups: list[dict], group_name: str) -> set[str]:
    for g in coral_groups:
        if g.get("name", "").strip().lower() == group_name.strip().lower():
            return set(g.get("codes", []))
    return set()
```

### Tugas 1.2 — Kategori kesehatan terumbu
**File:** `src/core/analysis.py`

```python
def reef_health_category(live_coral_pct: float) -> dict:
    """
    Klasifikasi Gomez & Yap (1988) / KepMen LH No.4/2001 berdasarkan % tutupan karang keras hidup.
      0   <= x < 25   -> 'Buruk'        (Poor)
      25  <= x < 50   -> 'Sedang'       (Fair)
      50  <= x < 75   -> 'Baik'         (Good)
      75  <= x <=100  -> 'Sangat Baik'  (Excellent)
    Return {'category': str, 'category_en': str, 'live_coral_pct': float}.
    """
```
`live_coral_pct` = total tutupan(%) semua kode dalam grup 'Hard Coral' (jumlahkan dari `coverage_with_ci` atau `group_coverage`).

### Tugas 1.3 — Rasio Karang:Alga (indikator phase shift)
**File:** `src/core/analysis.py`

```python
def coral_algae_ratio(labels: list[str], coral_groups: list[dict]) -> float | None:
    """
    Rasio = live_hard_coral_pct / algae_pct.
    >1 = didominasi karang (sehat); <1 = didominasi alga (indikasi phase shift).
    Return None jika algae_pct == 0 (hindari div-by-zero) atau grup tak ada.
    """
```

### Tugas 1.4 — Indeks dominansi & Hill numbers
**File:** `src/core/analysis.py`

```python
def berger_parker_dominance(labels: list[str]) -> float:
    """d = n_max / N, proporsi kategori paling melimpah. Range 0..1."""

def hill_numbers(labels: list[str]) -> dict:
    """
    Hill numbers (effective number of species):
      q0 = richness (S)
      q1 = exp(Shannon H')
      q2 = 1 / Simpson_D  (Simpson_D = sum p_i^2)
    Return {'q0': float, 'q1': float, 'q2': float}.
    """
```
Reuse `_shannon_index` / `_simpson_index` dari `statistics.py` jika memudahkan (impor atau duplikasi rumus kecil).

### Tugas 1.5 — Wire ke summary
**File:** `src/core/statistics.py`

- Di `project_summary()` dan `station_summary()`, tambahkan kunci baru:
  `mortality_index`, `reef_health` (dict dari 1.2), `coral_algae_ratio`, `berger_parker`, `hill` (dict dari 1.4).
- `live_coral_pct` dihitung dari `group_coverage(labels, project.coral_groups)` grup 'Hard Coral'.

**Kriteria selesai:** memanggil `project_summary(project)` mengembalikan semua metrik baru tanpa error,
dan `None`/aman saat grup/labels kosong.

### Tugas 1.6 — Tambahkan ke export
**File:** `src/core/exporter.py`

- Di sheet **Summary**, tambahkan baris: Mortality Index, Kategori Kesehatan, Rasio Karang:Alga, Berger-Parker, Hill q0/q1/q2.
- Di sheet **Per Station**, tambahkan kolom yang sama per stasiun (gunakan `per_station_table` + `station_summary`).
- Jangan ubah sheet `Raw Points` / `Per Image` struktur dasarnya (boleh tambah kolom, jangan hapus).

**Kriteria selesai:** export Excel berjalan; buka file → metrik baru muncul di Summary & Per Station.

---

## FASE 2 — Statistik Perbandingan (sebagian Lapis 2, sebagian Lapis 3)

### Tugas 2.1 — Bootstrap CI untuk indeks keanekaragaman
**File baru:** `src/core/comparison.py`

```python
import numpy as np

def bootstrap_ci(labels: list[str], metric_fn, n_boot: int = 1000,
                 confidence: float = 0.95, seed: int | None = 42) -> dict:
    """
    Bootstrap percentile CI untuk metrik berbasis label (mis. Shannon, Simpson).
    metric_fn: fungsi labels->float.
    Resample labels dengan pengembalian n_boot kali, hitung metric, ambil persentil.
    Return {'value': float, 'ci_lower': float, 'ci_upper': float}.
    """
```
Pakai untuk Shannon & Simpson di summary (lapis 2). `np.random.default_rng(seed)` untuk reprodusibilitas.

### Tugas 2.2 — Uji beda antar grup (Lapis 3, opt-in)
**File:** `src/core/comparison.py`

```python
def compare_groups(values_by_group: dict[str, list[float]], method: str = "auto") -> dict:
    """
    Bandingkan suatu metrik (mis. tutupan HC per gambar) antar grup (mis. zona/stasiun).
    method:
      'anova'   -> scipy.stats.f_oneway
      'kruskal' -> scipy.stats.kruskal (non-parametrik)
      'auto'    -> kruskal jika n kecil (<10/grup) atau distribusi tak normal, selain itu anova
    Return {'method': str, 'statistic': float, 'p_value': float, 'significant': bool(p<0.05)}.
    Butuh >=2 grup, tiap grup >=2 nilai; else return {'error': alasan}.
    """
```
Semua via `scipy.stats` (sudah ada). Jangan tambah dependensi.

**Kriteria selesai:** menghasilkan p-value benar pada data uji; menolak rapi saat grup/n tidak cukup.

---

## FASE 3 — Multivariat: Bray-Curtis & Ordinasi (Lapis 3, opt-in + guardrail)

> WAJIB lewat `can_run_multivariate(project)` dulu. Jika `ok=False`, jangan hitung.

### Tugas 3.1 — Matriks komposisi & Bray-Curtis
**File baru:** `src/core/multivariate.py`

```python
import numpy as np
from scipy.spatial.distance import pdist, squareform

def composition_matrix(project, biotic_only: bool = True,
                       exclude_codes: set[str] | None = None,
                       transform: str = "none") -> tuple[list[str], list[str], np.ndarray]:
    """
    Bangun matriks komposisi: baris = unit sampel (stasiun), kolom = kode, sel = PROPORSI titik.
    - biotic_only: buang kode substrat/artefak (S, R, RK, SI, TWS, dst) -> hanya kategori biotik.
    - exclude_codes: kode tambahan yang dibuang (default {'TWS'} selalu dibuang).
    - transform: 'none' | 'sqrt' | 'fourth_root' (akar/akar-keempat menyeimbangkan kategori dominan).
    Proporsi dihitung per stasiun (jumlah titik bisa beda antar stasiun).
    Return (sample_names, code_names, matrix).
    """

def bray_curtis_matrix(matrix: np.ndarray) -> np.ndarray:
    """
    Matriks ketidaksamaan Bray-Curtis (n_sampel x n_sampel), nilai 0..1.
    Implementasi: squareform(pdist(matrix, metric='braycurtis')).
    """
```
Catatan: default `biotic_only=True` & buang `TWS` — sesuai keputusan desain agar substrat tidak mendominasi jarak.

### Tugas 3.2 — Ordinasi (PCoA tanpa dependensi baru; nMDS opsional)
**File:** `src/core/multivariate.py`

```python
def pcoa(distance_matrix: np.ndarray, n_axes: int = 2) -> dict:
    """
    Principal Coordinates Analysis (classical MDS) memakai NUMPY saja (tanpa sklearn).
    Langkah: double-centering matriks jarak kuadrat -> eigen-decomposition -> koordinat.
    Return {'coords': np.ndarray (n x n_axes), 'eigenvalues': np.ndarray,
            'variance_explained': list[float]}.
    """
```
**Keputusan dependensi:** gunakan **PCoA (numpy)** sebagai default — nol dependensi baru.
nMDS sejati (`sklearn.manifold.MDS(metric=False)`) bersifat **opsional**; jika ingin, tambahkan
`scikit-learn` ke requirements dan buat fungsi `nmds()` terpisah. Untuk awal, PCoA cukup.

### Tugas 3.3 — Clustering hierarkis
**File:** `src/core/multivariate.py`

```python
from scipy.cluster.hierarchy import linkage

def hierarchical_clusters(distance_matrix: np.ndarray, method: str = "average") -> dict:
    """
    Linkage hierarkis dari matriks Bray-Curtis (gunakan squareform->condensed).
    method 'average' (UPGMA) = standar ekologi.
    Return {'linkage': np.ndarray, 'method': str}.  (Dendrogram digambar di Fase 5.)
    """
```

### Tugas 3.4 — PERMANOVA (numpy, tanpa dependensi berat)
**File:** `src/core/multivariate.py`

```python
def permanova(distance_matrix: np.ndarray, group_labels: list[str],
              permutations: int = 999, seed: int | None = 42) -> dict:
    """
    PERMANOVA (Anderson 2001) untuk uji beda komunitas antar grup.
    Hitung pseudo-F dari sum-of-squares within/between berbasis matriks jarak,
    lalu p-value via permutasi label grup.
    Return {'pseudo_F': float, 'p_value': float, 'permutations': int, 'significant': bool}.
    Butuh >=2 grup; tiap grup >=2 sampel.
    """
```
Implementasi pseudo-F: total SS = sum semua jarak^2 / N; within SS dijumlah per grup (jarak^2 dalam grup / n_grup).
F = (SSbetween/(a-1)) / (SSwithin/(N-a)), a = jumlah grup.

### Tugas 3.5 — SIMPER (kontribusi kode terhadap perbedaan)
**File:** `src/core/multivariate.py`

```python
def simper(matrix: np.ndarray, code_names: list[str], group_labels: list[str],
           group_a: str, group_b: str) -> list[dict]:
    """
    SIMPER: dekomposisi ketidaksamaan Bray-Curtis rata-rata antar dua grup
    menjadi kontribusi tiap kode. Urutkan kode dari kontribusi terbesar.
    Return list[{'code': str, 'avg_contribution': float, 'pct_contribution': float,
                 'cumulative_pct': float}].
    """
```

### Tugas 3.6 — Export hasil multivariat
**File:** `src/core/exporter.py`
- Sheet baru **'Bray-Curtis'**: matriks ketidaksamaan (stasiun x stasiun).
- Sheet baru **'Ordination'**: koordinat PCoA + variance explained.
- Sheet baru **'PERMANOVA'**: hasil uji (jika grup didefinisikan).
- Sheet baru **'SIMPER'**: tabel kontribusi (untuk pasangan grup terpilih).
- Sheet hanya ditulis bila `can_run_multivariate().ok`; jika tidak, tulis sheet 'Multivariate' berisi satu baris alasan.

---

## FASE 4 — Analisa Temporal, Kedalaman & Spasial (Lapis 3, opt-in)

Tiap analisa hanya jalan bila validasi metadata terkait (Fase 0.1) `ok=True`.

### Tugas 4.1 — Tren temporal
**File:** `src/core/comparison.py`
```python
def temporal_trend(project, metric: str = "live_coral_pct") -> dict:
    """
    Untuk stasiun dengan beberapa survei (date berbeda), hitung deret waktu metrik
    (live_coral_pct / mortality_index / shannon). Hitung tren via regresi linear
    (scipy.stats.linregress) -> slope, p_value, arah ('naik'/'turun'/'stabil').
    Butuh validate_metadata_completeness(project)['temporal'].ok.
    Return per-stasiun {'dates': [...], 'values': [...], 'slope': float, 'p_value': float, 'trend': str}.
    """
```

### Tugas 4.2 — Gradien kedalaman
**File:** `src/core/comparison.py`
```python
def depth_gradient(project, metric: str = "live_coral_pct") -> dict:
    """
    Regresi metrik terhadap depth_m antar stasiun (linregress).
    Butuh ['depth'].ok. Return {'slope', 'r_squared', 'p_value', 'points': [(depth, value), ...]}.
    """
```

### Tugas 4.3 — Ekspor data peta (spasial)
**File:** `src/core/exporter.py`
- Sheet baru **'Map Data'**: kolom `station, lat, lon, live_coral_pct, mortality_index, reef_health`.
  Ini cukup untuk user plot di GIS/Google Earth. (Peta interaktif = Fase 5 opsional.)
- Hanya bila `['spatial'].ok`.

---

## FASE 5 — Visualisasi & Laporan (OPSIONAL, butuh dependensi baru)

> Ini menambah `matplotlib` ke `requirements.txt`. Buat **opsional**: bila matplotlib tak terpasang,
> fitur export gambar dinonaktifkan dengan pesan, sisanya tetap jalan.

### Tugas 5.1 — Modul plotting
**File baru:** `src/core/plots.py` (impor matplotlib di dalam fungsi, tangkap ImportError)
- `plot_coverage_bar(summary)` — bar tutupan per kode + error bar (CI).
- `plot_lifeform_pie(summary)` — komposisi life-form.
- `plot_ordination(pcoa_result, group_labels)` — scatter PCoA, warna per grup.
- `plot_dendrogram(linkage_result, sample_names)` — dendrogram cluster.
- `plot_temporal(trend_result)` — garis tren waktu.
Semua menyimpan PNG ke path keluaran.

### Tugas 5.2 — Laporan ringkas (opsional lanjutan)
- Susun ringkasan eksekutif (kategori kesehatan + grafik) → bisa HTML sederhana atau sheet 'Report' di Excel.

---

## Guardrail UI (mengikat Lapis 3)

### Tugas U.1 — Dialog pengaturan analisa lanjutan
**File baru:** `src/ui/analysis_dialog.py`
- Checkbox per analisa lanjutan (Bray-Curtis, PERMANOVA, Temporal, Kedalaman, Spasial, Plot).
- Saat dialog dibuka, panggil validasi Fase 0:
  - Jika prasyarat tak terpenuhi → checkbox **disabled** + tooltip berisi `reasons` (alasan spesifik).
  - Opsi Bray-Curtis: dropdown `biotic_only`, `transform (none/sqrt/fourth_root)`.
- Tombol "Jalankan & Export" memanggil exporter dengan opsi terpilih.

### Tugas U.2 — Wire ke menu utama
**File:** `src/ui/main_window.py`
- Tambah menu **"Analisa"** → "Analisa Lanjutan…" membuka dialog U.1.
- Lapis 2 tetap otomatis ikut di setiap export (tanpa toggle).

---

## Dependensi Baru (ringkasan keputusan)
| Kebutuhan | Keputusan | Alasan |
|---|---|---|
| Bray-Curtis, pdist, linkage | `scipy` (sudah ada) | tidak perlu tambah |
| PCoA / ordinasi | numpy (sudah ada) | hindari sklearn untuk inti |
| nMDS sejati | `scikit-learn` (OPSIONAL) | hanya bila benar perlu nMDS metrik=False |
| PERMANOVA/SIMPER | numpy (sudah ada) | implementasi manual |
| Visualisasi | `matplotlib` (OPSIONAL, Fase 5) | impor lazy, fitur degradasi anggun |

---

## Strategi Testing
**Folder:** `tests/` (buat bila belum ada; gunakan `pytest`).
Untuk tiap fungsi inti, buat test dengan data sintetis kecil dan **nilai harapan yang dihitung tangan**:
- `test_mortality_index`: labels diketahui → MI manual.
- `test_reef_health_category`: cek tiap batas ambang (24.9, 25, 49.9, 50, 74.9, 75).
- `test_hill_numbers`: komunitas seragam → q0=q1=q2=S.
- `test_bray_curtis`: dua stasiun identik → jarak 0; saling lepas → 1.
- `test_pcoa`: dua titik → jarak terjaga di sumbu 1.
- `test_permanova`: dua grup terpisah jelas → p kecil; grup acak → p besar.
- `test_validation`: metadata kosong → `ok=False` dengan alasan benar.

Jalankan: `pytest tests/ -q`. Target: semua hijau sebelum commit tiap fase.

---

## Urutan Pengerjaan (dampak vs usaha)
1. **Fase 1** (MI, kategori kesehatan, rasio, Hill) — dampak tinggi, usaha rendah. **Mulai dari sini.**
2. **Fase 0** (validasi) — fondasi untuk lapis 3.
3. **Fase 2** (bootstrap CI, uji beda) — naikkan rigor.
4. **Fase 3** (Bray-Curtis + ordinasi + PERMANOVA + SIMPER) — fitur penelitian utama.
5. **Fase 4** (temporal/kedalaman/spasial) — bergantung metadata.
6. **Fase 5 + U.1/U.2** (visualisasi + UI toggle) — pemoles akhir.

> Setelah tiap fase: jalankan `pytest`, pastikan export Excel masih terbuka normal, lalu commit
> dengan pesan jelas (mis. `feat(analysis): tambah Mortality Index & kategori kesehatan terumbu`).

---

## Catatan Akurasi (jangan dilanggar)
- **Selalu pakai proporsi** untuk perbandingan antar stasiun (jumlah titik bisa beda).
- **CI Wilson** hanya valid untuk sampling acak/stratified; untuk distribusi `uniform` (grid),
  beri label CI sebagai "indikatif" / non-valid. (Lihat `validate_sampling_consistency`.)
- **Bray-Curtis** default `biotic_only=True` + buang `TWS`, agar substrat tidak mendominasi jarak.
- **Multivariat** jangan pernah jalan dengan < 4 stasiun (`can_run_multivariate`).
- Fungsi harus **mengembalikan None/alasan**, bukan melempar exception, saat data tak memadai.
