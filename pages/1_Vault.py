# pages/1_Vault.py
from datetime import datetime, timedelta
from decimal import Decimal, getcontext

import pandas as pd
import pytz
import streamlit as st
import altair as alt

from src.chain import get_w3, checksum, find_block_at_or_before_timestamp
from src.erc4626 import read_vault_snapshot
from src.fees import get_fee_amount_for_day
from src.storage import load_csv, save_csv, append_or_update_today, latest_date
from src.app_config import START_DATE, SNAPSHOT_LOCAL_TIME, VAULTS
from src.auth import require_login

require_login()

getcontext().prec = 50
TZ = pytz.timezone("Europe/Amsterdam")

st.set_page_config(page_title="Vault Data", page_icon=None, layout="wide")

# ---------- Styling (subtle, professional; matches dashboard) ----------
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
[data-testid="stSidebarNav"] { display: none; }  /* hide default app/page list */

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

/* Summary cards */
.summary-card {
  width: 100%;
  background: radial-gradient(120% 120% at 0% 0%, #122042 0%, #0e1a36 100%);
  border: 1px solid #233257;
  border-radius: 16px;
  padding: 14px 16px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}
.summary-card h4 {
  margin: 0 0 6px 0;
  color: #9fb3d8;
  font-size: .9rem;
  font-weight: 600;
  letter-spacing: .3px;
}
.summary-card .val {
  font-size: 1.35rem;
  font-weight: 700;
  color: #eaf0fb;
}

/* Dataframe container */
.block-container .element-container:has(div[data-testid="stDataFrame"]) {
  background: #0d1832;
  border: 1px solid #223158;
  border-radius: 16px;
  padding: 8px 8px 2px 8px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.18);
}

