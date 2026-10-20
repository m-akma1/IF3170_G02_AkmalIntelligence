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
python -m pip install -e ".[project]"
```

3. Jalankan program dengan perintah berikut:

```sh
python -m uma_ai.main <file-test-case> --param <file-param> [--algo ga|hc|sa] [--no-server]
python -m uma_ai.main --generate <file-generator> [--param <file-param>] [--algo ga|hc|sa] [--no-server]
```

Keterangan argumen:
* `<file-test-case>`: Nama *test case* di [`data/input`](./data/input) atau *path* file JSON
* `<file-param>`: Nama file parameter di [`data/param`](./data/param) atau *path* file JSON, dengan default [`data/param/default.json`](./data/param/default.json)
* `--algo`: Algoritma yang dijalankan (`ga`, `hc`, `sa`), default `ga`. Varian *Hill Climbing* (`steepest`, `stochastic`, `sideways`, `random_restart`) diatur di `hc.variant` pada file parameter. Suhu *Simulated Annealing* (`sa.t_start`, `sa.t_end`) secara *default* dikali `v_max` (nilai paket terbesar yang muat), sehingga sebanding dengan penalti *objective function*; `sa.t_scale: "absolute"` memakai nilai apa adanya. [`data/param/sa_unscaled.json`](./data/param/sa_unscaled.json) berisi pengaturan SA awal (variant 6, suhu absolut, `alpha` 0.999)
* `--generate`: Membuat *test case* acak dari konfigurasi di [`data/generator`](./data/generator) ke `data/input`, lalu langsung menjalankannya
* `--no-server`: Menjalankan tanpa visualisasi (opsional)

3. Program sudah berjalan dan output dapat dilihat langsung di folder [`output`](./output). Jika server dijalankan, dapat dibuka di [`http://localhost:8080`](http://localhost:8080). Kunjungi situs melalui browser untuk menggunakan program.

### Eksperimen

Satu *suite* eksperimen di [`data/experiment`](./data/experiment) berisi *test case*, parameter dasar, jumlah *run*, *seed*, dan daftar eksperimen (algoritma dan *override* parameter).

```sh
python -m uma_ai.experiment <suite> [--input <file-test-case>] [--jobs N] [--only <eksperimen> ...]
```

Pilihan variable `<suite>` untuk *suite* eksperimen:
* `report`: semua varian *Hill Climbing*, *Simulated Annealing*, serta variasi jumlah generasi dan ukuran populasi GA, masing-masing 3 *run* pada `02_tc02`
* `quick`: struktur yang sama dengan ukuran kecil untuk uji cepat
* `compare`: semua algoritma dengan ukuran sedang, untuk dijalankan pada *test case* hasil *generator* (`--input`)
* `--jobs N`: menjalankan *run* secara paralel. Durasi menjadi kurang akurat, jadi gunakan 1 (*default*) untuk hasil laporan

*Run* ke-*k* memakai *seed* `seed + k - 1`. Semua varian HC (dan SA) pada *run* yang sama mulai dari *state* awal yang sama. Hasil disimpan di `output/experiments/<suite>/` (atau `<suite>_<input>/` jika `--input` dipakai):

* `<eksperiment_name>/run_<k>/initial.json`: nilai state awal (format sama dengan input)
* `<eksperiment_name>/run_<k>/final.json`: nilai state akhir
* `<eksperiment_name>/run_<k>/history.csv`: nilai objective (dan kolom lain per algoritma) per iterasi
* `<eksperiment_name>/run_<k>/summary.json`: nilai awal/akhir, durasi, iterasi, statistik algoritma, parameter
* `<eksperiment_name>/run_<k>/objective.png`: plot objective terhadap iterasi (GA: maksimum dan rata-rata populasi)
* `<eksperiment_name>/run_<k>/accept_prob.png`: (SA) plot $e^(\delta \frac{E}{T})$ terhadap iterasi
* `<eksperiment_name>/overlay.png`: semua run dalam satu plot
* `summary.csv`: satu baris per run, untuk tabel laporan

### Generator Test Case

Konfigurasi di [`data/generator`](./data/generator) mengatur truk (dimensi, kapasitas, jumlah), jumlah paket (`n_packages`) atau rasio volume (`volume_ratio`), rasio berat (`weight_ratio`), serta kelas paket. Tiap kelas memiliki distribusi ukuran, nilai atau nilai per volume, berat atau berat per volume, ETA, dan peluang *fragile*. Distribusi dapat berupa `uniform` (cukup `[min, max]`), `triangular`, `normal`, atau `lognormal`. Paket kustom dapat ditambahkan melalui `extra_packages`.

```sh
python -m uma_ai.experiment.generator <file-generator> ... [--seed N] [--out <path>]
```

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