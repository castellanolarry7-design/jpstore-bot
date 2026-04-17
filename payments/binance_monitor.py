"""
binance_monitor.py – Auto-detection of received Binance Pay payments
Uses the personal Binance API (not merchant) to poll incoming pay transactions.

How to get API keys:
1. Go to https://www.binance.com/en/my/settings/api-management
2. Click "Create API" → choose "System generated"
3. Label it: "JPStoreX Bot"
4. Enable ONLY: ✅ "Enable Reading"  (DO NOT enable trading or withdrawals)
5. Save API Key and Secret to your .env as BINANCE_API_KEY / BINANCE_API_SECRET

Endpoint used: GET /sapi/v1/pay/transactions
Docs: https://binance-docs.github.io/apidocs/spot/en/#get-pay-trade-history-user_data
"""
import asyncio
import hashlib
import hmac
import time
import urllib.parse
import aiohttp

BINANCE_BASE    = "https://api.binance.com"
POLL_INTERVAL   = 30     # seconds between checks
TOLERANCE       = 0.000015  # essentially exact — only covers IEEE 754 float imprecision at 4 decimals
DEFAULT_TIMEOUT = 900    # 15 minutes


def _sign(secret: str, params: dict) -> str:
    """HMAC-SHA256 signature required by Binance API."""
    query = urllib.parse.urlencode(params)
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()


