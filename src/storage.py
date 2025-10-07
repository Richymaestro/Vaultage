import os
from decimal import Decimal
from typing import List, Optional
import pandas as pd

DATA_DIR = "data"

COLUMNS = [
    "date",
    "total_assets",
    "share_price",
    "fee_amount",
    "apy",
    "yield_earned",
    "asset_symbol",
    "vault_address",
    "markets",
]

def _csv_path(vault_address: str) -> str:
    safe = vault_address.lower()
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"vault_{safe}.csv")

def load_csv(vault_address: str) -> pd.DataFrame:
    path = _csv_path(vault_address)
    if os.path.exists(path):
        df = pd.read_csv(path)
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = None
        return df[COLUMNS]
    return pd.DataFrame(columns=COLUMNS)

def save_csv(vault_address: str, df: pd.DataFrame):
    path = _csv_path(vault_address)
    df.sort_values("date", inplace=True)
    df.to_csv(path, index=False)

def append_or_update_today(
    df: pd.DataFrame,
    *,
    date_str: str,
    total_assets: Decimal,
    share_price: Decimal,
    fee_amount: Decimal,
    apy: Decimal,
    yield_earned: Decimal,
    asset_symbol: str,
    vault_address: str,
    markets: List[str],
) -> pd.DataFrame:
    row = {
        "date": date_str,
        "total_assets": float(total_assets),
        "share_price": float(share_price),
        "fee_amount": float(fee_amount),
        "apy": float(apy),
        "yield_earned": float(yield_earned),
        "asset_symbol": asset_symbol,
        "vault_address": vault_address,
        "markets": ",".join([m.strip() for m in markets if m.strip()]),
    }
    if (df["date"] == date_str).any():
        df.loc[df["date"] == date_str, :] = row
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df

def latest_date(df: pd.DataFrame) -> Optional[str]:
    if df.empty:
        return None
    try:
        return df["date"].max()
    except Exception:
        return None