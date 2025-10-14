# src/events.py
from decimal import Decimal
from typing import Tuple

from web3 import Web3

from src.chain import checksum, find_block_at_or_before_timestamp

# Minimal ABIs to resolve underlying asset decimals
ERC4626_ABI_MIN = [
    {"inputs": [], "name": "asset", "outputs": [{"internalType": "address", "name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"}
]
ERC20_ABI_MIN = [
    {"inputs": [], "name": "decimals", "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
     "stateMutability": "view", "type": "function"}
]

# Event topics (OpenZeppelin ERC-4626)
TOPIC_DEPOSIT  = Web3.keccak(text="Deposit(address,address,uint256,uint256)").to_0x_hex()
TOPIC_WITHDRAW = Web3.keccak(text="Withdraw(address,address,address,uint256,uint256)").to_0x_hex()

def _asset_decimals(w3, vault_addr: str) -> int:
    try:
        vault = w3.eth.contract(address=checksum(vault_addr), abi=ERC4626_ABI_MIN)
        asset_addr = vault.functions.asset().call()
        if int(asset_addr, 16) == 0:
            return 18
        erc20 = w3.eth.contract(address=checksum(asset_addr), abi=ERC20_ABI_MIN)
        return int(erc20.functions.decimals().call())
    except Exception:
        return 18

def _sum_event_assets_in_logs(w3, vault_addr: str, topic0: str, from_block, to_block) -> int:
    """
    Returns sum of 'assets' field over matching logs in raw integer (token base units).
    For ERC-4626 Deposit/Withdraw, data encodes assets (uint256) then shares (uint256).
    """
    try:
        logs = w3.eth.get_logs({
            "fromBlock": from_block,
            "toBlock": to_block,
            "address": checksum(vault_addr),
            "topics": [topic0],
        })
    except Exception:
        return 0

    total_raw = 0
    for lg in logs:
        data = lg.get("data")
        # Expect hex string like 0x<64 bytes assets><64 bytes shares>
        if not isinstance(data, (str, bytes)):
            continue
        if isinstance(data, bytes):
            data = data.hex()
            if not data.startswith("0x"):
                data = "0x" + data
        if not data.startswith("0x"):
            continue
        hexdata = data[2:].rjust(64 * 2, "0")
        try:
            assets_hex = hexdata[0:64]
            total_raw += int(assets_hex, 16)
        except Exception:
            continue
    return total_raw

def get_deposits_withdraws(*, w3, vault_addr: str, since_ts: int, until_ts: int) -> Tuple[Decimal, Decimal]:
    """
    Sum ERC-4626 Deposit/Withdraw 'assets' between [since_ts, until_ts] (UTC),
    convert to token units using underlying decimals, and return (deposits, withdraws) as Decimal.
    """
    # Map timestamps to block range (inclusive)
    try:
        from_block = find_block_at_or_before_timestamp(w3, since_ts)
    except Exception:
        from_block = "earliest"
    try:
        to_block = find_block_at_or_before_timestamp(w3, until_ts)
    except Exception:
        to_block = "latest"

    decs = _asset_decimals(w3, vault_addr)
    scale = Decimal(10) ** decs

    dep_raw = _sum_event_assets_in_logs(w3, vault_addr, TOPIC_DEPOSIT,  from_block, to_block)
    wdr_raw = _sum_event_assets_in_logs(w3, vault_addr, TOPIC_WITHDRAW, from_block, to_block)

    deposits  = (Decimal(dep_raw) / scale) if dep_raw else Decimal(0)
    withdraws = (Decimal(wdr_raw) / scale) if wdr_raw else Decimal(0)
    return deposits, withdraws