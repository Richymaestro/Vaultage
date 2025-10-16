# streamlit_app.py  — Dashboard / Start page (with EOA summaries)
from datetime import datetime
from decimal import Decimal, getcontext
import os

import pandas as pd
import pytz
import streamlit as st

from src.storage import load_csv
from src.chain import checksum
from src.app_config import START_DATE, SNAPSHOT_LOCAL_TIME, VAULTS
from src.auth import require_login_on_home, logout_button

require_login_on_home()

getcontext().prec = 50
TZ = pytz.timezone("Europe/Amsterdam")

st.set_page_config(page_title="Morpho Vault Daily", page_icon=None, layout="wide")

# ---------- Styling (subtle, professional) ----------
st.markdown("""
<style>
/* Global */
[data-testid="stAppViewContainer"] {
  background: linear-gradient(180deg, #0b1020 0%, #0e1426 100%);
  color: #e6e9ef;
}
section.main > div { padding-top: 0.25rem; }
h1, h2, h3, h4 { color: #e6e9ef; }

/* Sidebar */
[data-testid="stSidebar"] {
  background: #0a0f1d;
  border-right: 1px solid #1f2a44;
}
.sidebar-link {
  padding: .6rem .8rem;
  border-radius: 10px;
  margin-bottom: .25rem;
  display: block;
  color: #cbd5e1 !important;
  text-decoration: none;
  border: 1px solid transparent;
}
.sidebar-link:hover {
  background: #111936;
  border-color: #26314e;
}
.sidebar-link.active {
  background: #1a2442;
  border-color: #2b3a62;
  color: #f1f5f9 !important;
  font-weight: 600;
}
[data-testid="stSidebarNav"] { display: none; }  /* hide default app/page list */

/* Cards */
.card {
  width: 100%;
  background: radial-gradient(120% 120% at 0% 0%, #122042 0%, #0e1a36 100%);
  border: 1px solid #233257;
  border-radius: 16px;
  padding: 14px 16px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
  margin-bottom: 10px;
}
.card h4 {
  margin: 0 0 6px 0;
  color: #9fb3d8;
  font-size: .9rem;
  font-weight: 600;
  letter-spacing: .3px;
}
.card .val {
  font-size: 1.05rem;
  font-weight: 700;
  color: #eaf0fb;
}
.card .sep { margin: 8px 0; border-top: 1px solid #223158; }

/* Caption */
.small-note {
  color: #9fb3d8;
  font-size: .85rem;
}
</style>
""", unsafe_allow_html=True)

# ---------- Helpers ----------
def slugify(name: str) -> str:
    return (
        name.lower()
        .replace("&", "and")
        .replace("/", " ")
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .replace(" ", "-")
    )

def _to_dec(x, default=Decimal(0)):
    try:
        return Decimal(str(x))
    except Exception:
        return default

def _realloc_csv_path(vault_addr_checksum: str) -> str:
    os.makedirs("data", exist_ok=True)
    return os.path.join("data", f"reallocations_{vault_addr_checksum.lower()}.csv")