/* Caption */
.small-note {
  color: #9fb3d8;
  font-size: .85rem;
}
</style>
""", unsafe_allow_html=True)

def _slug(name: str) -> str:
    return (
        name.lower()
        .replace("&", "and")
        .replace("/", " ")
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .replace(" ", "-")
    )

# ------- Routing / selection -------
ROUTES = {_slug(v["name"]): v for v in VAULTS}

# get slug from query params (?vault=slug)
qp = st.query_params
if "vault" in qp and qp["vault"] in ROUTES:
    current_slug = qp["vault"]
else:
    current_slug = next(iter(ROUTES)) if ROUTES else None

if not current_slug:
    st.error("No vaults configured.")
    st.stop()

active_vault = ROUTES[current_slug]

# ------- Sidebar: Overview + per-vault pages (same-tab via anchors) -------
st.sidebar.title("Vaults")

def _sbar_link(label: str, href: str, active: bool = False):
    cls = "sidebar-link active" if active else "sidebar-link"
    st.sidebar.markdown(f'<a class="{cls}" href="{href}">{label}</a>', unsafe_allow_html=True)

# Overview link (root app)
_sbar_link("🏠 Overview", "?", active=False)

for v in VAULTS:
    slug = _slug(v["name"])
    _sbar_link(f"{v['name']} data", f"Vault?vault={slug}", active=(slug == current_slug))
    _sbar_link(f"{v['name']} EOA data", f"Reallocations?vault={slug}", active=False)

# ------- Header -------
st.header(f"{active_vault['name']}")
st.caption(f"Address: `{active_vault['address']}`  ·  Start date: {START_DATE}")

# ------- Web3 -------
try:
    w3 = get_w3()
except Exception as e:
    st.error(f"Web3 error: {e}")
    st.stop()

try:
    vault_addr = checksum(active_vault["address"])
except Exception as e:
    st.error(f"Invalid address for {active_vault['name']}: {e}")
    st.stop()

# ------- CSV load & incremental backfill -------
df = load_csv(vault_addr)

today_local = datetime.now(TZ).date()
start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").date()

last = latest_date(df)
if last:
    try:
        last_dt = datetime.strptime(last, "%Y-%m-%d").date()
        begin = max(start_dt, last_dt + timedelta(days=1))
    except Exception:
        begin = start_dt
else:
    begin = start_dt

# Incrementally fill from latest CSV -> today
if begin <= today_local:
    days = (today_local - begin).days + 1
    progress = st.progress(0.0, text="Updating CSV…")
    for i in range(days):
        d = begin + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")

        # Fee/event day window
        sod_local = datetime(d.year, d.month, d.day, tzinfo=TZ)
        eod_local = sod_local + timedelta(days=1, seconds=-1)
        since_ts = int(sod_local.astimezone(pytz.UTC).timestamp())
        until_ts = int(eod_local.astimezone(pytz.UTC).timestamp())

        # Consistent snapshot time each day
        snap_local = datetime.combine(d, SNAPSHOT_LOCAL_TIME, tzinfo=TZ)
        snap_ts = int(snap_local.astimezone(pytz.UTC).timestamp())

        # Historical block
        try:
            block_id = find_block_at_or_before_timestamp(w3, snap_ts)
        except Exception as e:
            st.warning(f"{date_str}: failed to map timestamp to block → {e}")
            continue

        # Snapshot at that block
        try:
            snap = read_vault_snapshot(w3, vault_addr, block_identifier=block_id)
        except Exception as e:
            st.warning(f"{date_str}: snapshot failed at block {block_id} → {e}")
            continue

        asset_symbol = snap["asset_symbol"] or "ASSET"
        total_assets = snap["total_assets"]
        share_price = snap["share_price"]
        total_supply = snap["total_supply"]

        fee_amount = get_fee_amount_for_day(
            w3=w3, vault_addr=vault_addr, since_ts=since_ts, until_ts=until_ts
        )

        # Compute APY / yield vs previous stored row
        apy = Decimal(0)
        yield_earned = Decimal(0)
        if not df.empty and (df["date"] < date_str).any():
            prev = df.sort_values("date")[df["date"] < date_str].iloc[-1]
            prev_sp = Decimal(str(prev["share_price"])) if pd.notna(prev["share_price"]) else Decimal(0)
            if prev_sp > 0 and share_price > 0:
                daily_ret = (share_price - prev_sp) / prev_sp
                apy = (Decimal(1) + daily_ret) ** Decimal(365) - Decimal(1)
                yield_earned = (share_price - prev_sp) * total_supply

        # Upsert CSV row & persist incrementally
        df = append_or_update_today(
            df,
            date_str=date_str,
            total_assets=total_assets,
            share_price=share_price,
            fee_amount=fee_amount,
            apy=apy,
            yield_earned=yield_earned,
            asset_symbol=asset_symbol,
            vault_address=vault_addr,
            markets=active_vault.get("markets", []),
        )
        save_csv(vault_addr, df)
        progress.progress((i + 1) / days, text=f"Updating CSV… {date_str} (block {block_id})")
    progress.empty()

# ------- Helpers -------
def _to_dec(x, default=Decimal(0)):
    try:
        return Decimal(str(x))
    except Exception:
        return default

# ------- SUMMARY (TOP; laid out side-by-side) -------
if df.empty:
    st.info("No data yet. Check your START_DATE and RPC; the app will populate incrementally.")
else:
    df_sorted = df.sort_values("date").reset_index(drop=True)

    # First/last valid share price
    sp_series = pd.to_numeric(df_sorted["share_price"], errors="coerce").dropna()
    if len(sp_series) >= 2:
        sp0 = Decimal(str(sp_series.iloc[0]))
        spN = Decimal(str(sp_series.iloc[-1]))
    else:
        sp0 = Decimal(0)
        spN = Decimal(0)

    # Dates for annualization
    first_date = pd.to_datetime(df_sorted["date"].iloc[0]).date()
    last_date  = pd.to_datetime(df_sorted["date"].iloc[-1]).date()
    elapsed_days = (last_date - first_date).days

    # Annualized APY (since start): ((SP_last / SP_first) ** (365/days)) - 1
    if sp0 > 0 and elapsed_days > 0:
        total_ratio = (spN / sp0)
        ann_apy = (total_ratio ** (Decimal(365) / Decimal(elapsed_days))) - Decimal(1)
        ann_apy_pct = ann_apy * 100
    else:
        ann_apy_pct = Decimal(0)

    total_yield_cum = df_sorted["yield_earned"].apply(_to_dec).sum()
    latest_row = df_sorted.iloc[-1]
    latest_assets = _to_dec(latest_row["total_assets"])
    latest_sp = _to_dec(latest_row["share_price"])
    asset_symbol = latest_row.get("asset_symbol", "")

    # Summary cards laid out side-by-side
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'''
            <div class="summary-card"><h4>Annualized APY (since start)</h4>
            <div class="val">{ann_apy_pct:.2f}%</div></div>
        ''', unsafe_allow_html=True)
    with c2:
        st.markdown(f'''
            <div class="summary-card"><h4>Total Yield</h4>
            <div class="val">{total_yield_cum:,.2f} {asset_symbol}</div></div>
        ''', unsafe_allow_html=True)
    with c3:
        st.markdown(f'''
            <div class="summary-card"><h4>Latest Total Assets</h4>
            <div class="val">{latest_assets:,.2f} {asset_symbol}</div></div>
        ''', unsafe_allow_html=True)
    with c4:
        st.markdown(f'''
            <div class="summary-card"><h4>Latest Share Price</h4>
            <div class="val">{latest_sp:.4f}</div></div>
        ''', unsafe_allow_html=True)

    # ------- CHARTS BELOW SUMMARY -------
    st.subheader("Charts")

    df_plot = df_sorted.copy()
    df_plot["Date"] = pd.to_datetime(df_plot["date"])

    # Left axis: cumulative total yield over time (float)
    df_plot["cum_yield"] = pd.to_numeric(df_plot["yield_earned"], errors="coerce").fillna(0.0).cumsum().astype(float)

    # Right axis: DAILY APY from CSV, as percentage (float)
    df_plot["daily_apy_pct"] = (pd.to_numeric(df_plot["apy"], errors="coerce").fillna(0.0) * 100.0).astype(float)

    # Assets chart (simple line)
    df_plot["total_assets_float"] = pd.to_numeric(df_plot["total_assets"], errors="coerce").astype(float)
    chart_assets = (
        alt.Chart(df_plot)
        .mark_line()
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("total_assets_float:Q", title=f"Total Assets ({asset_symbol})"),
            tooltip=[
                alt.Tooltip("Date:T"),
                alt.Tooltip("total_assets_float:Q", title="Total Assets", format=",.2f")
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart_assets, use_container_width=True)

    # Dual-axis: cumulative total yield (left) & DAILY APY % (right)
    color_yield = "#3B82F6"     # bright blue
    color_apy   = "#1E40AF"     # darker blue

    left = (
        alt.Chart(df_plot)
        .mark_line(stroke=color_yield, strokeWidth=2)
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y(
                "cum_yield:Q",
                title=f"Total Yield ({asset_symbol})",
                axis=alt.Axis(grid=True, titleColor=color_yield),
            ),
            tooltip=[
                alt.Tooltip("Date:T"),
                alt.Tooltip("cum_yield:Q", title="Total Yield", format=",.2f"),
            ],
        )
    )

    right = (
        alt.Chart(df_plot)
        .mark_line(stroke=color_apy, strokeDash=[4, 2], strokeWidth=2)
        .encode(
            x="Date:T",
            y=alt.Y(
                "daily_apy_pct:Q",
                title="Daily APY (%)",
                axis=alt.Axis(orient="right", titleColor=color_apy),
            ),
            tooltip=[
                alt.Tooltip("Date:T"),
                alt.Tooltip("daily_apy_pct:Q", title="Daily APY (%)", format=",.2f"),
            ],
        )
    )

    chart_dual = (
        alt.layer(left, right)
        .resolve_scale(y="independent")
        .properties(
            height=340,
            title=alt.TitleParams(
                text=f"Total Yield ({color_yield}) and Daily APY ({color_apy}) over Time",
                color="#E5E7EB",
                fontSize=14,
                anchor="start",
                subtitle=["Blue line = Total Yield  |  Dark blue dashed line = Daily APY"],
                subtitleColor="#9FB3D8",
                subtitleFontSize=12,
            ),
        )
    )

    st.altair_chart(chart_dual, use_container_width=True)

# ------- TABLE (formatted & clean) -------
st.subheader("Daily metrics")

if not df.empty:
    df_disp = df.sort_values("date", ascending=False).reset_index(drop=True)

    # Build a formatted view DataFrame (no vault/markets columns)
    df_view = pd.DataFrame()
    df_view["Date"] = pd.to_datetime(df_disp["date"]).dt.strftime("%d-%m-%Y")
    df_view["Total Assets"]  = df_disp.apply(lambda r: f"{_to_dec(r['total_assets']):,.2f}", axis=1)
    df_view["Share Price"]   = df_disp.apply(lambda r: f"{_to_dec(r['share_price']):.4f}", axis=1)
    df_view["Fee"]           = df_disp.apply(lambda r: f"{_to_dec(r['fee_amount']):.2f}", axis=1)
    df_view["APY"]           = df_disp.apply(lambda r: f"{(_to_dec(r['apy']) * 100):.2f}", axis=1)
    df_view["Yield Earned"]  = df_disp.apply(lambda r: f"{_to_dec(r['yield_earned']):,.2f}", axis=1)

    st.dataframe(df_view, use_container_width=True, hide_index=True)

st.markdown(
    '<p class="small-note">CSV is stored per-vault in <code>data/</code>. '
    'The app resumes from the latest stored date to today on refresh. '
    'Dates are shown as DD-MM-YYYY; CSV keeps ISO for sorting.</p>',
    unsafe_allow_html=True
)