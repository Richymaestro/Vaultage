# pages/3_Comparisons.py
from datetime import datetime, date, timedelta, time as dtime
from decimal import Decimal, getcontext
import os

import pandas as pd
import pytz
import streamlit as st
import altair as alt
from web3 import Web3

from src.auth import guard_other_pages, logout_button
from src.chain import get_w3, checksum, find_block_at_or_before_timestamp
from src.erc4626 import read_vault_snapshot

# Import your app-wide vault list for sidebar navigation (keeps menu consistent)
from src.app_config import VAULTS as APP_VAULTS

guard_other_pages()
getcontext().prec = 50
TZ = pytz.timezone("Europe/Amsterdam")

st.set_page_config(page_title="Comparisons — APYs", page_icon=None, layout="wide")

# ----------------------------
# Configure here (standalone for comparisons data)
# ----------------------------
COMPARISON_START_DATE = date(2025, 9, 1)          # inclusive
SNAPSHOT_LOCAL_TIME   = dtime(12, 0, 0)           # daily snapshot time (Europe/Amsterdam)
COMPARISON_CSV_PATH   = os.path.join("data", "apy_comparisons.csv")

# Standalone list for which vaults to compare (can differ from APP_VAULTS)
VAULTS = [
    {"name": "kpk USDC Prime",      "address": "0xe108fbc04852B5df72f9E44d7C29F47e7A993aDd", "note": "USDC"},
    {"name": "kpk USDT Yield",      "address": "0xd4e95092a8f108728c49f32A30f30556896563b5", "note": "USDT"},
    {"name": "kpk EURC Yield",      "address": "0x0c6aec603d48eBf1cECc7b247a2c3DA08b398DC1", "note": "EURC"},
    {"name": "Steakhouse USDC",     "address": "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB", "note": "USDC"},
    {"name": "Gauntlet USDC Prime", "address": "0xdd0f28e19C1780eb6396170735D45153D261490d", "note": "USDC"},
    {"name": "Smokehouse USDC",     "address": "0xBEeFFF209270748ddd194831b3fa287a5386f5bC", "note": "USDC"},
    {"name": "Steakhouse USDT",     "address": "0xbEef047a543E45807105E51A8BBEFCc5950fcfBa", "note": "USDT"},
    {"name": "Gauntlet USDT Prime", "address": "0x8CB3649114051cA5119141a34C200D65dc0Faa73", "note": "USDT"},
    {"name": "Smokehouse USDT",     "address": "0xA0804346780b4c2e3bE118ac957D1DB82F9d7484", "note": "USDT"},
    {"name": "Gauntlet EURC Core",  "address": "0x2ed10624315b74a78f11FAbedAa1A228c198aEfB", "note": "EURC"},
]

