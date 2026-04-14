"""
crypto_monitor.py – Automated blockchain payment detection
Monitors TRC20 (TronGrid API) and BEP20 (BSCScan API) for incoming USDT.

Free API keys:
  TronGrid:  https://www.trongrid.io  (free tier: 15 req/sec)
  BSCScan:   https://bscscan.com/apis (free tier: 5 req/sec, 100k/day)
"""
import asyncio
import aiohttp
from config import (
    USDT_TRC20, USDT_BEP20,
    TRONGRID_API_KEY, BSCSCAN_API_KEY,
)

# ── Contract addresses ────────────────────────────────────────────────────────
USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"   # USDT on TRON
USDT_BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"  # USDT on BSC

POLL_INTERVAL = 30   # seconds between blockchain checks
TOLERANCE     = 0.005  # $0.005 tolerance for amount matching


def unique_amount(base_price: float, order_id: int) -> float:
    """
    Generates a unique payment amount by adding a small decimal.
    Order #5  → base + $0.05
    Order #99 → base + $0.99
    Order #100 → base + $0.00  (wraps, but shows as base price)
    Always rounds to 2 decimal places.
    """
    cents = (order_id % 100)
    return round(base_price + cents * 0.01, 2)


def amount_matches(received: float, expected: float) -> bool:
    return abs(received - expected) <= TOLERANCE


# ── TRC20 (TronGrid) ─────────────────────────────────────────────────────────

async def get_trc20_transactions(address: str, min_timestamp_ms: int = 0) -> list[dict]:
    """
    Returns recent incoming USDT TRC20 transactions to `address`.
    Each tx dict has: { 'tx_id', 'from', 'to', 'amount', 'timestamp' }
    """
    url = (
        f"https://api.trongrid.io/v1/accounts/{address}/transactions/trc20"
        f"?limit=30&contract_address={USDT_TRC20_CONTRACT}&only_confirmed=true"
    )
    headers = {}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception as e:
        print(f"[TronGrid] Error: {e}")
        return []

    results = []
    for tx in data.get("data", []):
        try:
            to_addr = tx.get("to", "")
            if to_addr.lower() != address.lower():
                continue
            # USDT TRC20 has 6 decimals
            raw_value = int(tx.get("value", 0))
            amount    = raw_value / 1_000_000
            timestamp = tx.get("block_timestamp", 0)
            if timestamp < min_timestamp_ms:
                continue
            results.append({
                "tx_id":     tx.get("transaction_id", ""),
                "from":      tx.get("from", ""),
                "to":        to_addr,
                "amount":    amount,
                "timestamp": timestamp,
                "network":   "trc20",
            })
        except Exception:
            continue
    return results


# ── BEP20 (BSCScan) ──────────────────────────────────────────────────────────

