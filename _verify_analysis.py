# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from pathlib import Path
import sys

out_path = Path(r"C:\Users\106761\Desktop\agentic-ai-iot-analyser\_verify_report.txt")
base = Path(r"C:\Users\106761\Desktop\agentic-ai-iot-analyser\prod-info-test-files-5-days")
day_files = [
    "生産情報_2026_07_06.csv",
    "生産情報_2026_07_07.csv",
    "生産情報_2026_07_08.csv",
    "生産情報_2026_07_09.csv",
    "生産情報_2026_07_10.csv",
]

lines = []
def log(s=""):
    lines.append(str(s))

# Load all days
frames = []
for f in day_files:
    df = pd.read_csv(base / f, encoding="utf-8-sig", low_memory=False)
    df["_source"] = f
    frames.append(df)
    log(f"Loaded {f}: rows={len(df):,} cols={len(df.columns)}")

all_df = pd.concat(frames, ignore_index=True)
log(f"\nUNION total rows: {len(all_df):,}")
log(f"Columns: {list(all_df.columns)}")

# Key columns by position/name
shift_col = "昼夜勤"
hour_col = "時間帯"
judge_col = "判定"
st_col = "ST"
inout_col = "IN/OUT"
date_col = "日付"

# Strip helpers
all_df["_judge"] = all_df[judge_col].astype(str).str.strip()
# Treat 'nan' string from NaN as empty
all_df.loc[all_df[judge_col].isna(), "_judge"] = ""
all_df["_judge_blank"] = all_df["_judge"].eq("") | all_df[judge_col].isna()
# Also blank if original was whitespace-only
all_df["_hour_raw"] = all_df[hour_col].astype(str).str.strip()
all_df["_shift"] = all_df[shift_col].astype(str).str.strip()

# Sample unique values
log("\n=== Sample unique 判定 (top 30 by count) ===")
jcounts = all_df[judge_col].value_counts(dropna=False).head(30)
for k, v in jcounts.items():
    log(f"  repr={k!r} count={v:,}")

log("\n=== Sample unique 時間帯 (first 40 sorted) ===")
hours_unique = sorted(all_df["_hour_raw"].unique(), key=lambda x: (len(x), x))
log(f"  n_unique={len(hours_unique)}")
log(f"  samples: {hours_unique[:40]}")
log(f"  has '1:20': {'1:20' in set(all_df['_hour_raw'])}")
log(f"  has '01:20': {'01:20' in set(all_df['_hour_raw'])}")
# Check zero-padded vs not
has_unpadded = any(h.split(":")[0].isdigit() and len(h.split(":")[0]) == 1 for h in hours_unique if ":" in h)
has_padded = any(h.split(":")[0].isdigit() and len(h.split(":")[0]) == 2 and h.split(":")[0].startswith("0") for h in hours_unique if ":" in h)
log(f"  unpadded hour present: {has_unpadded}")
log(f"  zero-padded hour present: {has_padded}")
padded_ex = [h for h in hours_unique if ":" in h and h.split(":")[0].isdigit() and len(h.split(":")[0])==2 and h.startswith("0")][:10]
unpadded_ex = [h for h in hours_unique if ":" in h and h.split(":")[0].isdigit() and len(h.split(":")[0])==1][:10]
log(f"  padded examples: {padded_ex}")
log(f"  unpadded examples: {unpadded_ex}")

# Parse hour for sorting
def parse_hour(h):
    try:
        parts = str(h).split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return -1

all_df["_mins"] = all_df["_hour_raw"].map(parse_hour)

# 1) Per (昼夜勤, 時間帯)
g = all_df.groupby(["_shift", "_hour_raw"], dropna=False)
agg = g.agg(
    total=("_judge", "size"),
    ok=("_judge", lambda s: (s == "OK").sum()),
    ng=("_judge", lambda s: (s == "NG").sum()),
).reset_index()
agg["ok_ng_sum"] = agg["ok"] + agg["ng"]
agg["empty_judge"] = agg["total"] - agg["ok_ng_sum"]  # approx; other non OK/NG possible
# more precise empty
empty_by = all_df.groupby(["_shift", "_hour_raw"])["_judge_blank"].sum().reset_index(name="blank_judge")
agg = agg.merge(empty_by, on=["_shift", "_hour_raw"])
other = all_df[~all_df["_judge"].isin(["OK", "NG"]) & ~all_df["_judge_blank"]].groupby(["_shift", "_hour_raw"]).size().reset_index(name="other_judge")
agg = agg.merge(other, on=["_shift", "_hour_raw"], how="left").fillna({"other_judge": 0})

