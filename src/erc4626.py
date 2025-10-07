from decimal import Decimal, getcontext
from web3 import Web3

getcontext().prec = 50

ERC20_ABI = [
    {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]

ERC4626_MIN_ABI = [
    {"inputs":[],"name":"totalAssets","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"asset","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
]

def contract(w3: Web3, address: str, abi):
    return w3.eth.contract(address=address, abi=abi)

def _decimals(w3: Web3, token_addr: str, block_identifier=None) -> int:
    c = contract(w3, token_addr, ERC20_ABI)
    return c.functions.decimals().call(block_identifier=block_identifier)

def _symbol(w3: Web3, token_addr: str, block_identifier=None) -> str:
    c = contract(w3, token_addr, ERC20_ABI)
    try:
        return c.functions.symbol().call(block_identifier=block_identifier)
    except Exception:
        return ""

def read_vault_snapshot(w3: Web3, vault_addr: str, block_identifier=None):
    """
    Read an ERC-4626 snapshot at a specific historical block (or 'latest').

    Returns dict with: asset, asset_decimals, asset_symbol, total_assets(_raw),
    total_supply(_raw), share_price, vault_decimals.
    """
    v = contract(w3, vault_addr, ERC4626_MIN_ABI)

    asset_addr = v.functions.asset().call(block_identifier=block_identifier)
    asset_dec = _decimals(w3, asset_addr, block_identifier=block_identifier)
    asset_sym = _symbol(w3, asset_addr, block_identifier=block_identifier)

    total_assets_raw = v.functions.totalAssets().call(block_identifier=block_identifier)
    total_supply_raw = v.functions.totalSupply().call(block_identifier=block_identifier)
    vault_decimals = v.functions.decimals().call(block_identifier=block_identifier)

    total_assets = Decimal(total_assets_raw) / Decimal(10 ** asset_dec)
    total_supply = Decimal(total_supply_raw) / Decimal(10 ** vault_decimals)

    share_price = Decimal(0)
    if total_supply_raw != 0:
        share_price = total_assets / total_supply

    return {
        "asset": asset_addr,
        "asset_decimals": asset_dec,
        "asset_symbol": asset_sym,
        "total_assets_raw": total_assets_raw,
        "total_assets": total_assets,
        "total_supply_raw": total_supply_raw,
        "total_supply": total_supply,
        "share_price": share_price,
        "vault_decimals": vault_decimals,
    }