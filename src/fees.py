from decimal import Decimal

def get_fee_amount_for_day(*, w3, vault_addr: str, since_ts: int, until_ts: int) -> Decimal:
    """
    Placeholder: returns Decimal(0).
    Extend by scanning logs for protocol-specific fee events between [since_ts, until_ts).
    """
    return Decimal(0)