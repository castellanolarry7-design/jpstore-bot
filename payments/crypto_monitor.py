"""
crypto_monitor.py – Automated blockchain payment detection
Monitors TRC20 (TronGrid API) and BEP20 (BSC public RPC / BSCScan fallback).

BEP20 strategy (no API key needed):
  Primary:  BSC public JSON-RPC via eth_getLogs — completely free, no signup
  Fallback: BSCScan API (optional key in .env as BSCSCAN_API_KEY)

TRC20:
  TronGrid API key (optional, improves rate limit): TRONGRID_API_KEY in .env
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

# ── BSC public RPC endpoints (tried in order, no API key needed) ──────────────
BSC_RPC_ENDPOINTS = [
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.defibit.io/",
    "https://bsc-dataseed1.ninicoin.io/",
    "https://rpc.ankr.com/bsc",
]

# ERC-20 Transfer(address indexed from, address indexed to, uint256 value)
ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

POLL_INTERVAL       = 30    # seconds between blockchain checks
TOLERANCE           = 0.02  # $0.02 tolerance for amount matching (covers float rounding)
DEFAULT_TIMEOUT     = 900   # 15 minutes
TIMESTAMP_BUFFER_S  = 300   # look 5 min back to avoid missing txs due to clock skew


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

async def _rpc_post(endpoint: str, payload: dict) -> dict | None:
    """POST a JSON-RPC request to a BSC node. Returns parsed response or None."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint, json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except Exception as e:
        print(f"[BSC-RPC] {endpoint} error: {e}")
        return None


async def _get_current_block() -> int | None:
    """Returns the latest BSC block number via public RPC."""
    payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
    for endpoint in BSC_RPC_ENDPOINTS:
        result = await _rpc_post(endpoint, payload)
        if result and "result" in result:
            try:
                return int(result["result"], 16)
            except Exception:
                continue
    return None


async def _get_bep20_logs(from_block: int, to_block: int, address: str) -> list[dict]:
    """
    Queries eth_getLogs for USDT Transfer events to `address` in block range.
    Pads address to 32-byte topic format (left-padded with zeros).
    """
    # Topics: [Transfer signature, any from, to=address]
    padded = "0x" + address.lower().replace("0x", "").zfill(64)
    payload = {
        "jsonrpc": "2.0", "method": "eth_getLogs", "id": 1,
        "params": [{
            "fromBlock": hex(from_block),
            "toBlock":   hex(to_block),
            "address":   USDT_BEP20_CONTRACT,
            "topics":    [ERC20_TRANSFER_TOPIC, None, padded],
        }]
    }
    for endpoint in BSC_RPC_ENDPOINTS:
        result = await _rpc_post(endpoint, payload)
        if result is None:
            continue
        if "error" in result:
            print(f"[BSC-RPC] eth_getLogs error from {endpoint}: {result['error']}")
            continue
        logs = result.get("result", [])
        if isinstance(logs, list):
            print(f"[BSC-RPC] Got {len(logs)} log(s) from {endpoint}")
            return logs
    return []


