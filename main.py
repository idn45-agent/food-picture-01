"""food-picture-01 — entry untuk bounty make.fun "Make the best-looking food picture".

Program ini menyalin gambar ramen bergaya foto (dibuat khusus untuk kompetisi
ini) dari berkas aset `assets/entry.png` di sebelah skrip ini ke berkas
keluaran `entry.png`. Penyalinan dilakukan byte-for-byte, sehingga gambar
yang dihasilkan selalu identik pada setiap run.

Direktori keluaran dipilih dari variabel lingkungan MAKEFUN_OUTPUT_DIR bila
diatur; bila tidak, dipakai /output.
"""

import os
import shutil

ASSET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "entry.png")


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "entry.png")
    shutil.copyfile(ASSET_PATH, target)
    return target


if __name__ == "__main__":
    main()
