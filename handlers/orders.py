"""
orders.py – Order creation, proof submission, and order listing
"""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from config import SERVICES, USDT_TRC20, USDT_BEP20, BINANCE_PAY_ENABLED, BINANCE_PAY_ID
import database as db
from strings import t
from utils.keyboards import order_confirm_kb, back_to_orders_kb, main_menu_kb
from utils.notifications import notify_admins_new_order, notify_order_status

WAITING_PROOF = 1


# ── Initiate payment (service) ─────────────────────────────────────────────────

async def initiate_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: pay_<method>_<service_id>"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_", 2)
    network    = parts[1]
    service_id = parts[2]
    svc = SERVICES.get(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)

    # ── Binance Pay (manual by ID) ─────────────────────────────────────────────
    if network == "binance":
        order_id = await db.create_order(
            query.from_user.id, service_id, svc["price"], "binance_pay")

        if lang == "en":
            warning = (
                "⚠️ Make sure to send the <b>exact amount</b> and use <b>USDT</b>.\n"
                "Include the order number in the note if possible."
            )
            id_label    = "Binance Pay ID"
            amount_label = "Exact amount"
            order_label  = "Order"
            steps = (
                "1️⃣ Open <b>Binance App</b>\n"
                "2️⃣ Go to <b>Pay</b> → <b>Send</b>\n"
                "3️⃣ Search by ID: <code>{bp_id}</code>\n"
                "4️⃣ Enter amount: <b>${price} USDT</b>\n"
                "5️⃣ Press the button below to send proof ✅"
            )
        else:
            warning = (
                "⚠️ Asegúrate de enviar el <b>monto exacto</b> en <b>USDT</b>.\n"
                "Incluye el número de pedido en la nota si es posible."
            )
            id_label    = "ID de Binance Pay"
            amount_label = "Monto exacto"
            order_label  = "Pedido"
            steps = (
                "1️⃣ Abre la <b>App de Binance</b>\n"
                "2️⃣ Ve a <b>Pay</b> → <b>Enviar</b>\n"
                "3️⃣ Busca por ID: <code>{bp_id}</code>\n"
                "4️⃣ Ingresa el monto: <b>${price} USDT</b>\n"
                "5️⃣ Presiona el botón abajo para enviar comprobante ✅"
            )

        text = (
            f"🟠 <b>Binance Pay</b>\n\n"
            f"🛒 {svc['emoji']} <b>{svc['name']}</b>\n"
            f"💵 {amount_label}: <b>${svc['price']:.2f} USDT</b>\n"
            f"🆔 {order_label}: <b>#{order_id}</b>\n\n"
            f"📲 <b>{id_label}:</b>\n"
            f"<code>{BINANCE_PAY_ID}</code>\n\n"
            + steps.format(bp_id=BINANCE_PAY_ID, price=f"{svc['price']:.2f}") +
            f"\n\n{warning}"
        )
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=order_confirm_kb(order_id, lang)
        )
        return

    # ── TRC20 / BEP20 — auto-monitored ───────────────────────────────────────
    order_id = await db.create_order(
        query.from_user.id, service_id, svc["price"], network)

    # Generate unique amount to identify the payment on-chain
    from payments.crypto_monitor import unique_amount, monitor_crypto_payment
    pay_amount = unique_amount(svc["price"], order_id)

    if network == "trc20":
        address  = USDT_TRC20 or "⚠️ Not configured"
        net_name = "🔵 <b>USDT TRC20 (TRON)</b>"
        net_warn = t("warning_trc20", lang)
    else:
        address  = USDT_BEP20 or "⚠️ Not configured"
        net_name = "🟡 <b>USDT BEP20 (BSC)</b>"
        net_warn = t("warning_bep20", lang)

    if lang == "en":
        auto_note = (
            "🤖 <b>Payment is monitored automatically.</b>\n"
            "Once we detect your transfer, the order confirms itself — "
            "no need to send a screenshot!"
        )
        exact_label = "Send EXACTLY"
    else:
        auto_note = (
            "🤖 <b>El pago se monitorea automáticamente.</b>\n"
            "Cuando detectemos tu transferencia, el pedido se confirma solo — "
            "¡no necesitas enviar captura!"
        )
        exact_label = "Envía EXACTAMENTE"

    text = (
        f"📋 <b>{'Order' if lang=='en' else 'Pedido'} #{order_id}</b>\n\n"
        f"🛒 {svc['emoji']} <b>{svc['name']}</b>\n"
        f"💳 {net_name}\n\n"
        f"📤 <b>{'Address' if lang=='en' else 'Dirección'}:</b>\n"
        f"<code>{address}</code>\n\n"
        f"💵 <b>{exact_label}: <u>${pay_amount:.2f} USDT</u></b>\n"
        f"<i>{'(unique amount to identify your payment)' if lang=='en' else '(monto único para identificar tu pago)'}</i>\n\n"
        f"{net_warn}\n\n"
        f"{auto_note}"
    )

    # Keep manual proof button as fallback
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📸 " + ("Send proof manually" if lang == "en" else "Enviar comprobante manual"),
            callback_data=f"proof_{order_id}"
        )],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"cancel_{order_id}")],
    ])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    # Launch background blockchain monitor
    asyncio.create_task(monitor_crypto_payment(
        bot=context.bot,
        order_id=order_id,
        network=network,
        expected_amount=pay_amount,
        user_id=query.from_user.id,
        service_name=svc["name"],
        lang=lang,
        timeout_seconds=3600,
    ))


