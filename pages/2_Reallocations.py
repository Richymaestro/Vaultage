# pages/2_Reallocations.py
from datetime import datetime
from decimal import Decimal, getcontext
from typing import List, Dict, Any
import os
import json
import requests
import pandas as pd
import pytz
import streamlit as st
from hexbytes import HexBytes
from web3 import Web3

from src.chain import get_w3, checksum
from streamlit_app import VAULTS  # reuse config & market ids
from src.auth import require_login

require_login()

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
getcontext().prec = 50
TZ = pytz.timezone("Europe/Amsterdam")

st.set_page_config(page_title="Reallocations", page_icon=None, layout="wide")
st.title("Reallocations Dashboard")
st.caption("EOA → Zodiac Roles Modifier execs, gas costs (ETH & USD via Chainlink), and on-the-spot APY around each tx.")

# ---------- Styling (match main) ----------
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#0b1020 0%,#0e1426 100%);color:#e6e9ef;}
[data-testid="stSidebar"]{background:#0a0f1d;border-right:1px solid #1f2a44;}
.sidebar-link{padding:.6rem .8rem;border-radius:10px;margin-bottom:.25rem;display:block;color:#cbd5e1!important;text-decoration:none;border:1px solid transparent;}
.sidebar-link:hover{background:#111936;border-color:#26314e;}
.sidebar-link.active{background:#1a2442;border-color:#2b3a62;color:#f1f5f9!important;font-weight:600;}
.small-note{color:#9fb3d8;font-size:.85rem;}
.summary-card{width:100%;background:radial-gradient(120% 120% at 0% 0%,#122042 0%,#0e1a36 100%);border:1px solid #233257;border-radius:16px;padding:14px 16px;box-shadow:0 6px 18px rgba(0,0,0,0.25);}
.summary-card h4{margin:0 0 6px 0;color:#9fb3d8;font-size:.9rem;font-weight:600;letter-spacing:.3px;}
.summary-card .val{font-size:1.35rem;font-weight:700;color:#eaf0fb;}
[data-testid="stSidebarNav"] { display: none; }  /* hide default app/page list */
</style>
""", unsafe_allow_html=True)

# ---------- Config & routing ----------
def slugify(name: str) -> str:
    return name.lower().replace("&","and").replace("/"," ").replace("_"," ").replace("-"," ").strip().replace(" ","-")

ROUTES = {slugify(v["name"]): v for v in VAULTS}

def _normalize_slug_from_qp() -> str:
    qp = st.query_params
    if "vault" not in qp:
        return next(iter(ROUTES))  # first slug
    raw = str(qp["vault"]).strip()
    low = raw.lower()
    if low in ROUTES:
        return low
    guess = slugify(raw)
    if guess in ROUTES:
        return guess
    return next(iter(ROUTES))

current_slug = _normalize_slug_from_qp()

# Sidebar with "data" + "EOA data"
st.sidebar.title("Vaults")
def _link(label: str, href: str, active: bool):
    cls = "sidebar-link active" if active else "sidebar-link"
    st.sidebar.markdown(f'<a class="{cls}" href="{href}">{label}</a>', unsafe_allow_html=True)

for slug, Vv in ROUTES.items():
    _link(f"{Vv['name']} data", f"?vault={slug}", active=False)
    _link(f"{Vv['name']} EOA data", f"Reallocations?vault={slug}", active=(slug == current_slug))

V = ROUTES[current_slug]

vault_addr     = checksum(V["address"])
allocator_eoa  = checksum(V["allocator_eoa"])
roles_modifier = checksum(V["roles_modifier"])
morpho_addr    = checksum(V["morpho_address"])
market_ids: List[str] = [HexBytes(mid).hex() for mid in V.get("market_ids", [])]

st.subheader(V["name"])
st.caption(f"Vault: `{vault_addr}` · Allocator EOA: `{allocator_eoa}` · Roles Modifier: `{roles_modifier}`")

# ---------- Connections ----------
try:
    w3 = get_w3()
except Exception as e:
    st.error(f"Web3 error: {e}")
    st.stop()

# ---------- Minimal ABIs ----------
MORPHO_ABI = [
    {"inputs":[{"internalType":"bytes32","name":"id","type":"bytes32"}],
     "name":"idToMarketParams","outputs":[
        {"internalType":"address","name":"loanToken","type":"address"},
        {"internalType":"address","name":"collateralToken","type":"address"},
        {"internalType":"address","name":"oracle","type":"address"},
        {"internalType":"address","name":"irm","type":"address"},
        {"internalType":"uint256","name":"lltv","type":"uint256"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"bytes32","name":"id","type":"bytes32"}],
     "name":"market","outputs":[
        {"internalType":"uint128","name":"totalSupplyAssets","type":"uint128"},
        {"internalType":"uint128","name":"totalSupplyShares","type":"uint128"},
        {"internalType":"uint128","name":"totalBorrowAssets","type":"uint128"},
        {"internalType":"uint128","name":"borrowShares","type":"uint128"},
        {"internalType":"uint128","name":"lastUpdate","type":"uint128"},
        {"internalType":"uint128","name":"fee","type":"uint128"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"bytes32","name":"id","type":"bytes32"},
               {"internalType":"address","name":"account","type":"address"}],
     "name":"position","outputs":[
        {"internalType":"uint256","name":"supplyShares","type":"uint256"},
        {"internalType":"uint128","name":"borrowShares","type":"uint128"},
        {"internalType":"uint128","name":"collateral","type":"uint128"}],
     "stateMutability":"view","type":"function"},
]
ERC20_ABI = [
    {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],
     "stateMutability":"view","type":"function"}
]
IRM_ABI = [
    {"inputs":[
        {"components":[
            {"internalType":"address","name":"loanToken","type":"address"},
            {"internalType":"address","name":"collateralToken","type":"address"},
            {"internalType":"address","name":"oracle","type":"address"},
            {"internalType":"address","name":"irm","type":"address"},
            {"internalType":"uint256","name":"lltv","type":"uint256"}],
         "internalType":"struct MarketParams","name":"params","type":"tuple"},
        {"components":[
            {"internalType":"uint128","name":"totalSupplyAssets","type":"uint128"},
            {"internalType":"uint128","name":"totalSupplyShares","type":"uint128"},
            {"internalType":"uint128","name":"totalBorrowAssets","type":"uint128"},
            {"internalType":"uint128","name":"borrowShares","type":"uint128"},
            {"internalType":"uint128","name":"lastUpdate","type":"uint128"},
            {"internalType":"uint128","name":"fee","type":"uint128"}],
         "internalType":"struct Market","name":"market","type":"tuple"}],
     "name":"borrowRateView","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
     "stateMutability":"view","type":"function"}
]
# Chainlink ETH/USD AggregatorV3
AGG_ABI = [
    {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"latestRoundData","outputs":[
        {"internalType":"uint80","name":"roundId","type":"uint80"},
        {"internalType":"int256","name":"answer","type":"int256"},
        {"internalType":"uint256","name":"startedAt","type":"uint256"},
        {"internalType":"uint256","name":"updatedAt","type":"uint256"},
        {"internalType":"uint80","name":"answeredInRound","type":"uint80"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint80","name":"_roundId","type":"uint80"}],
     "name":"getRoundData","outputs":[
        {"internalType":"uint80","name":"roundId","type":"uint80"},
        {"internalType":"int256","name":"answer","type":"int256"},
        {"internalType":"uint256","name":"startedAt","type":"uint256"},
        {"internalType":"uint256","name":"updatedAt","type":"uint256"},
        {"internalType":"uint80","name":"answeredInRound","type":"uint80"}],
     "stateMutability":"view","type":"function"},
]
ETH_USD_FEED = Web3.to_checksum_address("0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419")

# ---------- Helpers ----------
def _csv_path_for_vault(vault: str) -> str:
    os.makedirs("data", exist_ok=True)
    return os.path.join("data", f"reallocations_{vault.lower()}.csv")

def _load_csv(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def _save_csv(path: str, df: pd.DataFrame) -> None:
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)

def _eth_usd_at_or_before(block_id: int) -> float:
    """Return Chainlink ETH/USD price at the given block (hardcoded 8 decimals)."""
    try:
        eth_usd = w3.eth.contract(address=ETH_USD_FEED, abi=AGG_ABI)
        rd = eth_usd.functions.latestRoundData().call(block_identifier=block_id)
        _, answer, _, _, _ = rd
        return float(answer) / (10 ** 8)  # Chainlink ETH/USD = 8 decimals
    except Exception:
        return 0.0

def _wei_to_eth(wei: int) -> float:
    return float(wei) / 1e18

WAD = Decimal(10) ** 18
SECONDS_PER_YEAR = Decimal(31_536_000)

morpho = w3.eth.contract(address=morpho_addr, abi=MORPHO_ABI)

def _dec(addr: str, block_id: int) -> int:
    return int(w3.eth.contract(address=addr, abi=ERC20_ABI).functions.decimals().call(block_identifier=block_id))

def _pos_shares(mid: str, account: str, block_id: int) -> Decimal:
    return Decimal(morpho.functions.position(HexBytes(mid), account).call(block_identifier=block_id)[0])

def _borrow_rate(irm_addr: str, params, mkt, block_id: int) -> Decimal:
    irm = w3.eth.contract(address=irm_addr, abi=IRM_ABI)
    return Decimal(irm.functions.borrowRateView(params, mkt).call(block_identifier=block_id))

def _tokens(wei_amt: Decimal, decs: int) -> Decimal:
    return Decimal(wei_amt) / (Decimal(10) ** decs)

def _exp(x: Decimal) -> Decimal:
    from decimal import localcontext
    with localcontext() as lc:
        lc.prec = max(lc.prec, 64)
        return x.exp()

def vault_apy_at_block(block_id: int, *, mids: List[str], vault: str) -> float:
    total_contrib = Decimal(0)
    total_x      = Decimal(0)
    for mid in mids:
        idp = morpho.functions.idToMarketParams(HexBytes(mid)).call(block_identifier=block_id)
        mkt = morpho.functions.market(HexBytes(mid)).call(block_identifier=block_id)
        loan, _, _, irm, _ = idp
        tsA, tsS, tbA, _, _, fee = mkt
        tsA = Decimal(tsA); tsS = Decimal(tsS); tbA = Decimal(tbA); feeWad = Decimal(fee)
        if tsA == 0 or tsS == 0:
            continue

        s_shares = _pos_shares(mid, vault, block_id)
        if s_shares == 0:
            continue

        alloc_wei = (s_shares / tsS) * tsA
        if alloc_wei <= 0:
            continue

        decs = _dec(loan, block_id)
        x_tokens = _tokens(alloc_wei, decs)
        b_tokens = _tokens(tbA, decs)
        l_base   = _tokens(tsA - alloc_wei, decs)

        if irm == ZERO_ADDRESS:
            r_per_sec = Decimal(0)
        else:
            r_per_sec = _borrow_rate(irm, idp, mkt, block_id) / WAD

        borrow_apy = _exp(r_per_sec * SECONDS_PER_YEAR) - Decimal(1)
        if borrow_apy < 0: borrow_apy = Decimal(0)

        one_minus_fee = Decimal(1) - (feeWad / WAD)
        one_minus_fee = max(Decimal(0), min(Decimal(1), one_minus_fee))

        contrib = one_minus_fee * (x_tokens * b_tokens / (l_base + x_tokens)) * borrow_apy
        total_contrib += contrib
        total_x += x_tokens
    if total_x <= 0:
        return 0.0
    return float((total_contrib / total_x) * 100)

# ---------- Etherscan v2 (paginated) ----------
EXEC_SELECTOR = Web3.keccak(
    text="execTransactionWithRole(address,uint256,bytes,uint8,bytes32,bool)"
)[:4].to_0x_hex()   # keep as-is

@st.cache_data(ttl=300)
def fetch_txs_to_all_pages(address: str) -> List[Dict[str, Any]]:
    """Fetch all normal txs via Etherscan API v2 with pagination."""
    api_key = os.getenv("ETHERSCAN_API_KEY", "")
    if not api_key:
        st.warning("No ETHERSCAN_API_KEY found in .env")
        return []

    base = "https://api.etherscan.io/v2/api"
    params = {
        "chainid": 1,
        "module": "account",
        "action": "txlist",
        "address": address,
        "sort": "asc",
        "apikey": api_key,
    }

    all_records = []
    next_token = None

    while True:
        p = dict(params)
        if next_token:
            p["page"] = next_token  # Etherscan v2 pagination token
        r = requests.get(base, params=p, timeout=30)
        r.raise_for_status()
        j = r.json()
        result = j.get("result", {})
        if isinstance(result, dict) and "records" in result:
            recs = result.get("records", [])
            all_records.extend(recs)
            next_token = result.get("nextPageToken")
            if not next_token:
                break
        elif isinstance(result, list):
            all_records.extend(result)
            break
        else:
            st.warning(f"Etherscan returned unexpected structure: {result}")
            break
    return all_records

# ---------- Load CSV (existing) ----------
csv_path = _csv_path_for_vault(vault_addr)
df_all = _load_csv(csv_path)

# Build a quick index of hashes to prevent duplicates when saving incrementally
existing_hashes = set()
if not df_all.empty and "Tx Hash" in df_all.columns:
    existing_hashes = set(str(x) for x in df_all["Tx Hash"].astype(str).tolist())

# Determine last processed block (optional optimization)
last_block_in_csv = 0
if not df_all.empty and "Block" in df_all.columns:
    try:
        last_block_in_csv = int(pd.to_numeric(df_all["Block"], errors="coerce").max())
    except Exception:
        last_block_in_csv = 0

# ---------- Fetch & filter new txs ----------
with st.spinner("Fetching allocator execs…"):
    all_txs = fetch_txs_to_all_pages(roles_modifier)

    txs = [
        t for t in all_txs
        if t.get("from", "").lower() == allocator_eoa.lower()
        and t.get("to", "").lower() == roles_modifier.lower()
        and str(t.get("input", "")).lower().startswith(EXEC_SELECTOR.lower())
        and int(t.get("blockNumber", 0)) > last_block_in_csv
    ]

# Sort ascending so we save in chronological order
txs.sort(key=lambda t: int(t.get("blockNumber", 0)))

# ---------- Incremental build & persist (row-by-row) ----------
for t in txs:
    tx_hash = t["hash"]
    if tx_hash in existing_hashes:
        continue  # already saved

    blk = int(t["blockNumber"])
    ts  = int(t["timeStamp"])
    date_utc = datetime.utcfromtimestamp(ts)

    # Gas (ETH & USD at tx block)
    try:
        rcpt = w3.eth.get_transaction_receipt(tx_hash)
        gas_used = int(rcpt["gasUsed"])
        egp = rcpt.get("effectiveGasPrice") or w3.eth.get_transaction(tx_hash).get("gasPrice", 0)
        gas_eth = _wei_to_eth(gas_used * int(egp))
    except Exception:
        gas_eth = 0.0

    eth_usd = _eth_usd_at_or_before(blk)
    gas_usd = gas_eth * eth_usd if eth_usd > 0 else 0.0

    # APY at blocks: before (blk-1) vs after (blk)
    before_block = max(0, blk - 1)
    try:
        apy_before = vault_apy_at_block(before_block, mids=market_ids, vault=vault_addr)
    except Exception:
        apy_before = 0.0
    try:
        apy_after  = vault_apy_at_block(blk, mids=market_ids, vault=vault_addr)
    except Exception:
        apy_after = 0.0

    apy_diff = apy_after - apy_before  # percentage points

    row = {
        "Date (UTC)": date_utc.strftime("%d-%m-%Y %H:%M"),
        "Tx Hash": tx_hash,
        "Block": blk,
        "Gas (ETH)": gas_eth,
        "Gas (USD)": gas_usd,
        "APY Before %": apy_before,
        "APY After %": apy_after,
        "APY Δ (pp)": apy_diff,
    }

    # Append to df_all and persist immediately
    df_all = pd.concat([df_all, pd.DataFrame([row])], ignore_index=True)
    # Keep CSV tidy & unique as we go
    df_all = df_all.drop_duplicates(subset=["Tx Hash"]).sort_values("Block", ascending=True).reset_index(drop=True)
    _save_csv(csv_path, df_all)
    existing_hashes.add(tx_hash)

# ---------- Summary (top) ----------
if df_all.empty:
    st.info("No matching execTransactionWithRole transactions found yet.")
    st.stop()
else:
    total_txs = len(df_all)
    total_gas_eth = pd.to_numeric(df_all["Gas (ETH)"], errors="coerce").fillna(0.0).sum()
    total_gas_usd = pd.to_numeric(df_all["Gas (USD)"], errors="coerce").fillna(0.0).sum()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'''
            <div class="summary-card"><h4>Total transactions</h4>
            <div class="val">{total_txs:,}</div></div>
        ''', unsafe_allow_html=True)
    with c2:
        st.markdown(f'''
            <div class="summary-card"><h4>Total gas (ETH)</h4>
            <div class="val">{total_gas_eth:,.5f}</div></div>
        ''', unsafe_allow_html=True)
    with c3:
        st.markdown(f'''
            <div class="summary-card"><h4>Total gas (USD)</h4>
            <div class="val">${total_gas_usd:,.2f}</div></div>
        ''', unsafe_allow_html=True)

# ---------- Display table (newest first) ----------
df_show = df_all.sort_values("Block", ascending=False).reset_index(drop=True)

def f5(x):
    try: return f"{float(x):,.5f}"
    except: return x

def f2(x):
    try: return f"{float(x):,.2f}"
    except: return x

st.subheader("Execs & On-the-spot APY")
df_view = pd.DataFrame({
    "Date (UTC)": df_show["Date (UTC)"],
    "Tx Hash": df_show["Tx Hash"],
    "Block": df_show["Block"],
    "Gas (ETH)": df_show["Gas (ETH)"].map(f5),   # 5 decimals
    "Gas (USD)": df_show["Gas (USD)"].map(f2),   # 2 decimals
    "APY Before %": df_show["APY Before %"].map(f2),
    "APY After %": df_show["APY After %"].map(f2),
    "APY Δ (pp)": df_show["APY Δ (pp)"].map(f2),
})
st.dataframe(df_view, use_container_width=True, hide_index=True)

st.markdown(
    f'<p class="small-note">Results cached in <code>{csv_path}</code>. '
    'USD uses Chainlink ETH/USD (0x5f4e…8419) at the tx block. '
    'APY is computed per block using market state, fee, and IRM borrowRateView across the configured markets.</p>',
    unsafe_allow_html=True
)