log("\n=== 1) Per (昼夜勤, 時間帯) summary (top by total) ===")
agg_sorted = agg.sort_values("total", ascending=False)
log(agg_sorted.head(20).to_string(index=False))

max_row = agg_sorted.iloc[0]
log(f"\nMax total hour: shift={max_row['_shift']} hour={max_row['_hour_raw']} total={max_row['total']:,} NG={max_row['ng']:,} OK={max_row['ok']:,}")

# Night vs day volume
shift_tot = all_df.groupby("_shift").size()
log(f"\nShift totals (all rows):\n{shift_tot.to_string()}")
log(f"Night > Day? {shift_tot.get('夜勤', 0) > shift_tot.get('昼勤', 0)}")

# Lunch gap 12:00-13:00 day shift
day = all_df[all_df["_shift"] == "昼勤"]
lunch = day[(day["_mins"] >= 12*60) & (day["_mins"] < 13*60)]
log(f"\nDay shift 12:00-13:00 rows: {len(lunch):,}")
if len(lunch):
    log(f"  unique hours: {sorted(lunch['_hour_raw'].unique())}")
else:
    log("  NO data in 12:00-13:00 for 昼勤")

# Claim 23:20
c2320 = agg[(agg["_hour_raw"].isin(["23:20", "23:20"])) ]
# match any shift
for h in ["23:20", "23:2"]:
    pass
rows_2320 = agg[agg["_hour_raw"] == "23:20"]
log(f"\nClaim 23:20 41561 / 6 NG:")
log(rows_2320.to_string(index=False) if len(rows_2320) else "  NO rows with 時間帯==23:20")
# also all shifts combined
sub = all_df[all_df["_hour_raw"] == "23:20"]
log(f"  ALL shifts combined 23:20: total={len(sub):,} OK={(sub['_judge']=='OK').sum():,} NG={(sub['_judge']=='NG').sum():,}")

# Claim 13:10 day 4 NG / 31507
rows_1310 = agg[(agg["_hour_raw"] == "13:10") & (agg["_shift"] == "昼勤")]
log(f"\nClaim 13:10 昼勤 4 NG / 31507:")
log(rows_1310.to_string(index=False) if len(rows_1310) else "  NO match")
sub = all_df[(all_df["_hour_raw"] == "13:10") & (all_df["_shift"] == "昼勤")]
log(f"  verify: total={len(sub):,} OK={(sub['_judge']=='OK').sum():,} NG={(sub['_judge']=='NG').sum():,}")

# Save full per-hour table
agg_out = Path(r"C:\Users\106761\Desktop\agentic-ai-iot-analyser\_verify_shift_hour.csv")
agg_sorted.to_csv(agg_out, index=False, encoding="utf-8-sig")
log(f"\nSaved full shift-hour table: {agg_out}")

# 3) Earliest 時間帯 for 夜勤 and 昼勤
log("\n=== 3) Earliest 時間帯 ===")
for shift in ["夜勤", "昼勤"]:
    sub = all_df[all_df["_shift"] == shift]
    if len(sub) == 0:
        log(f"{shift}: no data")
        continue
    earliest_overall = sub.loc[sub["_mins"].idxmin()]
    log(f"{shift} overall earliest: {earliest_overall['_hour_raw']} (mins={earliest_overall['_mins']}) on {earliest_overall.get(date_col)}")
    for f in day_files:
        s2 = sub[sub["_source"] == f]
        if len(s2) == 0:
            log(f"  {f}: no {shift}")
            continue
        e = s2.loc[s2["_mins"].idxmin()]
        # also show min unique
        umin = s2["_mins"].min()
        hours_at_min = sorted(s2.loc[s2["_mins"] == umin, "_hour_raw"].unique())
        log(f"  {f}: earliest={hours_at_min} count_at_earliest={(s2['_mins']==umin).sum():,}")

# Night start might be evening - also show min by wall clock carefully
# For night, earliest chronologically within shift might mean first time of shift start (e.g. 20:00 or 22:00)
# Report both absolute min minutes and "shift-start-like" candidates
log("\nNight shift unique hours (sorted by minutes), first 15 and last 5:")
nh = sorted(all_df.loc[all_df["_shift"]=="夜勤", "_hour_raw"].unique(), key=parse_hour)
log(f"  first15: {nh[:15]}")
log(f"  last5: {nh[-5:]}")
log("Day shift unique hours first15/last5:")
dh = sorted(all_df.loc[all_df["_shift"]=="昼勤", "_hour_raw"].unique(), key=parse_hour)
log(f"  first15: {dh[:15]}")
log(f"  last5: {dh[-5:]}")

