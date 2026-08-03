# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from pathlib import Path

base = Path(r"C:\Users\106761\Desktop\agentic-ai-iot-analyser\prod-info-test-files-5-days")
day_files = [
    "生産情報_2026_07_06.csv",
    "生産情報_2026_07_07.csv",
    "生産情報_2026_07_08.csv",
    "生産情報_2026_07_09.csv",
    "生産情報_2026_07_10.csv",
]
ref = base / "生産情報_02_he.csv"

for enc in ["utf-8-sig", "cp932", "utf-8", "shift_jis"]:
    try:
        df_he = pd.read_csv(ref, nrows=3, encoding=enc)
        print(f"REF encoding OK: {enc}")
        print("REF cols:", list(df_he.columns)[:25])
        break
    except Exception as e:
        print(f"REF {enc} fail: {e}")

print("\n--- Day file encodings ---")
for f in day_files:
    p = base / f
    for enc in ["utf-8-sig", "cp932", "utf-8", "shift_jis"]:
        try:
            df = pd.read_csv(p, nrows=2, encoding=enc, low_memory=False)
            print(f"{f}: {enc}, ncols={len(df.columns)}")
            print("  cols:", list(df.columns)[:18])
            break
        except Exception as e:
            print(f"{f}: {enc} fail: {type(e).__name__}")
