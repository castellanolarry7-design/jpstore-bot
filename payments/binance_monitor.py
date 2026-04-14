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

BINANCE_BASE = "https://api.binance.com"
POLL_INTERVAL = 30   # seconds between checks
TOLERANCE = 0.005    # $0.005 tolerance for amount matching


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
    except Exception as e:
        print(f"[BinanceMonitor] Request error: {e}")
        return []

    if data.get("code") != "000000":
        print(f"[BinanceMonitor] API error: {data.get('message', data)}")
        return []

    results = []
    for tx in data.get("data", []):
        # orderType PAY = received, C2C = sent — we only want received
        if tx.get("orderType") not in ("PAY", "PAY_REFUND"):
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
    timeout_seconds: int = 3600,
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

        # Match by BOTH payer ID and expected amount
        for tx in transactions:
            # Check payer identity — match against name or any ID field
            tx_payer = str(tx.get("payer", "")).strip().lower()
            payer_match = (
                payer_id_normalized in tx_payer or
                tx_payer in payer_id_normalized or
                payer_id_normalized == tx_payer
            )
            amount_match = abs(tx["amount"] - expected_amount) <= TOLERANCE

            if payer_match and amount_match:
                tx_id = tx["transaction_id"]
                print(f"[BinanceMonitor] ✅ Match! Order #{order_id} | TX: {tx_id}")

                await db.update_order_proof(order_id, f"BPAY:{tx_id}")
                await db.update_order_status(
                    order_id, "paid",
                    admin_note=f"Auto Binance Pay detected | TX: {tx_id} | "
                               f"from: {tx['payer']}"
                )

                # Send payment confirmation to user
                if lang == "en":
                    confirm_msg = (
                        f"✅ <b>Binance Pay confirmed!</b>\n\n"
                        f"🆔 Order #{order_id} — {service_name}\n"
                        f"💵 ${tx['amount']:.2f} USDT | 🔖 <code>{tx_id}</code>"
                    )
                else:
                    confirm_msg = (
                        f"✅ <b>¡Binance Pay confirmado!</b>\n\n"
                        f"🆔 Pedido #{order_id} — {service_name}\n"
                        f"💵 ${tx['amount']:.2f} USDT | 🔖 <code>{tx_id}</code>"
                    )
                try:
                    await bot.send_message(chat_id=user_id, text=confirm_msg, parse_mode="HTML")
                except Exception:
                    pass

                # ── Auto-deliver from stock ────────────────────────────────
                from utils.delivery import auto_deliver
                order      = await db.get_order(order_id)
                service_id = order["service_id"]
                await auto_deliver(bot, order_id, service_id, user_id, lang, qty=qty)

                # Notify admins
                user = await db.get_user(user_id)
                await notify_admins_new_order(bot, order, user)

                # Referral credit
                from handlers.referrals import handle_first_purchase_referral
                await handle_first_purchase_referral(bot, user_id)
                return

    # Timeout — order stays pending, send fallback message
    order = await db.get_order(order_id)
    if order and order["status"] == "pending":
        if lang == "en":
            msg = (
                f"⏰ <b>Payment window expired</b>\n\n"
                f"Order #{order_id} — we didn't detect a Binance Pay transfer in 1 hour.\n"
                "If you already paid, tap below to send your screenshot. 💙"
            )
        else:
            msg = (
                f"⏰ <b>Ventana de pago expirada</b>\n\n"
                f"Pedido #{order_id} — no detectamos el pago de Binance Pay en 1 hora.\n"
                "Si ya pagaste, envía tu captura de pantalla. 💙"
            )
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            await bot.send_message(
                chat_id=user_id, text=msg, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "📸 Send proof" if lang == "en" else "📸 Enviar comprobante",
                        callback_data=f"proof_{order_id}"
                    )
                ]])
            )
        except Exception:
            pass

    print(f"[BinanceMonitor] Order #{order_id} timed out.")