# 4) July 6 only distinct (昼夜勤, 時間帯) chronological
log("\n=== 4) July 6 distinct (昼夜勤, 時間帯) chronological ===")
j6 = all_df[all_df["_source"] == "生産情報_2026_07_06.csv"].copy()
# Chronological: typically night may wrap; order by shift then mins is imperfect.
# Use 勤務日付軸 + hour if available, else date + mins
# Simple: sort by 日付, then mins; but night after midnight is next calendar day possibly
# User asked ordered chronologically - use parse_hour within each shift, list night then day or by actual time sequence
# Better: use 日付 + 時間帯
j6["_date_s"] = j6[date_col].astype(str)
pairs = j6.groupby(["_date_s", "_shift", "_hour_raw", "_mins"]).size().reset_index(name="n")
pairs = pairs.sort_values(["_date_s", "_mins", "_shift"])
# distinct (昼夜勤, 時間帯) preserving chrono order of first appearance
seen = []
seen_set = set()
for _, r in pairs.sort_values(["_date_s", "_mins"]).iterrows():
    key = (r["_shift"], r["_hour_raw"])
    if key not in seen_set:
        seen_set.add(key)
        seen.append((r["_date_s"], r["_shift"], r["_hour_raw"], int(r["n"])))
log(f"Distinct pairs: {len(seen)}")
for item in seen:
    log(f"  {item[0]} | {item[1]} | {item[2]} | n={item[3]:,}")

# Also list uniquely sorted by mins within shift
log("\nJuly6 by shift then hour:")
for shift in ["昼勤", "夜勤"]:
    hs = sorted(j6.loc[j6["_shift"]==shift, "_hour_raw"].unique(), key=parse_hour)
    log(f"  {shift} ({len(hs)}): {hs}")

# 5) 判定 emptiness %
blank = all_df["_judge_blank"].sum()
pct = 100.0 * blank / len(all_df)
log(f"\n=== 5) 判定 emptiness ===")
log(f"blank/null/whitespace: {blank:,} / {len(all_df):,} = {pct:.4f}%")
okn = (all_df["_judge"]=="OK").sum()
ngn = (all_df["_judge"]=="NG").sum()
log(f"OK: {okn:,} NG: {ngn:,} OK+NG: {okn+ngn:,} ({100*(okn+ngn)/len(all_df):.4f}%)")
log(f"Pattern: total huge vs OK+NG tiny? total={len(all_df):,} OK+NG={okn+ngn:,} ratio_okng={100*(okn+ngn)/len(all_df):.4f}%")

# 6) Station-hourly NG rates
log("\n=== 6) Station-hourly NG rates (ng>0) ===")
# group by date, shift, hour, ST
all_df["_date_s"] = all_df[date_col].astype(str)
# normalize date for matching 2026/07/10
st_g = all_df.groupby(["_date_s", "_shift", "_hour_raw", st_col], dropna=False).agg(
    total=("_judge", "size"),
    ok=("_judge", lambda s: (s=="OK").sum()),
    ng=("_judge", lambda s: (s=="NG").sum()),
).reset_index()
st_g["denom"] = st_g["ok"] + st_g["ng"]
st_g["ng_rate"] = np.where(st_g["denom"] > 0, st_g["ng"] / st_g["denom"] * 100, np.nan)
st_pos = st_g[st_g["ng"] > 0].copy()
st_pos = st_pos.sort_values("ng_rate", ascending=False)
log(f"Groups with ng>0: {len(st_pos):,}")
log("Top 15 by ng_rate:")
log(st_pos.head(15).to_string(index=False))

# Claim specific
claim = st_g[
    (st_g[st_col].astype(str).str.contains("12ST_洗浄チェック", na=False))
    & (st_g["_hour_raw"] == "02:20")
    & (st_g["_shift"] == "夜勤")
]
log("\nClaim 12ST_洗浄チェック 2026/07/10 night 02:20 3.74%:")
# filter date containing 07/10 or 07-10
claim10 = claim[claim["_date_s"].str.contains("07/10|07-10|2026/7/10|2026-07-10", regex=True, na=False)]
if len(claim10) == 0:
    # show all matching st/hour/shift
    log("  date filter miss; all matching ST/hour/shift:")
    log(claim.to_string(index=False) if len(claim) else "  none")
    log(f"  unique dates for this ST@02:20夜勤: {claim['_date_s'].unique().tolist() if len(claim) else []}")
else:
    log(claim10.to_string(index=False))

