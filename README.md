# Tugas Besar I IF3170 Inteligensi Artifisial 2026/2027

## Deskripsi

Tugas Besar I IF3170 Intelegensi Artifisial berfokus pada implementasi dan evaluasi algoritma-algoritma *local search* untuk menyelesaikan permasalahan berupa studi kasus yang relevan terhadap industri. Tugas ini berisi rancangan representasi solusi, implementasi beberapa varian algoritma *local search*, serta hasil dan analisis eksperimen.

Objektif utama program pada tugas ini bertujuan untuk membuat konfigurasi pengisian paket paling optimal untuk sebuah truk peti kemas. 

## Menjalankan Program

### Persyaratan Sistem

Pastikan program berikut sudah terpasang di sistem Anda:
* Python 3.10 atau lebih tinggi
* Pip 23.0 atau lebih tinggi

### Cara Menjalankan

1. *Clone repository*, lalu buat *virtual environment* di *root* dan aktifkan.
```sh
git clone https://github.com/m-akma1/IF3170_G02_AkmalIntelligence
cd IF3170_G02_AkmalIntelligence

python3 -m venv .venv
source .venv/bin/activate
```

2. *Install* dependensi. Pastikan versi Python dan Pip terpenuhi.
```sh
python -m pip install -e .
```
Gunakan `python -m pip install -e ".[dev]"` jika ingin sekaligus memasang `pytest` dan `ruff`. Jika folder *repository* dipindahkan, ulangi perintah ini agar *package* `uma_ai` menunjuk ke lokasi yang baru.

3. Jalankan program dengan salah satu perintah berikut (isi tepat satu: `<file-test-case>` atau `--generate`):

```sh
python -m uma_ai.main <file-test-case> [-p <file-param>] [-a ga|hc|sa] [--no-server]
python -m uma_ai.main -g <file-generator> [-p <file-param>] [-a ga|hc|sa] [--no-server]
```