async def get_bep20_transactions(address: str, min_timestamp_s: int = 0) -> list[dict]:
    """
    Returns recent incoming USDT BEP20 transactions to `address`.

    Primary method: BSC public RPC (eth_getLogs) — no API key needed.
    Fallback: BSCScan API (uses BSCSCAN_API_KEY from .env if set).

    BSC produces ~1 block every 3 seconds, so 600 blocks ≈ 30 minutes.
    We scan the last 1200 blocks (~60 min) to be safe.
    """
    results = []

    # ── Method 1: BSC public RPC (eth_getLogs) ────────────────────────────────
    try:
        current_block = await _get_current_block()
        if current_block:
            # ~1 block per 3s → 1200 blocks ≈ 60 min lookback
            from_block = max(0, current_block - 1200)
            logs = await _get_bep20_logs(from_block, current_block, address)
            for log in logs:
                try:
                    # value is the last topic / data field (uint256, 18 decimals)
                    raw_value = int(log.get("data", "0x0"), 16)
                    amount    = raw_value / 1e18
                    # block number → approximate timestamp (3s/block)
                    block_num = int(log.get("blockNumber", "0x0"), 16)
                    approx_ts = int((block_num - current_block) * 3 + __import__("time").time())
                    tx_hash   = log.get("transactionHash", "")
                    results.append({
                        "tx_id":     tx_hash,
                        "from":      "0x" + log["topics"][1][-40:] if len(log.get("topics", [])) > 1 else "",
                        "to":        address,
                        "amount":    amount,
                        "timestamp": approx_ts,
                        "network":   "bep20",
                    })
                except Exception:
                    continue
            if results:
                return results
            # No results from RPC (could mean no txs or RPC issue) — try BSCScan as backup
            print("[BSC-RPC] No logs via RPC, trying BSCScan as backup…")
        else:
            print("[BSC-RPC] Could not get current block, falling back to BSCScan…")
    except Exception as e:
        print(f"[BSC-RPC] Unexpected error: {e}, falling back to BSCScan…")

    # ── Method 2: BSCScan fallback ────────────────────────────────────────────
    base_params = (
        "?module=account&action=tokentx"
        f"&contractaddress={USDT_BEP20_CONTRACT}"
        f"&address={address}"
        "&sort=desc&page=1&offset=30"
    )
    urls = []
    if BSCSCAN_API_KEY:
        urls.append("https://api.bscscan.com/api" + base_params + f"&apikey={BSCSCAN_API_KEY}")
    urls.append("https://api.bscscan.com/api" + base_params)  # keyless fallback

    for url in urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
        except Exception as e:
            print(f"[BSCScan] Request error: {e}")
            continue

        status  = data.get("status")
        message = data.get("message", "")
        raw_res = data.get("result", "")

        if status == "1":
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

        if "no transactions" in message.lower():
            return []

        if "notok" in message.lower() or "invalid api" in str(raw_res).lower():
            print(f"[BSCScan] ⚠ Key rejected ({raw_res}), retrying without key…")
            continue

        print(f"[BSCScan] Error — status={status} message={message} result={raw_res}")
        break

    return results

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
    network: str,
    expected_amount: float,
    user_id: int,
    service_name: str,
    lang: str,
    qty: int = 1,
    timeout_seconds: int = DEFAULT_TIMEOUT,
) -> None:
    """
    Background task: polls blockchain every 30s until payment found or timeout.
    On success: marks order as paid, notifies admin + user.
    Wrapped in a top-level try/except so NO exception can kill the task silently.
    """
    try:
        await _monitor_crypto_payment_inner(
            bot=bot, order_id=order_id, network=network,
            expected_amount=expected_amount, user_id=user_id,
            service_name=service_name, lang=lang, qty=qty,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        import traceback
        print(f"[CryptoMonitor] ❌ FATAL ERROR on order #{order_id}: {exc}")
        traceback.print_exc()


async def _monitor_crypto_payment_inner(
    bot,
    order_id: int,
    network: str,
    expected_amount: float,
    user_id: int,
    service_name: str,
    lang: str,
    qty: int = 1,
    timeout_seconds: int = DEFAULT_TIMEOUT,
) -> None:
    import time
    import database as db
    from utils.notifications import notify_admins_new_order

    address     = USDT_TRC20 if network == "trc20" else USDT_BEP20
    start_time  = time.time()
    # Look back TIMESTAMP_BUFFER_S seconds to avoid missing txs due to clock skew
    start_ts_ms = int((start_time - TIMESTAMP_BUFFER_S) * 1000)  # TronGrid uses ms
    start_ts_s  = int(start_time - TIMESTAMP_BUFFER_S)           # BSCScan uses seconds

    seen_txids: set = set()  # avoid re-processing the same TX across poll cycles
    poll_count = 0

    print(f"[CryptoMonitor] ▶ Started | order #{order_id} | {network.upper()} | "
          f"expected ${expected_amount:.2f} USDT | address: {address}")

    while time.time() - start_time < timeout_seconds:
        await asyncio.sleep(POLL_INTERVAL)
        poll_count += 1
        elapsed = int(time.time() - start_time)

        # Check if order was cancelled or already processed
        order = await db.get_order(order_id)
        if not order or order["status"] != "pending":
            print(f"[CryptoMonitor] Order #{order_id} status={order['status'] if order else 'NOT FOUND'}, stopping.")
            return

        print(f"[CryptoMonitor] Poll #{poll_count} | order #{order_id} | {elapsed}s elapsed | querying {network.upper()}…")

        # Fetch recent transactions
        try:
            if network == "trc20":
                txs = await get_trc20_transactions(address, min_timestamp_ms=start_ts_ms)
            else:
                txs = await get_bep20_transactions(address, min_timestamp_s=start_ts_s)
        except Exception as e:
            print(f"[CryptoMonitor] ⚠ Fetch error on poll #{poll_count}: {e}")
            continue

        print(f"[CryptoMonitor] Poll #{poll_count} | {len(txs)} transaction(s) found")

        # Look for a matching transaction (exact) or overpayment (deliver + credit surplus).
        # Note: underpayment detection is skipped for on-chain payments since we can't
        # verify the sender identity — any under-valued incoming tx could be unrelated.
        if txs:
            print(f"[CryptoMonitor] Order #{order_id} — {len(txs)} tx(s) to check")
        for tx in txs:
            tx_id    = tx["tx_id"]
            received = tx["amount"]

            if tx_id in seen_txids:
                continue  # already processed this TX

            print(f"[CryptoMonitor] Checking TX {tx_id[:20]}… | received: ${received:.4f} | expected: ${expected_amount:.2f}")

            is_exact = amount_matches(received, expected_amount)
            is_over  = (not is_exact) and received > expected_amount and received <= expected_amount * 5.0

            if not (is_exact or is_over):
                seen_txids.add(tx_id)   # mark as seen even if no match
                continue

            seen_txids.add(tx_id)
            classification = "Exact" if is_exact else "Overpayment"
            print(f"[CryptoMonitor] ✅ {classification} | Order #{order_id} | "
                  f"expected: ${expected_amount:.2f} | received: ${received:.2f} | TX: {tx_id}")

            # Save proof and mark paid
            await db.update_order_proof(order_id, f"TX:{tx_id}")
            await db.update_order_status(
                order_id, "paid",
                admin_note=f"Auto-detected {network.upper()} {'(overpayment)' if is_over else ''} | "
                           f"TX: {tx_id} | received: ${received:.2f} expected: ${expected_amount:.2f}"
            )

            # ── Delete the payment instruction message ─────────────────────
            order = await db.get_order(order_id)
            if order and order.get("instruction_msg_id"):
                try:
                    await bot.delete_message(
                        chat_id=order["instruction_chat_id"],
                        message_id=order["instruction_msg_id"]
                    )
                except Exception:
                    pass

            # ── Topup orders: credit actual received amount ────────────────
            if order.get("item_type") == "topup":
                credited = round(received, 2)
                await db.add_credits(user_id, credited)
                await db.update_order_status(
                    order_id, "delivered",
                    admin_note=f"Topup via {network.upper()}: received ${received:.2f} | TX: {tx_id}"
                )
                user        = await db.get_user(user_id)
                new_balance = float(user["credits"]) if user else credited
                if lang == "en":
                    topup_msg = (
                        f"✅ <b>Balance added!</b>\n\n"
                        f"💰 <b>+${credited:.2f} USDT</b> credited to your wallet.\n"
                        f"📊 New balance: <b>${new_balance:.2f} USDT</b>\n\n"
                        "You can now use your balance to buy any service 🎉"
                    )
                else:
                    topup_msg = (
                        f"✅ <b>¡Saldo añadido!</b>\n\n"
                        f"💰 <b>+${credited:.2f} USDT</b> añadidos a tu billetera.\n"
                        f"📊 Nuevo saldo: <b>${new_balance:.2f} USDT</b>\n\n"
                        "Ya puedes usar tu saldo para comprar cualquier servicio 🎉"
                    )
                try:
                    await bot.send_message(chat_id=user_id, text=topup_msg, parse_mode="HTML")
                except Exception:
                    pass
                return

            # ── Regular service/method: auto-deliver from stock ────────────
            from utils.delivery import auto_deliver
            service_id      = order["service_id"]
            stock_delivered = await auto_deliver(
                bot, order_id, service_id, user_id, lang, qty=qty)

            # ── If manual delivery needed → notify admins ──────────────────
            if not stock_delivered:
                user = await db.get_user(user_id)
                await notify_admins_new_order(bot, order, user)

            # ── Credit surplus to balance if overpayment ───────────────────
            if is_over:
                surplus = round(received - expected_amount, 2)
                await db.add_credits(user_id, surplus)
                user        = await db.get_user(user_id)
                new_balance = float(user["credits"]) if user else surplus
                if lang == "en":
                    surplus_msg = (
                        f"💰 <b>Overpayment credited!</b>\n\n"
                        f"You sent ${received:.2f} for a ${expected_amount:.2f} order.\n"
                        f"The difference <b>+${surplus:.2f} USDT</b> has been added to your wallet.\n"
                        f"📊 Balance: <b>${new_balance:.2f} USDT</b>"
                    )
                else:
                    surplus_msg = (
                        f"💰 <b>¡Excedente acreditado!</b>\n\n"
                        f"Enviaste ${received:.2f} para un pedido de ${expected_amount:.2f}.\n"
                        f"La diferencia <b>+${surplus:.2f} USDT</b> fue añadida a tu billetera.\n"
                        f"📊 Saldo: <b>${new_balance:.2f} USDT</b>"
                    )
                try:
                    await bot.send_message(chat_id=user_id, text=surplus_msg, parse_mode="HTML")
                except Exception:
                    pass

            # Handle referral credit
            from handlers.referrals import handle_first_purchase_referral
            await handle_first_purchase_referral(bot, user_id)
            return

    # Timeout — cancel order, delete instruction message, notify user
    order = await db.get_order(order_id)
    if order and order["status"] == "pending":
        timeout_min = timeout_seconds // 60
        await db.update_order_status(order_id, "cancelled",
                                     admin_note=f"Auto-cancelled: {timeout_min}min timeout")
        # Delete instruction message
        if order.get("instruction_msg_id"):
            try:
                await bot.delete_message(chat_id=order["instruction_chat_id"],
                                         message_id=order["instruction_msg_id"])
            except Exception:
                pass

        timeout_min = timeout_seconds // 60
        if lang == "en":
            timeout_msg = (
                f"⏰ <b>Order #{order_id} expired</b>\n\n"
                f"We didn't detect your payment in {timeout_min} minutes. "
                "The order was cancelled automatically.\n\n"
                "If you already sent the payment, contact support 💙"
            )
        else:
            timeout_msg = (
                f"⏰ <b>Pedido #{order_id} vencido</b>\n\n"
                f"No detectamos tu pago en {timeout_min} minutos. "
                "El pedido fue cancelado automáticamente.\n\n"
                "Si ya enviaste el pago, contacta soporte 💙"
            )
        try:
            await bot.send_message(chat_id=user_id, text=timeout_msg, parse_mode="HTML")
        except Exception:
            pass

    print(f"[CryptoMonitor] Order #{order_id} timed out after {timeout_seconds}s.")