async def get_received_binance_pay(
    api_key: str,
    api_secret: str,
    start_time_ms: int,
) -> list[dict]:
    """
    Returns recent Binance Pay payments RECEIVED in your account since start_time_ms.
    Each item: { 'transaction_id', 'amount', 'currency', 'timestamp', 'payer' }
    """
    params = {
        "startTime": start_time_ms,
        "limit":     100,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(api_secret, params)

    headers = {"X-MBX-APIKEY": api_key}
    url = f"{BINANCE_BASE}/sapi/v1/pay/transactions"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                print(f"👀 RESPUESTA BRUTA DE BINANCE: {data}")
    except Exception as e:
        print(f"[BinanceMonitor] Request error: {e}")
        return []

    if data.get("code") != "000000":
        print(f"[BinanceMonitor] API error: {data.get('message', data)}")
        return []

    results = []
    for tx in data.get("data", []):
        # orderType PAY = received, C2C = sent — we only want received
        if tx.get("orderType") not in ("PAY", "PAY_REFUND", "C2C"):
            continue
        try:
            # Get USDT amount from fundsDetail or top-level amount
            amount = 0.0
            for fund in tx.get("fundsDetail", []):
                if fund.get("currency", "").upper() == "USDT":
                    amount = float(fund.get("amount", 0))
                    break
            if amount == 0.0:
                amount = float(tx.get("transAmount", 0) or tx.get("amount", 0))

            payer_info = tx.get("payerInfo", {})
            # Binance Pay returns name and sometimes binanceId
            payer_name = payer_info.get("name", "")
            payer_id   = str(payer_info.get("binanceId", "") or
                             payer_info.get("accountId", "") or "")
            # Combined payer string for matching
            payer_combined = f"{payer_name} {payer_id}".strip().lower()

            results.append({
                "transaction_id": tx.get("transactionId", ""),
                "amount":         amount,
                "currency":       "USDT",
                "timestamp":      int(tx.get("transactionTime", 0)),
                "payer":          payer_combined,
                "payer_name":     payer_name,
                "payer_id":       payer_id,
            })
        except Exception:
            continue

    return results


async def monitor_binance_pay_payment(
    bot,
    order_id: int,
    expected_amount: float,
    payer_binance_id: str,
    user_id: int,
    service_name: str,
    lang: str,
    qty: int = 1,
    timeout_seconds: int = DEFAULT_TIMEOUT,
) -> None:
    """
    Background task: polls Binance Pay history every 30s until payment found or timeout.
    On success: marks order as paid, notifies admin + user.
    """
    from config import BINANCE_API_KEY, BINANCE_API_SECRET
    import database as db
    from utils.notifications import notify_admins_new_order

    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        print(f"[BinanceMonitor] No API keys configured — order #{order_id} won't be auto-detected.")
        return

    start_time  = time.time()
    start_ts_ms = int(start_time * 1000)

    # Normalize payer ID for comparison (strip spaces, lowercase)
    payer_id_normalized = payer_binance_id.strip().lower()

    print(f"[BinanceMonitor] Watching order #{order_id} | "
          f"Binance Pay | ${expected_amount:.2f} USDT | payer: {payer_binance_id}")

    while time.time() - start_time < timeout_seconds:
        await asyncio.sleep(POLL_INTERVAL)

        # Check if order was already processed or cancelled
        order = await db.get_order(order_id)
        if not order or order["status"] != "pending":
            print(f"[BinanceMonitor] Order #{order_id} no longer pending, stopping.")
            return

        try:
            transactions = await get_received_binance_pay(
                BINANCE_API_KEY, BINANCE_API_SECRET, start_ts_ms
            )
        except Exception as e:
            print(f"[BinanceMonitor] Fetch error: {e}")
            continue

        # Match by payer ID (primary) + amount range (secondary)
        # Supports exact match, underpayment (credit to balance) and overpayment (deliver + credit surplus).
        for tx in transactions:
            received    = tx["amount"]
            tx_payer_id = tx["payer_id"].strip().lower()

            # ── Payer ID filter ────────────────────────────────────────────
            if tx_payer_id:
                if payer_id_normalized not in tx_payer_id and tx_payer_id not in payer_id_normalized:
                    continue  # different payer, skip
            else:
                # Binance didn't return payer_id — only proceed if amount is in a tight range
                if abs(received - expected_amount) > 1.0:
                    continue

            # ── Classify payment ───────────────────────────────────────────
            is_exact = abs(received - expected_amount) <= TOLERANCE
            is_under = (not is_exact) and received < expected_amount and received >= expected_amount * 0.3
            is_over  = (not is_exact) and received > expected_amount and received <= expected_amount * 5.0

            if not (is_exact or is_under or is_over):
                continue

            tx_id = tx["transaction_id"]
            classification = "Exact" if is_exact else ("Underpayment" if is_under else "Overpayment")
            print(f"[BinanceMonitor] {classification} | Order #{order_id} | "
                  f"expected: ${expected_amount:.2f} | received: ${received:.2f} | TX: {tx_id}")

            await db.update_order_proof(order_id, f"BPAY:{tx_id}")

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
                    admin_note=f"Topup via Binance Pay: received ${received:.2f} | TX: {tx_id}"
                )
                user        = await db.get_user(user_id)
                new_balance = float(user["credits"]) if user else credited
                if lang == "es":
                    topup_msg = (
                        f"✅ <b>¡Saldo añadido!</b>\n\n"
                        f"💰 <b>+${credited:.2f} USDT</b> añadidos a tu billetera.\n"
                        f"📊 Nuevo saldo: <b>${new_balance:.2f} USDT</b>\n\n"
                        "Ya puedes usar tu saldo para comprar cualquier servicio 🎉"
                    )
                else:
                    topup_msg = (
                        f"✅ <b>Balance added!</b>\n\n"
                        f"💰 <b>+${credited:.2f} USDT</b> credited to your wallet.\n"
                        f"📊 New balance: <b>${new_balance:.2f} USDT</b>\n\n"
                        "You can now use your balance to buy any service 🎉"
                    )
                try:
                    await bot.send_message(chat_id=user_id, text=topup_msg, parse_mode="HTML")
                except Exception:
                    pass
                return

            # ── Underpayment: credit received to balance, cancel order ─────
            if is_under:
                credited = round(received, 2)
                await db.update_order_status(
                    order_id, "cancelled",
                    admin_note=f"Underpayment: received ${received:.2f}, expected ${expected_amount:.2f} | TX: {tx_id}"
                )
                await db.add_credits(user_id, credited)
                user        = await db.get_user(user_id)
                new_balance = float(user["credits"]) if user else credited
                if lang == "es":
                    msg = (
                        f"⚠️ <b>Pago incompleto — Pedido #{order_id} cancelado</b>\n\n"
                        f"Recibimos <b>${received:.2f} USDT</b>, pero el total era "
                        f"<b>${expected_amount:.2f} USDT</b>.\n\n"
                        f"💰 <b>${credited:.2f} USDT</b> han sido añadidos a tu billetera.\n"
                        f"📊 Nuevo saldo: <b>${new_balance:.2f} USDT</b>\n\n"
                        "Puedes usar tu saldo para cubrir el total la próxima vez, "
                        "o recargar e intentarlo de nuevo 💙"
                    )
                else:
                    msg = (
                        f"⚠️ <b>Incomplete payment — Order #{order_id} cancelled</b>\n\n"
                        f"We received <b>${received:.2f} USDT</b>, but the order total was "
                        f"<b>${expected_amount:.2f} USDT</b>.\n\n"
                        f"💰 <b>${credited:.2f} USDT</b> has been added to your wallet balance.\n"
                        f"📊 New balance: <b>${new_balance:.2f} USDT</b>\n\n"
                        "You can use your balance to pay the full amount next time, "
                        "or top up and try again 💙"
                    )
                try:
                    await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
                except Exception:
                    pass
                return

            # ── Exact or overpayment: deliver service ──────────────────────
            await db.update_order_status(
                order_id, "paid",
                admin_note=f"Auto Binance Pay {'(overpayment)' if is_over else ''} | "
                           f"TX: {tx_id} | from: {tx['payer']} | "
                           f"received: ${received:.2f} expected: ${expected_amount:.2f}"
            )

            from utils.delivery import auto_deliver
            service_id      = order["service_id"]
            stock_delivered = await auto_deliver(
                bot, order_id, service_id, user_id, lang, qty=qty)

            if not stock_delivered:
                user = await db.get_user(user_id)
                await notify_admins_new_order(bot, order, user)

            # ── Credit surplus to balance if overpayment ───────────────────
            if is_over:
                surplus = round(received - expected_amount, 2)
                await db.add_credits(user_id, surplus)
                user        = await db.get_user(user_id)
                new_balance = float(user["credits"]) if user else surplus
                if lang == "es":
                    surplus_msg = (
                        f"💰 <b>¡Excedente acreditado!</b>\n\n"
                        f"Enviaste ${received:.2f} para un pedido de ${expected_amount:.2f}.\n"
                        f"La diferencia <b>+${surplus:.2f} USDT</b> fue añadida a tu billetera.\n"
                        f"📊 Saldo: <b>${new_balance:.2f} USDT</b>"
                    )
                else:
                    surplus_msg = (
                        f"💰 <b>Overpayment credited!</b>\n\n"
                        f"You sent ${received:.2f} for a ${expected_amount:.2f} order.\n"
                        f"The difference <b>+${surplus:.2f} USDT</b> has been added to your wallet.\n"
                        f"📊 Balance: <b>${new_balance:.2f} USDT</b>"
                    )
                try:
                    await bot.send_message(chat_id=user_id, text=surplus_msg, parse_mode="HTML")
                except Exception:
                    pass

            # Referral credit
            from handlers.referrals import handle_first_purchase_referral
            await handle_first_purchase_referral(bot, user_id)
            return

    # Timeout — cancel order, delete instruction message, notify user
    order = await db.get_order(order_id)
    if order and order["status"] == "pending":
        await db.update_order_status(order_id, "cancelled",
                                     admin_note="Auto-cancelled: 15min timeout")

        # Delete the payment instruction message
        if order.get("instruction_msg_id"):
            try:
                await bot.delete_message(
                    chat_id=order["instruction_chat_id"],
                    message_id=order["instruction_msg_id"]
                )
            except Exception:
                pass

        if lang == "es":
            msg = (
                f"⏰ <b>Pedido #{order_id} vencido</b>\n\n"
                "No detectamos tu Binance Pay en 15 minutos. "
                "El pedido fue cancelado automáticamente.\n\n"
                "Si ya pagaste, contacta soporte 💙"
            )
        else:
            msg = (
                f"⏰ <b>Order #{order_id} expired</b>\n\n"
                "We didn't detect your Binance Pay transfer in 15 minutes. "
                "The order was cancelled automatically.\n\n"
                "If you already paid, contact support 💙"
            )
        try:
            await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
        except Exception:
            pass

    print(f"[BinanceMonitor] Order #{order_id} timed out after {timeout_seconds}s.")
