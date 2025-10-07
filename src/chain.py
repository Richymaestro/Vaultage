import os
from functools import lru_cache
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

def get_w3() -> Web3:
    rpc = os.getenv("WEB3_HTTP_PROVIDER")
    if not rpc:
        raise RuntimeError("WEB3_HTTP_PROVIDER missing in .env")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        raise RuntimeError("Failed to connect to RPC")
    return w3

def checksum(addr: str) -> str:
    return Web3.to_checksum_address(addr)

@lru_cache(maxsize=2048)
def _block_ts(w3: Web3, block_number: int) -> int:
    blk = w3.eth.get_block(block_number)
    return blk.timestamp

def find_block_at_or_before_timestamp(w3: Web3, target_ts: int) -> int:
    """
    Returns the highest block number with timestamp <= target_ts.
    If target is before genesis, returns 0.
    """
    latest = w3.eth.block_number
    # early exit if target is after latest
    if _block_ts(w3, latest) <= target_ts:
        return latest

    low = 0
    high = latest
    # if target is before first block, return 0
    if _block_ts(w3, 0) > target_ts:
        return 0

    while low < high:
        mid = (low + high + 1) // 2
        ts = _block_ts(w3, mid)
        if ts <= target_ts:
            low = mid
        else:
            high = mid - 1
    return low