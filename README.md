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
python -m uma_ai.main <file-test-case> --param <file-param> [--no-server]
```

Keterangan argumen:
* `<file-test-case>`: Nama *test case* di [`data/input`](./data/input) atau *path* file JSON
* `<file-param>`: Nama file parameter di [`data/param`](./data/param) atau *path* file JSON, dengan default [`data/param/default.json`](./data/param/default.json)
* `--no-server`: Menjalankan tanpa visualisasi (opsional)

3. Program sudah berjalan dan output dapat dilihat langsung di folder [`output`](./output). Jika server dijalankan, dapat dibuka di [`http://localhost:8080`](http://localhost:8080). Kunjungi situs melalui browser untuk menggunakan program.

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