# ----------------------------
# Styling
# ----------------------------
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
  background: linear-gradient(180deg, #0b1020 0%, #0e1426 100%);
  color: #e6e9ef;
}
[data-testid="stSidebar"] { background:#0a0f1d; border-right:1px solid #1f2a44; }
[data-testid="stSidebarNav"] { display:none; }
.card {
  width: 100%;
  background: radial-gradient(120% 120% at 0% 0%, #122042 0%, #0e1a36 100%);
  border: 1px solid #233257;
  border-radius: 16px;
  padding: 14px 16px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
  margin-bottom: 10px;
}
.card h4 { margin: 0 0 6px 0; color:#9fb3d8; font-size:.9rem; font-weight:600; letter-spacing:.3px; }
.card .val { font-size:1.05rem; font-weight:700; color:#eaf0fb; }
.small-note { color:#9fb3d8; font-size:.85rem; }
.df-wrap .stDataFrame { background:#0d1832; border:1px solid #223158; border-radius:16px; }
.sidebar-link {
  padding:.6rem .8rem; border-radius:10px; margin-bottom:.25rem; display:block;
  color:#cbd5e1!important; text-decoration:none; border:1px solid transparent;
}
.sidebar-link:hover { background:#111936; border-color:#26314e; }
.sidebar-link.active { background:#1a2442; border-color:#2b3a62; color:#f1f5f9!important; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Sidebar (complete menu, consistent with other pages)
# ----------------------------
def _slug(name: str) -> str:
    return (
        name.lower()
        .replace("&", "and").replace("/", " ").replace("_", " ").replace("-", " ")
        .strip().replace(" ", "-")
    )

st.sidebar.title("Vaults")

# Home
if st.sidebar.button("🏠 Overview", use_container_width=True, key="sb-home"):
    st.switch_page("streamlit_app.py")

# Comparisons (active)
st.sidebar.markdown('<div class="sidebar-link active">📊 Comparisons</div>', unsafe_allow_html=True)

# Per-vault links (use app_config list for navigation consistency)
def _goto(page_py: str, slug: str | None = None):
    if slug is not None:
        st.session_state.vault_slug = slug
    st.switch_page(page_py)

for v in APP_VAULTS:
    s = _slug(v["name"])
    if st.sidebar.button(f"{v['name']} Vault data", use_container_width=True, key=f"sb-data-{s}"):
        _goto("pages/1_Vault.py", s)
    if st.sidebar.button(f"{v['name']} Rebalancer data", use_container_width=True, key=f"sb-eoa-{s}"):
        _goto("pages/2_Reallocations.py", s)

st.sidebar.divider()
logout_button()

# ----------------------------
# Helpers
# ----------------------------
def _to_dec(x, default=Decimal(0)) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return default

def _underlying_from(name: str, asset_symbol: str | None) -> str:
    s = (asset_symbol or "").strip()
    if s:
        return s.upper()
    nm = (name or "").lower()
    if "usdc" in nm: return "USDC"
    if "usdt" in nm: return "USDT"
    if "eurc" in nm: return "EURC"
    return ""

def _load_comparisons_csv() -> pd.DataFrame:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(COMPARISON_CSV_PATH):
        try:
            return pd.read_csv(COMPARISON_CSV_PATH)
        except Exception:
            pass
    return pd.DataFrame(columns=["date","vault_name","vault_address","underlying_token","daily_apy_pct"])

def _save_comparisons_csv(df: pd.DataFrame) -> None:
    tmp = COMPARISON_CSV_PATH + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, COMPARISON_CSV_PATH)

def _snapshot_ts_for_day(d: date) -> int:
    snap_local = datetime.combine(d, SNAPSHOT_LOCAL_TIME, tzinfo=TZ)
    return int(snap_local.astimezone(pytz.UTC).timestamp())

# ----------------------------
# Chain connection
# ----------------------------
st.header("Comparisons — Daily APYs")
st.caption(f"Start date: {COMPARISON_START_DATE.isoformat()}. Builds and maintains `data/apy_comparisons.csv` by querying vaults on-chain.")

try:
    w3 = get_w3()
except Exception as e:
    st.error(f"Web3 error: {e}")
    st.stop()

df_comp = _load_comparisons_csv()

# Track existing (date, vault_address) rows to avoid duplicates
existing_keys = set()
if not df_comp.empty:
    for _, r in df_comp[["date", "vault_address"]].dropna().iterrows():
        existing_keys.add((str(r["date"]), str(r["vault_address"]).lower()))

today_local = datetime.now(TZ).date()

# ----------------------------
# Incremental build (direct from chain)
# ----------------------------
progress = st.progress(0.0, text="Updating APYs…")

total_tasks = len(VAULTS)
done = 0

for v in VAULTS:
    name = v["name"]
    addr = checksum(v["address"])
    # Determine range to compute for this vault (based on what's already in CSV)
    df_v_existing = df_comp[df_comp["vault_address"].str.lower() == addr.lower()]
    if df_v_existing.empty:
        begin = COMPARISON_START_DATE
    else:
        try:
            last_str = str(df_v_existing["date"].max())
            last_dt  = pd.to_datetime(last_str).date()
            begin    = max(COMPARISON_START_DATE, last_dt + timedelta(days=1))
        except Exception:
            begin = COMPARISON_START_DATE

    if begin > today_local:
        done += 1
        progress.progress(done / total_tasks, text=f"{name}: up to date")
        continue

    # Fetch sequentially so we can reuse yesterday's share price
    prev_day = begin - timedelta(days=1)
    prev_sp  = None
    try:
        ts_prev  = _snapshot_ts_for_day(prev_day)
        block_prev = find_block_at_or_before_timestamp(w3, ts_prev)
        snap_prev  = read_vault_snapshot(w3, addr, block_identifier=block_prev)
        if snap_prev and snap_prev.get("share_price"):
            prev_sp = _to_dec(snap_prev["share_price"], None)
    except Exception:
        prev_sp = None  # ok

    d = begin
    while d <= today_local:
        ts = _snapshot_ts_for_day(d)
        try:
            block = find_block_at_or_before_timestamp(w3, ts)
            snap  = read_vault_snapshot(w3, addr, block_identifier=block)
        except Exception:
            d += timedelta(days=1)
            continue

        sp = _to_dec(snap.get("share_price", 0))
        asset_symbol = (snap.get("asset_symbol") or "").strip()
        underlying = _underlying_from(name, asset_symbol)

        if prev_sp and prev_sp > 0 and sp > 0:
            daily_ret = (sp - prev_sp) / prev_sp
            apy = (Decimal(1) + daily_ret) ** Decimal(365) - Decimal(1)
            daily_apy_pct = float(apy * 100)
        else:
            daily_apy_pct = 0.0

        key = (d.strftime("%Y-%m-%d"), addr.lower())
        if key not in existing_keys:
            row = {
                "date": d.strftime("%Y-%m-%d"),
                "vault_name": name,
                "vault_address": addr,
                "underlying_token": underlying,
                "daily_apy_pct": daily_apy_pct,
            }
            df_comp = pd.concat([df_comp, pd.DataFrame([row])], ignore_index=True)
            df_comp = (
                df_comp.drop_duplicates(subset=["date","vault_address"])
                       .sort_values(["underlying_token","vault_name","date"])
                       .reset_index(drop=True)
            )
            _save_comparisons_csv(df_comp)
            existing_keys.add(key)

        prev_sp = sp
        d += timedelta(days=1)

    done += 1
    progress.progress(done / total_tasks, text=f"{name}: updated")

progress.empty()

if df_comp.empty:
    st.info("No APY data yet. Ensure your RPC works and the vault addresses are valid ERC-4626.")
    st.stop()

st.markdown(
    f"<p class='small-note'>Aggregated rows: <b>{len(df_comp):,}</b>  ·  File: <code>{COMPARISON_CSV_PATH}</code></p>",
    unsafe_allow_html=True
)

# ----------------------------
# Display comparison tables & charts
# ----------------------------
df_comp["date"] = pd.to_datetime(df_comp["date"])
underlyings = sorted([
    u for u in df_comp["underlying_token"].fillna("").unique()
    if str(u).strip() != ""
])

if not underlyings:
    st.info("No underlying tokens detected yet in the aggregated data.")
    st.stop()

for u in underlyings:
    st.subheader(f"Underlying: {u}")

    df_u = df_comp[df_comp["underlying_token"] == u].copy()
    if df_u.empty:
        st.caption("No data for this token yet.")
        continue

    # Pivot table with latest date on top
    pivot = df_u.pivot_table(
        index="date", columns="vault_name", values="daily_apy_pct", aggfunc="mean"
    ).sort_index(ascending=False)   # <<< newest first
    pivot = pivot.reindex(sorted(pivot.columns), axis=1)

    # Show table (format as % with 2 decimals)
    disp = pivot.copy()
    for c in disp.columns:
        disp[c] = disp[c].map(lambda x: f"{x:.2f}%" if pd.notnull(x) else "")
    st.markdown('<div class="df-wrap">', unsafe_allow_html=True)
    st.dataframe(disp, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Long form for chart (chart will handle time on X; keep chronological order)
    long = pivot.sort_index(ascending=True).reset_index().melt(
        id_vars="date", var_name="vault_name", value_name="daily_apy_pct"
    ).dropna()
    if long.empty:
        st.caption("No chart data for this token yet.")
        continue

    chart = (
        alt.Chart(long)
        .mark_line()
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("daily_apy_pct:Q", title="Daily APY (%)"),
            color=alt.Color("vault_name:N", title="Vault"),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("vault_name:N", title="Vault"),
                alt.Tooltip("daily_apy_pct:Q", title="Daily APY (%)", format=".2f"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)

# ----------------------------
# Footer
# ----------------------------
st.markdown(
    "<p class='small-note'>This page calls each ERC-4626 vault directly at the daily snapshot block, "
    "computes APY from share-price change (annualized), and appends rows to "
    "<code>data/apy_comparisons.csv</code>. Add more vaults in the VAULTS list above.</p>",
    unsafe_allow_html=True
)