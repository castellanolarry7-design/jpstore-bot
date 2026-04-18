"""
methods.py – Methods section handler
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import METHODS, USDT_TRC20, USDT_BEP20, BINANCE_PAY_ENABLED, BINANCE_PAY_ID
import database as db
from strings import t
from utils.notifications import notify_admins_new_order
from handlers.orders import WAITING_PAYER_ID


def _method_price_str(method: dict, lang: str) -> str:
    return f"${method['price']:.2f} USDT"


def _all_methods() -> dict:
    """Merge static config METHODS with DB-created methods."""
    return {**METHODS, **db.get_cached_db_methods()}


def methods_catalog_kb(lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for mid, m in _all_methods().items():
        price_str = f"${m['price']:.2f} USDT"
        buttons.append([
            InlineKeyboardButton(
                f"{m['emoji']} {m['name']} — {price_str}",
                callback_data=f"method_{mid}"
            )
        ])
    buttons.append([InlineKeyboardButton(t("btn_home", lang), callback_data="home")])
    return InlineKeyboardMarkup(buttons)


def method_detail_kb(method_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_buy_now", lang), callback_data=f"mbuy_{method_id}")],
        [InlineKeyboardButton(t("btn_back", lang),    callback_data="methods")],
    ])


def method_payment_kb(
    method_id: str,
    lang: str,
    user_credits: float = 0.0,
    total_price: float = 0.0,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🔵 USDT TRC20",  callback_data=f"mpay_trc20_{method_id}")],
        [InlineKeyboardButton("🟡 USDT BEP20",  callback_data=f"mpay_bep20_{method_id}")],
        [InlineKeyboardButton("🟠 Binance Pay", callback_data=f"mpay_binance_{method_id}")],
    ]
    if total_price > 0 and user_credits >= total_price:
        bal_label = (
            f"💰 {'Pay with balance' if lang == 'en' else 'Pagar con saldo'} "
            f"(${user_credits:.2f} USDT)"
        )
        rows.append([InlineKeyboardButton(bal_label, callback_data=f"mpay_balance_{method_id}")])
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data=f"method_{method_id}")])
    return InlineKeyboardMarkup(rows)


# ── Show all methods ──────────────────────────────────────────────────────────

async def show_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = await db.get_user_lang(query.from_user.id)
    await query.edit_message_text(
        t("methods_title", lang),
        parse_mode="HTML",
        reply_markup=methods_catalog_kb(lang)
    )


# ── Show method detail ────────────────────────────────────────────────────────

async def show_method_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    method_id = query.data.split("_", 1)[1]  # method_<id>
    method = _all_methods().get(method_id)
    if not method:
        await query.answer("Method not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)
    desc = method["description"].get(lang) or method["description"]["en"]
    delivery = method["delivery"].get(lang) or method["delivery"]["en"]

    text = t("method_detail", lang,
             emoji=method["emoji"],
             name=method["name"],
             description=desc,
             price=f"${method['price']:.2f} USDT",
             delivery=delivery)

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=method_detail_kb(method_id, lang)
    )


# ── Show payment options for method ──────────────────────────────────────────

async def show_method_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    method_id = query.data.split("_", 1)[1]  # mbuy_<id>
    method = _all_methods().get(method_id)
    if not method:
        await query.answer("Method not found.", show_alert=True)
        return

    lang         = await db.get_user_lang(query.from_user.id)
    user         = await db.get_user(query.from_user.id)
    user_credits = float(user["credits"]) if user and user.get("credits") else 0.0

    text = t("choose_payment", lang,
             emoji=method["emoji"],
             name=method["name"],
             price=f"{method['price']:.2f}")

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=method_payment_kb(method_id, lang,
                                       user_credits=user_credits, total_price=method["price"])
    )


# ── Initiate method payment ───────────────────────────────────────────────────

async def initiate_method_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: mpay_<network>_<method_id>"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_", 2)   # ['mpay', 'trc20'|'bep20'|'binance', method_id]
    network   = parts[1]
    method_id = parts[2]
    method    = METHODS.get(method_id)
    if not method:
        await query.answer("Method not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)

    # ── Binance Pay — ask payer ID first ──────────────────────────────────────
    if network == "binance":
        order_id = await db.create_order(
            user_id=query.from_user.id,
            service_id=method_id,
            amount=method["price"],
            payment_method="binance_pay",
            item_type="method",
        )

        # Reuse the orders conversation — store in context
        context.user_data["bp_order_id"]   = order_id
        context.user_data["bp_service_id"] = method_id
        context.user_data["bp_lang"]       = lang
        context.user_data["bp_item_type"]  = "method"

        if lang == "es":
            msg = (
                f"🟠 <b>Binance Pay — Paso 1 de 2</b>\n\n"
                f"⚡ {method['emoji']} <b>{method['name']}</b>\n"
                f"💵 ${method['price']:.2f} USDT\n\n"
                "Envíanos <b>tu ID de Binance Pay</b> primero.\n\n"
                "📍 <i>Binance App → Pay → Mi QR → el número bajo el código QR</i>\n\n"
                "Escribe /cancelar para cancelar."
            )
        else:
            msg = (
                f"🟠 <b>Binance Pay — Step 1 of 2</b>\n\n"
                f"⚡ {method['emoji']} <b>{method['name']}</b>\n"
                f"💵 ${method['price']:.2f} USDT\n\n"
                "Please send us <b>your Binance Pay ID</b> first.\n\n"
                "📍 <i>Binance App → Pay → My QR → the number below the QR code</i>\n\n"
                "Type /cancel to abort."
            )

        await query.edit_message_text(msg, parse_mode="HTML")
        return WAITING_PAYER_ID   # ConversationHandler in bot.py handles the next message

    # ── TRC20 / BEP20 ─────────────────────────────────────────────────────────
    order_id = await db.create_order(
        user_id=query.from_user.id,
        service_id=method_id,
        amount=method["price"],
        payment_method=network,
        item_type="method",
    )

    if network == "trc20":
        address  = USDT_TRC20 or "⚠️ Address not configured"
        net_name = "🔵 <b>USDT TRC20 (TRON)</b>"
        warning  = t("warning_trc20", lang)
    else:
        address  = USDT_BEP20 or "⚠️ Address not configured"
        net_name = "🟡 <b>USDT BEP20 (BSC)</b>"
        warning  = t("warning_bep20", lang)

    from payments.crypto_monitor import unique_amount, monitor_crypto_payment
    import asyncio as _asyncio
    pay_amount = unique_amount(method["price"], order_id)

    if lang == "es":
        auto_note  = "🤖 <b>Monitoreo automático.</b> ¡No necesitas enviar captura!"
        exact_label = "Envía EXACTAMENTE"
    else:
        auto_note  = "🤖 <b>Monitored automatically.</b> No screenshot needed!"
        exact_label = "Send EXACTLY"

    text = (
        f"📋 <b>{'Pedido' if lang=='es' else 'Order'} #{order_id}</b>\n\n"
        f"⚡ {method['emoji']} <b>{method['name']}</b>\n"
        f"💳 {net_name}\n\n"
        f"📤 <b>{'Dirección' if lang=='es' else 'Address'}:</b>\n"
        f"<code>{address}</code>\n\n"
        f"💵 <b>{exact_label}: <u>${pay_amount:.4f} USDT</u></b>\n"
        f"⚠️ <b>{'Se requiere el monto EXACTO — cualquier otro monto NO será aprobado automáticamente.' if lang=='es' else 'EXACT amount required — any other amount will NOT be approved automatically.'}</b>\n\n"
        f"{warning}\n\n{auto_note}"
    )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📸 " + ("Send proof manually" if lang=="en" else "Enviar comprobante manual"),
            callback_data=f"proof_{order_id}"
        )],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"cancel_{order_id}")],
    ])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    _asyncio.create_task(monitor_crypto_payment(
        bot=context.bot,
        order_id=order_id,
        network=network,
        expected_amount=pay_amount,
        user_id=query.from_user.id,
        service_name=method["name"],
        lang=lang,
        timeout_seconds=3600,
    ))


async def _poll_method_binance(bot, user_id, order_id, prepay_id, method, lang):
    from payments.binance_pay import poll_payment
    try:
        final = await poll_payment(prepay_id, timeout_seconds=900, interval=15)
    except Exception as e:
        print(f"[Binance Method polling] {e}")
        return

    order = await db.get_order(order_id)
    if not order or order["status"] != "pending":
        return

    if final == "PAID":
        await db.update_order_status(order_id, "paid", admin_note="Auto Binance Pay – method")
        user = await db.get_user(user_id)
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>{'Payment confirmed!' if lang=='en' else '¡Pago confirmado!'}</b>\n\n"
                f"{'Order' if lang=='en' else 'Pedido'} #{order_id} – {method['emoji']} <b>{method['name']}</b>\n\n"
                + ("We'll deliver your method shortly! ⚡" if lang == "en"
                   else "¡Te entregaremos el método en breve! ⚡")
            ),
            parse_mode="HTML"
        )
        await notify_admins_new_order(bot, order, user)
    elif final in ("EXPIRED", "CANCELED"):
        await db.update_order_status(order_id, "cancelled", admin_note=f"Binance: {final}")
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ " + (f"Order #{order_id} expired/cancelled." if lang == "en"
                           else f"Pedido #{order_id} expirado/cancelado."),
            parse_mode="HTML"
        )


# ── Pay method with wallet balance ────────────────────────────────────────────

async def initiate_balance_method_payment(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback: mpay_balance_<method_id> — deduct credits and deliver method."""
    query = update.callback_query
    await query.answer()

    method_id = query.data[len("mpay_balance_"):]
    method    = METHODS.get(method_id)
    if not method:
        await query.answer("Method not found.", show_alert=True)
        return

    user_id = query.from_user.id
    lang    = await db.get_user_lang(user_id)
    price   = method["price"]

    # ── Re-check balance ──────────────────────────────────────────────────────
    user         = await db.get_user(user_id)
    user_credits = float(user["credits"]) if user and user.get("credits") else 0.0

    if user_credits < price:
        short = price - user_credits
        err = (
            f"❌ Insufficient balance. You have ${user_credits:.2f} but need ${price:.2f} "
            f"(${short:.2f} short)."
            if lang == "en" else
            f"❌ Saldo insuficiente. Tienes ${user_credits:.2f} pero necesitas ${price:.2f} "
            f"(faltan ${short:.2f})."
        )
        await query.answer(err, show_alert=True)
        return

    # ── Deduct + create order ─────────────────────────────────────────────────
    await db.use_credits(user_id, price)
    order_id = await db.create_order(user_id, method_id, price, "balance", item_type="method")
    await db.update_order_status(order_id, "paid", admin_note="Paid with wallet balance")

    new_credits = user_credits - price

    # ── Auto-deliver ──────────────────────────────────────────────────────────
    from utils.delivery import auto_deliver
    stock_delivered = await auto_deliver(context.bot, order_id, method_id, user_id, lang, qty=1)

    if not stock_delivered:
        order    = await db.get_order(order_id)
        user_obj = await db.get_user(user_id)
        await notify_admins_new_order(context.bot, order, user_obj)

        if lang == "en":
            text = (
                f"✅ <b>Order #{order_id} placed!</b>\n\n"
                f"💳 Paid with wallet balance\n"
                f"⚡ {method['emoji']} <b>{method['name']}</b>\n"
                f"💵 ${price:.2f} USDT\n"
                f"💰 Remaining balance: <b>${new_credits:.2f} USDT</b>\n\n"
                "We'll deliver your method shortly! ⚡"
            )
        else:
            text = (
                f"✅ <b>¡Pedido #{order_id} realizado!</b>\n\n"
                f"💳 Pagado con saldo de billetera\n"
                f"⚡ {method['emoji']} <b>{method['name']}</b>\n"
                f"💵 ${price:.2f} USDT\n"
                f"💰 Saldo restante: <b>${new_credits:.2f} USDT</b>\n\n"
                "¡Te entregaremos el método en breve! ⚡"
            )
        from utils.keyboards import main_menu_kb
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
        except Exception:
            await query.message.reply_text(text, parse_mode="HTML",
                                           reply_markup=main_menu_kb(lang))
