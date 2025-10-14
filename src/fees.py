# src/fees.py
from decimal import Decimal
from typing import List

from web3 import Web3
from src.chain import checksum, find_block_at_or_before_timestamp

# If your vault emits specific fee events, add their signatures here.
# We will sum the first uint256 from the event data payload.
CANDIDATE_FEE_EVENT_SIGS: List[str] = [
    # Add/keep what your vault actually emits:
    "FeesDistributed(uint256)",
    "FeeAccrued(uint256)",
    "PerformanceFeePaid(uint256)",
    "ManagementFeePaid(uint256)",
    "ProtocolFeePaid(uint256)",
]

CANDIDATE_TOPICS = [Web3.keccak(text=sig).to_0x_hex() for sig in CANDIDATE_FEE_EVENT_SIGS]

def _sum_uint256_first_slot_in_logs(w3, vault_addr: str, topic0: str, from_block, to_block) -> int:
    try:
        logs = w3.eth.get_logs({
            "fromBlock": from_block,
            "toBlock": to_block,
            "address": checksum(vault_addr),
            "topics": [topic0],
        })
    except Exception:
        return 0

    total = 0
    for lg in logs:
        data = lg.get("data")
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
            amt_hex = hexdata[0:64]
            total += int(amt_hex, 16)
        except Exception:
            continue
    return total

def get_fee_amount_for_day(*, w3, vault_addr: str, since_ts: int, until_ts: int) -> Decimal:
    """
    Scan for common fee events emitted by the vault between [since_ts, until_ts] (UTC).
    Sums the first uint256 slot in the event data for each candidate topic.
    Returns token-amount **in the vault's underlying units if events are denominated in underlying**,
    or raw units if fees are emitted in some other token (protocol dependent).
    If your vault uses different events, add their signatures to CANDIDATE_FEE_EVENT_SIGS above.
    """
    # Map timestamps to block range
    try:
        from_block = find_block_at_or_before_timestamp(w3, since_ts)
    except Exception:
        from_block = "earliest"
    try:
        to_block = find_block_at_or_before_timestamp(w3, until_ts)
    except Exception:
        to_block = "latest"

    total_raw = 0
    for topic in CANDIDATE_TOPICS:
        total_raw += _sum_uint256_first_slot_in_logs(w3, vault_addr, topic, from_block, to_block)

    # NOTE: We do not scale by decimals here because fee token/units are protocol specific.
    # If your fee events are in underlying token units with N decimals, change this to divide by 10**N.
    return Decimal(total_raw)