async def get_bep20_transactions(address: str, min_timestamp_s: int = 0) -> list[dict]:
    """
    Returns recent incoming USDT BEP20 transactions to `address`.
    """
    url = (
        "https://api.bscscan.com/api"
        "?module=account&action=tokentx"
        f"&contractaddress={USDT_BEP20_CONTRACT}"
        f"&address={address}"
        "&sort=desc&page=1&offset=30"
        f"&apikey={BSCSCAN_API_KEY}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception as e:
        print(f"[BSCScan] Error: {e}")
        return []

    if data.get("status") != "1":
        return []

    results = []
    for tx in data.get("result", []):
        try:
            to_addr = tx.get("to", "").lower()
            if to_addr != address.lower():
                continue
            decimals  = int(tx.get("tokenDecimal", 18))
            raw_value = int(tx.get("value", 0))
            amount    = raw_value / (10 ** decimals)
            timestamp = int(tx.get("timeStamp", 0))
            if timestamp < min_timestamp_s:
                continue
            results.append({
                "tx_id":     tx.get("hash", ""),
                "from":      tx.get("from", ""),
                "to":        tx.get("to", ""),
                "amount":    amount,
                "timestamp": timestamp,
                "network":   "bep20",
            })
        except Exception:
            continue
    return results


# ── Main monitor task ─────────────────────────────────────────────────────────

async def monitor_crypto_payment(
    bot,
    order_id: int,
    network: str,          # 'trc20' | 'bep20'
    expected_amount: float,
    user_id: int,
    service_name: str,
    lang: str,
    qty: int = 1,
    timeout_seconds: int = 3600,   # 1 hour default
) -> None:
    """
    Background task: polls blockchain every 30s until payment found or timeout.
    On success: marks order as paid, notifies admin + user.
    """
    import time
    import database as db
    from utils.notifications import notify_admins_new_order

    address     = USDT_TRC20 if network == "trc20" else USDT_BEP20
    start_time  = time.time()
    # Only look at transactions from now onwards
    start_ts_ms = int(start_time * 1000)   # TronGrid uses ms
    start_ts_s  = int(start_time)          # BSCScan uses seconds

    print(f"[CryptoMonitor] Watching order #{order_id} | {network.upper()} | "
          f"${expected_amount:.2f} USDT | address: {address}")

    while time.time() - start_time < timeout_seconds:
        await asyncio.sleep(POLL_INTERVAL)

        # Check if order was cancelled or already processed
        order = await db.get_order(order_id)
        if not order or order["status"] != "pending":
            print(f"[CryptoMonitor] Order #{order_id} no longer pending, stopping.")
            return

        # Fetch recent transactions
        try:
            if network == "trc20":
                txs = await get_trc20_transactions(address, min_timestamp_ms=start_ts_ms)
            else:
                txs = await get_bep20_transactions(address, min_timestamp_s=start_ts_s)
        except Exception as e:
            print(f"[CryptoMonitor] Fetch error: {e}")
            continue

        # Look for a matching transaction
        for tx in txs:
            if amount_matches(tx["amount"], expected_amount):
                tx_id = tx["tx_id"]
                print(f"[CryptoMonitor] ✅ Match found! Order #{order_id} | TX: {tx_id}")

                # Save proof and mark paid
                await db.update_order_proof(order_id, f"TX:{tx_id}")
                await db.update_order_status(
                    order_id, "paid",
                    admin_note=f"Auto-detected {network.upper()} payment | TX: {tx_id}"
                )

                # Send payment confirmation to user
                order = await db.get_order(order_id)
                if lang == "en":
                    confirm_msg = (
                        f"✅ <b>Payment detected!</b>\n\n"
                        f"🆔 Order #{order_id} — {service_name}\n"
                        f"💵 ${tx['amount']:.2f} USDT | 🔗 <code>{tx_id}</code>"
                    )
                else:
                    confirm_msg = (
                        f"✅ <b>¡Pago detectado!</b>\n\n"
                        f"🆔 Pedido #{order_id} — {service_name}\n"
                        f"💵 ${tx['amount']:.2f} USDT | 🔗 <code>{tx_id}</code>"
                    )
                try:
                    await bot.send_message(chat_id=user_id, text=confirm_msg, parse_mode="HTML")
                except Exception:
                    pass

                # ── Auto-deliver from stock ────────────────────────────────
                from utils.delivery import auto_deliver
                service_id = order["service_id"]
                await auto_deliver(bot, order_id, service_id, user_id, lang, qty=qty)

                # Notify admins of the new order
                user = await db.get_user(user_id)
                await notify_admins_new_order(bot, order, user)

                # Handle referral credit
                from handlers.referrals import handle_first_purchase_referral
                await handle_first_purchase_referral(bot, user_id)
                return

    # Timeout reached — order stays pending, notify user
    order = await db.get_order(order_id)
    if order and order["status"] == "pending":
        if lang == "en":
            timeout_msg = (
                f"⏰ <b>Payment window expired</b>\n\n"
                f"Order #{order_id} — we didn't detect a payment in 1 hour.\n"
                "If you already paid, send your TX proof and we'll verify manually. 💙"
            )
        else:
            timeout_msg = (
                f"⏰ <b>Ventana de pago expirada</b>\n\n"
                f"Pedido #{order_id} — no detectamos pago en 1 hora.\n"
                "Si ya pagaste, envía tu comprobante TX y lo verificamos manualmente. 💙"
            )
        try:
            await bot.send_message(chat_id=user_id, text=timeout_msg, parse_mode="HTML")
        except Exception:
            pass

    print(f"[CryptoMonitor] Order #{order_id} timed out after {timeout_seconds}s.")