# ── Binance Pay auto-polling ───────────────────────────────────────────────────

async def _auto_check_binance(bot, user_id, order_id, prepay_id, svc, lang):
    from payments.binance_pay import poll_payment
    from handlers.referrals import handle_first_purchase_referral
    try:
        final = await poll_payment(prepay_id, timeout_seconds=900, interval=15)
    except Exception as e:
        print(f"[Binance polling] order {order_id}: {e}")
        return

    order = await db.get_order(order_id)
    if not order or order["status"] != "pending":
        return

    if final == "PAID":
        await db.update_order_status(order_id, "paid",
                                     admin_note="Auto Binance Pay confirmed")
        user = await db.get_user(user_id)
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>{'Payment confirmed!' if lang=='en' else '¡Pago confirmado!'}</b>\n\n"
                f"🆔 {'Order' if lang=='en' else 'Pedido'} #{order_id}\n"
                f"{svc['emoji']} <b>{svc['name']}</b>\n\n"
                + ("We'll deliver within 24 hours ⏱️" if lang == "en"
                   else "Entregamos en menos de 24 horas ⏱️")
            ),
            parse_mode="HTML"
        )
        order = await db.get_order(order_id)
        await notify_admins_new_order(bot, order, user)
        await handle_first_purchase_referral(bot, user_id)

    elif final in ("EXPIRED", "CANCELED"):
        await db.update_order_status(order_id, "cancelled",
                                     admin_note=f"Binance: {final}")
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ " + (f"Order #{order_id} expired/cancelled." if lang == "en"
                           else f"Pedido #{order_id} expirado/cancelado."),
            parse_mode="HTML",
            reply_markup=main_menu_kb(lang)
        )


# ── Request proof (TRC20/BEP20) ───────────────────────────────────────────────

async def request_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != query.from_user.id:
        await query.answer("Order not found.", show_alert=True)
        return ConversationHandler.END

    lang = await db.get_user_lang(query.from_user.id)
    context.user_data["pending_order_id"] = order_id
    context.user_data["pending_lang"] = lang

    await query.edit_message_text(
        t("send_proof", lang, order_id=order_id), parse_mode="HTML")
    return WAITING_PROOF