max_ng = st_pos.iloc[0]
log(f"\nActual max ng_rate (ng>0): {max_ng['ng_rate']:.4f}% at ST={max_ng[st_col]} date={max_ng['_date_s']} shift={max_ng['_shift']} hour={max_ng['_hour_raw']} ng={max_ng['ng']} denom={max_ng['denom']} total={max_ng['total']}")

# Top NG stations by total NG
st_tot = all_df.groupby(st_col).agg(
    total=("_judge","size"),
    ng=("_judge", lambda s: (s=="NG").sum()),
    ok=("_judge", lambda s: (s=="OK").sum()),
).reset_index()
st_tot["ng_rate"] = np.where(st_tot["ok"]+st_tot["ng"]>0, st_tot["ng"]/(st_tot["ok"]+st_tot["ng"])*100, 0)
st_tot = st_tot.sort_values("ng", ascending=False)
log("\nTop stations by NG count:")
log(st_tot.head(15).to_string(index=False))
for name in ["2ST_カシメ", "5ST_測定", "12ST_洗浄チェック"]:
    row = st_tot[st_tot[st_col].astype(str) == name]
    log(f"  Check {name}: {'FOUND' if len(row) else 'NOT FOUND'}")
    if len(row):
        log(f"    {row.to_string(index=False)}")

st_pos.to_csv(Path(r"C:\Users\106761\Desktop\agentic-ai-iot-analyser\_verify_st_hourly_ng.csv"), index=False, encoding="utf-8-sig")

# 7) IN/OUT vs OK/NG
log("\n=== 7) IN/OUT vs 判定 ===")
all_df["_inout"] = all_df[inout_col].astype(str).str.strip()
io = all_df.groupby("_inout").agg(
    total=("_judge","size"),
    ok=("_judge", lambda s: (s=="OK").sum()),
    ng=("_judge", lambda s: (s=="NG").sum()),
    blank=("_judge_blank","sum"),
).reset_index()
log(io.to_string(index=False))
ok_on_out = ((all_df["_judge"]=="OK") & (all_df["_inout"].str.upper()=="OUT")).sum()
ng_on_out = ((all_df["_judge"]=="NG") & (all_df["_inout"].str.upper()=="OUT")).sum()
ok_on_in = ((all_df["_judge"]=="OK") & (all_df["_inout"].str.upper()=="IN")).sum()
ng_on_in = ((all_df["_judge"]=="NG") & (all_df["_inout"].str.upper()=="IN")).sum()
log(f"OK on Out: {ok_on_out:,} OK on In: {ok_on_in:,}")
log(f"NG on Out: {ng_on_out:,} NG on In: {ng_on_in:,}")
log(f"OK+NG mostly on Out? {(ok_on_out+ng_on_out) > (ok_on_in+ng_on_in)} share_out={100*(ok_on_out+ng_on_out)/max(1,okn+ngn):.2f}%")

# Unique IN/OUT values
log(f"IN/OUT unique: {all_df['_inout'].value_counts(dropna=False).head(20).to_dict()}")

# 8) Pattern confirmation per hour example
log("\n=== 8) LLM SQL pattern (total incl empty vs OK+NG) ===")
# show for max hour and 23:20 and 13:10
for label, mask in [
    ("max total group", (all_df["_shift"]==max_row["_shift"]) & (all_df["_hour_raw"]==max_row["_hour_raw"])),
    ("23:20 all shifts", all_df["_hour_raw"]=="23:20"),
    ("13:10 昼勤", (all_df["_hour_raw"]=="13:10") & (all_df["_shift"]=="昼勤")),
]:
    sub = all_df[mask]
    log(f"{label}: total={len(sub):,} OK={(sub['_judge']=='OK').sum():,} NG={(sub['_judge']=='NG').sum():,} blank={sub['_judge_blank'].sum():,} OK+NG={(sub['_judge'].isin(['OK','NG'])).sum():,}")

# Also check if 判定 has trailing spaces in raw
raw_ok = all_df[judge_col].dropna()
has_space = raw_ok.astype(str).str.match(r"^.*\s+$|^(\s+).*") 
# count values where strip changes
changed = (raw_ok.astype(str) != raw_ok.astype(str).str.strip()).sum()
log(f"\n判定 values changed by strip: {changed:,} / {len(raw_ok):,}")

# Reference file note
ref = base / "生産情報_02_he.csv"
try:
    rhe = pd.read_csv(ref, encoding="utf-8-sig", nrows=5)
    log(f"\nReference file cols: {list(rhe.columns)} shape_sample rows")
except Exception as e:
    log(f"Ref read err: {e}")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"WROTE {out_path} lines={len(lines)}")
print(f"total_rows={len(all_df)}")