Keterangan argumen:
* `<file-test-case>`: Nama *test case* di [`data/input`](./data/input) (dengan atau tanpa `.json`, mis. `02_tc02`) atau *path* file JSON
* `-g`, `--generate <file-generator>`: Membuat *test case* acak dari konfigurasi di [`data/generator`](./data/generator) (memakai `seed` di konfigurasi), menyimpannya ke `data/input/<nama>.json` (menimpa file lama), lalu langsung menjalankannya
* `-p`, `--param <file-param>`: Nama file parameter di [`data/param`](./data/param) atau *path* file JSON, default [`default`](./data/param/default.json). Lihat [File Parameter](#file-parameter)
* `-a`, `--algo`: Algoritma yang dijalankan, yaitu `ga` (*Genetic Algorithm*, default), `hc` (*Hill Climbing*), atau `sa` (*Simulated Annealing*)
* `--no-server`: Menjalankan tanpa visualisasi; program langsung selesai setelah output disimpan

4. Ringkasan hasil (nilai *objective* awal dan akhir, iterasi, durasi, statistik algoritma, pelanggaran *constraint*, jumlah paket di dalam truk, berat, dan total nilai) ditampilkan di terminal. *State* akhir disimpan ke [`output`](./output) dengan nama `<test-case>_<param>.json` untuk GA atau `<test-case>_<param>_<algo>.json` untuk HC dan SA. Tanpa `--no-server`, visualisasi 3D dapat dibuka di [`http://localhost:8080`](http://localhost:8080) (paket *fragile* berwarna merah; label, garis tepi, opasitas, dan filter *fragile* dapat diatur di panel). Tekan `Ctrl+C` untuk keluar.

### File Parameter

File di [`data/param`](./data/param) berisi parameter algoritma. Kunci yang tidak diisi memakai nilai default, sedangkan kunci yang tidak dikenal akan menghasilkan *error*. Nilai default lengkap ada di [`data/param/default.json`](./data/param/default.json).

| Bagian | Kunci |
|---|---|
| `seed` | *Seed* acak |
| `objective` | `variant` (1–6, default 3); bobot penalti `c_floating`, `c_fragile`, `c_weight`, `c_eta`; `c_support` dan `min_support` (variant 4); `c_compact` (variant 5); `adaptive` (bobot penalti naik seiring iterasi) |
| `init` | Pembuatan *state* awal: `mode` (`drop`, `density`, `ep`), `tries`, `p_in`, `weight_ratio` |
| `neighbor` | Peluang tiap jenis *neighbor* (`w_relocate`, `w_outside`, `w_rotate`, `w_switch`, `w_swap`); tujuan relokasi (`target_random`, `target_near` dalam `near_radius`, `target_ep`); `rotate_policy` (`strict`, `redrop`, `reanchor`); `swap_orient_tries`, `similar_partner`, `partner_samples`, `settle` |
| `ga` | `pop_size`, `generations`, `crossover_rate`, `mutation_rate` (`null` = 1 / jumlah paket), `shift_mutation`, `elitism`, `selection` (`roulette`, `tournament`), `tournament_k`, `eta_seed_frac`, `max_candidates` |
| `hc` | `variant` (`steepest`, `stochastic`, `sideways`, `random_restart`), `neighbors_per_step`, `max_iterations`, `max_sideways`, `max_restarts`, `restart_base` (varian yang dipakai tiap *restart*) |
| `sa` | `t_start`, `t_end`, `t_scale`, `cooling` (`geometric`, `linear`), `alpha` (`null` = dihitung dari `t_start`, `t_end`, dan `iterations`), `iterations` |

Suhu *Simulated Annealing* secara default (`t_scale: "v_max"`) dikali `v_max` (nilai paket terbesar yang muat), sehingga sebanding dengan penalti *objective function*; `t_scale: "absolute"` memakai nilai apa adanya.

File parameter yang tersedia:
* [`default`](./data/param/default.json): semua nilai default
* [`quick`](./data/param/quick.json): GA kecil (populasi 10, 5 generasi) untuk uji cepat
* [`sa_unscaled`](./data/param/sa_unscaled.json): pengaturan SA awal (variant 6, suhu absolut, `alpha` 0.999, 10.000 iterasi, *seed* 42)

### Eksperimen

Satu *suite* eksperimen di [`data/experiment`](./data/experiment) berisi *test case* (`input`), parameter dasar (`param`), jumlah *run* (`runs`), *seed*, dan daftar eksperimen (`name`, `algorithm`, `override` parameter, dan `runs` opsional per eksperimen).

```sh
python -m uma_ai.experiment <suite> [-i <file-test-case>] [-j N] [--only <eksperimen> ...]
```

Pilihan `<suite>` (atau *path* file JSON):
* `report`: semua varian *Hill Climbing*, *Simulated Annealing*, serta variasi jumlah generasi (50, 100, 200) dan ukuran populasi (25, 50, 100) GA, masing-masing 3 *run* pada `02_tc02`
* `quick`: struktur yang sama dengan ukuran kecil untuk uji cepat, pada `01_uma`
* `compare`: semua algoritma dengan ukuran sedang, default pada `03_gen_small`; gunakan `-i` untuk *test case* hasil *generator* lainnya

Keterangan argumen:
* `-i`, `--input <file-test-case>`: Mengganti *test case* milik *suite*
* `-j`, `--jobs N`: Menjalankan *run* secara paralel. Durasi menjadi kurang akurat, jadi gunakan 1 (default) untuk hasil laporan
* `--only <eksperimen> ...`: Hanya menjalankan eksperimen dengan nama tersebut, mis. `--only sa hc_steepest`

*Run* ke-*k* memakai *seed* `seed + k - 1` untuk *state* awal (dan `seed + k - 1 + 1000` untuk pencarian). Semua varian HC (dan SA) pada *run* yang sama mulai dari *state* awal yang sama. Hasil disimpan di `output/experiments/<suite>/` (atau `<suite>_<test-case>/` jika `--input` dipakai):

* `<eksperimen>/run_<k>/initial.json`: *state* awal (format sama dengan input)
* `<eksperimen>/run_<k>/final.json`: *state* akhir
* `<eksperimen>/run_<k>/history.csv`: nilai *objective* (dan kolom lain per algoritma) per iterasi
* `<eksperimen>/run_<k>/summary.json`: nilai awal/akhir, durasi, iterasi, statistik algoritma, parameter
* `<eksperimen>/run_<k>/objective.png`: plot *objective* terhadap iterasi (GA: maksimum dan rata-rata populasi)
* `<eksperimen>/run_<k>/accept_prob.png`: (SA) plot $e^{\Delta E / T}$ terhadap iterasi
* `<eksperimen>/overlay.png`: semua *run* dalam satu plot
* `summary.csv`: satu baris per *run* (termasuk *run* lama di folder yang sama), untuk tabel laporan

### Generator Test Case

```sh
python -m uma_ai.experiment.generator <file-generator> [<file-generator> ...] [-s N] [-o <path>]
```

Keterangan argumen:
* `<file-generator>`: Satu atau lebih konfigurasi di [`data/generator`](./data/generator) (`03_gen_small`, `04_gen_mixed`, `05_gen_multi`, `06_gen_heavy`) atau *path* file JSON. Hasil disimpan ke `data/input/<nama>.json`
* `-s`, `--seed N`: Mengganti *seed* pada konfigurasi
* `-o`, `--out <path>`: *Path* output kustom (hanya untuk satu konfigurasi)

Isi konfigurasi:
* `name` (default nama file), `seed`, dan `trucks` (dimensi, kapasitas, `count`)
* Jumlah paket: `n_packages` atau `volume_ratio` (total volume paket terhadap total volume truk)
* `weight_ratio`: berat paket diskalakan agar totalnya sebesar rasio ini terhadap total kapasitas
* `random_orientation`, `shuffle`, dan `extra_packages` (paket kustom dengan format input)
* `classes`: tiap kelas memiliki `share` atau `count`, ukuran (`side` atau `width`/`length`/`height`), `value` atau `value_density`, `weight` atau `weight_density`, `eta`, dan `fragile_prob`

Distribusi ditulis sebagai angka tetap, `[low, high]` (`uniform`), atau objek `{"low", "high", "dist", ...}` dengan `dist` berupa `uniform`, `triangular` (puncak `mode`), `normal` (`mu`, `sigma`), atau `lognormal` (median `mu`, `sigma` skala log). Hasil selalu dibatasi ke `[low, high]`.

## Pembagian Kerja

### 13524084 | Dzaki Ahmad Al Hussainy 

* Implementasi Genetic Algorithm
* Pembuatan Visualisasi dengan `viser`

### 13524096 | Moreno Syawali Ganda Sugita

* Implementasi Simulated Annealing
* Penulisan Laporan dengan $\LaTeX{}$

### 13524099 | Muhammad Akmal

* Implementasi Core
* Implementasi Hill Climbing

## Kredit

**IF3170 Intelegensi Artifisial**  
*Semester 1 2026/2027*

Kelompok 2: **AkmalIntelligence**
| Nama                        | NIM      | Username                                         |
|-----------------------------|----------|--------------------------------------------------|
| Dzaki Ahmad Al Hussainy     | 13524084 | [@HussainDzaki](https://github.com/HussainDzaki) |
| Moreno Syawali Ganda Sugita | 13524096 | [@DeSince29](https://github.com/DeSince29)       |
| Muhammad Akmal              | 13524099 | [@m-akma1](https://github.com/m-akma1)           |

**Program Studi Teknik Informatika**  
**Sekolah Teknik Elektro dan Informatika**  
**Institut Teknologi Bandung**