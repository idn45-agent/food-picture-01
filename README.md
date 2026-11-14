# food-picture-01

Entry untuk bounty make.fun "Make the best-looking food picture".

Gambarnya adalah foto ramen bergaya fotografi yang dibuat dengan AI khusus
untuk kompetisi ini — semangkuk ramen dengan kuah kaya, mie, telur, dan
taburan di atasnya, tersimpan sebagai `assets/entry.png` (PNG 1024×1024).

Program `main.py` menyalin berkas aset itu byte-for-byte ke berkas keluaran
`entry.png`, sehingga hasilnya selalu identik pada setiap run.

## Jalankan

```sh
python3 main.py
```

Secara bawaan keluaran ditulis ke `/output/entry.png`. Untuk menulis ke
direktori lain, atur variabel lingkungan `MAKEFUN_OUTPUT_DIR`:

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Hanya butuh Python 3 dengan pustaka standar — tanpa dependensi tambahan dan
tanpa akses jaringan.