def _load_realloc_csv(vaddr_cs: str) -> pd.DataFrame:
    path = _realloc_csv_path(vaddr_cs)
    if os.path.exists(path):
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def _summary_for_vault(v):
    """Return dict with summary metrics for dashboard cards, incl. EOA summary."""
    try:
        addr = checksum(v["address"])
    except Exception:
        addr = v["address"]

    df = load_csv(addr)
    if df.empty:
        ann_apy_pct = Decimal(0)
        latest_assets = Decimal(0)
        asset_symbol = ""
        latest_sp = Decimal(0)
        total_yield_cum = Decimal(0)
    else:
        df_sorted = df.sort_values("date").reset_index(drop=True)
        sp_series = pd.to_numeric(df_sorted["share_price"], errors="coerce").dropna()
        if len(sp_series) >= 2:
            sp0 = _to_dec(sp_series.iloc[0])
            spN = _to_dec(sp_series.iloc[-1])
            d0 = pd.to_datetime(df_sorted["date"].iloc[0]).date()
            dN = pd.to_datetime(df_sorted["date"].iloc[-1]).date()
            days = (dN - d0).days
            if sp0 > 0 and days > 0:
                ratio = spN / sp0
                ann_apy = (ratio ** (Decimal(365) / Decimal(days))) - Decimal(1)
                ann_apy_pct = ann_apy * 100
            else:
                ann_apy_pct = Decimal(0)
        else:
            ann_apy_pct = Decimal(0)

        latest = df_sorted.iloc[-1]
        latest_assets = _to_dec(latest["total_assets"])
        asset_symbol  = latest.get("asset_symbol", "")
        latest_sp     = _to_dec(latest["share_price"])
        total_yield_cum = df_sorted["yield_earned"].apply(_to_dec).sum()

    try:
        vaddr_cs = checksum(v["address"])
    except Exception:
        vaddr_cs = v["address"]

    df_r = _load_realloc_csv(vaddr_cs)
    if df_r.empty:
        eoa_txs = 0
        eoa_gas_eth = Decimal(0)
        eoa_gas_usd = Decimal(0)
    else:
        eoa_txs = len(df_r)
        eoa_gas_eth = _to_dec(pd.to_numeric(df_r["Gas (ETH)"], errors="coerce").fillna(0.0).sum())
        eoa_gas_usd = _to_dec(pd.to_numeric(df_r["Gas (USD)"], errors="coerce").fillna(0.0).sum())

    return {
        "name": v["name"],
        "asset_symbol": asset_symbol,
        "assets": latest_assets,
        "sp": latest_sp,
        "yield": total_yield_cum,
        "ann_apy_pct": ann_apy_pct,
        "eoa_txs": eoa_txs,
        "eoa_gas_eth": eoa_gas_eth,
        "eoa_gas_usd": eoa_gas_usd,
    }

# ---------- Sidebar: buttons that keep session (no anchor links) ----------
ROUTES = {slugify(v["name"]): v for v in VAULTS}
st.sidebar.title("Vaults")

def _goto(page_py: str, slug: str | None = None):
    if slug is not None:
        st.session_state.vault_slug = slug
    st.switch_page(page_py)

# Home (you are here)
st.sidebar.markdown('<div class="sidebar-link active">🏠 Overview</div>', unsafe_allow_html=True)

# Comparisons page button (uses switch_page)
if st.sidebar.button("📊 Comparisons", use_container_width=True, key="sb-comparisons"):
    _goto("pages/3_Comparisons.py")

# Per-vault buttons
for v in VAULTS:
    slug = slugify(v["name"])
    if st.sidebar.button(f"{v['name']} vault data", use_container_width=True, key=f"sb-data-{slug}"):
        _goto("pages/1_Vault.py", slug)
    if st.sidebar.button(f"{v['name']} rebalancer data", use_container_width=True, key=f"sb-eoa-{slug}"):
        _goto("pages/2_Reallocations.py", slug)

st.sidebar.divider()
logout_button()

# ---------- Page header ----------
st.header("Morpho Vaults — Overview")
st.caption(f"Start date (per-vault CSV): {START_DATE}. Select a vault from the sidebar or use the buttons below.")

# ---------- Summaries grid (incl. EOA summary) ----------
N = len(VAULTS)
if N == 0:
    st.info("No vaults configured.")
else:
    cols = st.columns(3)  # 3-up grid
    for i, v in enumerate(VAULTS):
        s = _summary_for_vault(v)
        with cols[i % 3]:
            st.markdown(f"""
            <div class="card">
              <h4>{s['name']}</h4>
              <div class="val">Annualized APY: {s['ann_apy_pct']:.2f}%</div>
              <div class="val">Total Yield: {s['yield']:,.2f} {s['asset_symbol']}</div>
              <div class="val">Total Assets: {s['assets']:,.2f} {s['asset_symbol']}</div>
              <div class="val">Share Price: {s['sp']:.4f}</div>
              <div class="sep"></div>
              <div class="val">EOA txs: {s['eoa_txs']:,}</div>
              <div class="val">EOA gas: {s['eoa_gas_eth']:.5f} ETH · ${s['eoa_gas_usd']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)

            slug = slugify(v["name"])
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Open data →", key=f"card-data-{slug}", use_container_width=True):
                    _goto("pages/1_Vault.py", slug)
            with b2:
                if st.button("Open EOA data →", key=f"card-eoa-{slug}", use_container_width=True):
                    _goto("pages/2_Reallocations.py", slug)

st.markdown(
    '<p class="small-note">Overview reads per-vault CSVs in <code>data/</code> and the EOA CSVs '
    '(e.g. <code>reallocations_&lt;vaultaddr&gt;.csv</code>) to show the latest summaries.</p>',
    unsafe_allow_html=True
)