async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.referrals import handle_first_purchase_referral
    order_id = context.user_data.get("pending_order_id")
    lang     = context.user_data.get("pending_lang", "en")
    if not order_id:
        return ConversationHandler.END

    order = await db.get_order(order_id)
    if not order:
        await update.message.reply_text("❌ Order not found.")
        return ConversationHandler.END

    if update.message.photo:
        proof = update.message.photo[-1].file_id
    elif update.message.text:
        proof = f"TX:{update.message.text.strip()}"
    elif update.message.document:
        proof = update.message.document.file_id
    else:
        await update.message.reply_text("❌ " + ("Please send a photo or TX hash."
                                                  if lang == "en" else
                                                  "Por favor envía una foto o hash TX."))
        return WAITING_PROOF

    await db.update_order_proof(order_id, proof)
    order = await db.get_order(order_id)
    user  = await db.get_user(update.effective_user.id)

    await update.message.reply_text(
        t("proof_received", lang, order_id=order_id),
        parse_mode="HTML",
        reply_markup=back_to_orders_kb(lang)
    )
    await notify_admins_new_order(context.bot, order, user)
    await handle_first_purchase_referral(context.bot, update.effective_user.id)

    context.user_data.pop("pending_order_id", None)
    context.user_data.pop("pending_lang", None)
    return ConversationHandler.END


async def cancel_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.pop("pending_lang", "en")
    context.user_data.pop("pending_order_id", None)
    await update.message.reply_text(
        t("cancelled", lang), reply_markup=main_menu_kb(lang))
    return ConversationHandler.END


# ── My Orders ─────────────────────────────────────────────────────────────────

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang   = await db.get_user_lang(query.from_user.id)
    orders = await db.get_user_orders(query.from_user.id)

    if not orders:
        await query.edit_message_text(
            t("my_orders_empty", lang), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog")],
                [InlineKeyboardButton(t("btn_home",    lang), callback_data="home")],
            ])
        )
        return

    STATUS_ICONS  = {"pending": "⏳", "paid": "✅", "delivered": "🎉", "cancelled": "❌"}
    STATUS_LABELS_EN = {"pending": "Pending", "paid": "Paid",
                        "delivered": "Delivered", "cancelled": "Cancelled"}
    STATUS_LABELS_ES = {"pending": "Pendiente", "paid": "Pagado",
                        "delivered": "Entregado", "cancelled": "Cancelado"}
    labels = STATUS_LABELS_EN if lang == "en" else STATUS_LABELS_ES

    lines = [t("my_orders_title", lang)]
    for o in orders[:10]:
        from config import SERVICES, METHODS
        name = (SERVICES.get(o["service_id"]) or METHODS.get(o["service_id"]) or {}).get("name", o["service_id"])
        icon  = STATUS_ICONS.get(o["status"], "❓")
        label = labels.get(o["status"], o["status"])
        lines.append(
            f"{icon} <b>#{o['order_id']}</b> — {name}\n"
            f"   💵 ${o['amount']:.2f} | {label} | {o['created_at'][:10]}\n"
        )

    await query.edit_message_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
        ])
    )


# ── Cancel Order ──────────────────────────────────────────────────────────────

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[1])
    order = await db.get_order(order_id)
    lang  = await db.get_user_lang(query.from_user.id)

    if not order or order["user_id"] != query.from_user.id:
        await query.answer("Order not found.", show_alert=True)
        return
    if order["status"] not in ("pending",):
        await query.answer("This order can't be cancelled." if lang == "en"
                           else "Este pedido ya no se puede cancelar.", show_alert=True)
        return

    if order.get("payment_proof", "").startswith("BINANCE:"):
        prepay_id = order["payment_proof"].replace("BINANCE:", "")
        try:
            from payments.binance_pay import close_order
            await close_order(prepay_id)
        except Exception:
            pass

    await db.update_order_status(order_id, "cancelled",
                                  admin_note="Cancelled by user")
    await query.edit_message_text(
        f"❌ <b>{'Order' if lang=='en' else 'Pedido'} #{order_id} {'cancelled' if lang=='en' else 'cancelado'}.</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(lang)
    )
