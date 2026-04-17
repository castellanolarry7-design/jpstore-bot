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

WAITING_PROOF     = 1
WAITING_PAYER_ID  = 3   # asking for Binance Pay ID before showing instructions


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

    # ── Resolve quantity and price (with discount) ────────────────────────────
    from utils.delivery import apply_discount
    qty = context.user_data.pop("order_qty", 1)
    unit_disc, total_price, disc_rate = apply_discount(svc["price"], qty)

    # ── Binance Pay — ask payer ID first ──────────────────────────────────────
    if network == "binance":
        # Create a pending order without starting the monitor yet
        order_id = await db.create_order(
            query.from_user.id, service_id, total_price, "binance_pay")

        # Store pending info in context so next handler can use it
        context.user_data["bp_order_id"]   = order_id
        context.user_data["bp_service_id"] = service_id
        context.user_data["bp_lang"]       = lang
        context.user_data["bp_item_type"]  = "service"
        context.user_data["bp_qty"]        = qty

        qty_label = f" x{qty}" if qty > 1 else ""
        disc_note = (f" <i>(-{int(disc_rate*100)}%)</i>" if disc_rate > 0 else "")
        if lang == "es":
            msg = (
                f"🟠 <b>Binance Pay — Paso 1 de 2</b>\n\n"
                f"🛒 {svc['emoji']} <b>{svc['name']}{qty_label}</b>\n"
                f"💵 ${total_price:.2f} USDT{disc_note}\n\n"
                "Envíanos <b>tu ID de Binance Pay</b> "
                "(el número de tu cuenta).\n\n"
                "📍 <i>Binance App → Pay → Mi QR → número bajo el código QR</i>"
            )
        else:
            msg = (
                f"🟠 <b>Binance Pay — Step 1 of 2</b>\n\n"
                f"🛒 {svc['emoji']} <b>{svc['name']}{qty_label}</b>\n"
                f"💵 ${total_price:.2f} USDT{disc_note}\n\n"
                "Please send us <b>your Binance Pay ID</b> "
                "(the numeric ID of your account).\n\n"
                "📍 <i>Binance App → Pay → My QR → number below the QR code</i>"
            )

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        cancel_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ " + ("Cancelar" if lang == "es" else "Cancel"),
                                 callback_data="cancel_payer_id")
        ]])
        await query.edit_message_text(msg, parse_mode="HTML", reply_markup=cancel_kb)
        return WAITING_PAYER_ID

    # ── TRC20 / BEP20 — auto-monitored ───────────────────────────────────────
    order_id = await db.create_order(
        query.from_user.id, service_id, total_price, network)

    # Generate unique amount to identify the payment on-chain
    from payments.crypto_monitor import unique_amount, monitor_crypto_payment
    pay_amount = unique_amount(total_price, order_id)

    if network == "trc20":
        address  = USDT_TRC20 or "⚠️ Not configured"
        net_name = "🔵 <b>USDT TRC20 (TRON)</b>"
        net_warn = t("warning_trc20", lang)
    else:
        address  = USDT_BEP20 or "⚠️ Not configured"
        net_name = "🟡 <b>USDT BEP20 (BSC)</b>"
        net_warn = t("warning_bep20", lang)

    if lang == "es":
        auto_note = (
            "🤖 <b>El pago se monitorea automáticamente.</b>\n"
            "Cuando detectemos tu transferencia, el pedido se confirma solo — "
            "¡no necesitas enviar captura!"
        )
        exact_label = "Envía EXACTAMENTE"
    else:
        auto_note = (
            "🤖 <b>Payment is monitored automatically.</b>\n"
            "Once we detect your transfer, the order confirms itself — "
            "no need to send a screenshot!"
        )
        exact_label = "Send EXACTLY"

    qty_label  = f" x{qty}" if qty > 1 else ""
    disc_label = (f" <i>(-{int(disc_rate*100)}%)</i>" if disc_rate > 0 else "")
    text = (
        f"📋 <b>{'Order' if lang=='en' else 'Pedido'} #{order_id}</b>\n\n"
        f"🛒 {svc['emoji']} <b>{svc['name']}{qty_label}</b>{disc_label}\n"
        f"💳 {net_name}\n\n"
        f"📤 <b>{'Address' if lang=='en' else 'Dirección'}:</b>\n"
        f"<code>{address}</code>\n\n"
        f"💵 <b>{exact_label}: <u>${pay_amount:.4f} USDT</u></b>\n"
        f"⚠️ <b>{'Se requiere el monto EXACTO — cualquier otro monto NO será aprobado automáticamente.' if lang=='es' else 'EXACT amount required — any other amount will NOT be approved automatically.'}</b>\n\n"
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

    # Save the instruction message ID so it can be deleted on payment/timeout
    await db.save_instruction_message(
        order_id,
        chat_id=query.message.chat_id,
        msg_id=query.message.message_id,
    )

    # Launch background blockchain monitor (30-minute window for crypto)
    asyncio.create_task(monitor_crypto_payment(
        bot=context.bot,
        order_id=order_id,
        network=network,
        expected_amount=pay_amount,
        user_id=query.from_user.id,
        service_name=svc["name"],
        lang=lang,
        qty=qty,
        timeout_seconds=1800,
    ))


# ── Receive payer Binance ID and show payment instructions ────────────────────

async def receive_payer_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Conversation step: user sends their Binance Pay ID → show payment details."""
    payer_id   = update.message.text.strip()
    order_id   = context.user_data.get("bp_order_id")
    service_id = context.user_data.get("bp_service_id")
    lang       = context.user_data.get("bp_lang", "en")
    item_type  = context.user_data.get("bp_item_type", "service")
    qty        = context.user_data.get("bp_qty", 1)

    if not order_id:
        await update.message.reply_text("❌ Session expired. Please start again.")
        return ConversationHandler.END

    # Validate — must be at least 5 chars (Binance IDs are numeric, 6-12 digits)
    if len(payer_id) < 5 or not any(c.isdigit() for c in payer_id):
        lang_err = ("⚠️ That doesn't look like a valid Binance Pay ID. "
                    "It should be a numeric ID (e.g. 123456789). Try again:"
                    if lang == "en" else
                    "⚠️ Eso no parece un ID de Binance Pay válido. "
                    "Debe ser un número (ej. 123456789). Intenta de nuevo:")
        await update.message.reply_text(lang_err, parse_mode="HTML")
        return WAITING_PAYER_ID

    # Get service/method info
    from config import SERVICES, METHODS
    item = SERVICES.get(service_id) or METHODS.get(service_id)
    if not item:
        await update.message.reply_text("❌ Service not found.")
        return ConversationHandler.END

    from payments.binance_monitor import monitor_binance_pay_payment

    # Use exact order amount (already includes discount/qty) — no unique cents needed
    # because we verify by payer ID, so the amount is always fixed and clean.
    order = await db.get_order(order_id)
    pay_amount = round(order["amount"], 2) if order else round(item["price"], 2)

    # Save payer ID and expected amount to DB
    await db.set_order_payer(order_id, payer_id, pay_amount)

    # Build Step 2 message
    if lang == "es":
        steps = (
            "1️⃣ Abre la <b>App de Binance</b>\n"
            "2️⃣ Ve a <b>Pay</b> → <b>Enviar</b>\n"
            f"3️⃣ Busca el ID: <code>{BINANCE_PAY_ID}</code>\n"
            f"4️⃣ Envía EXACTAMENTE: <b>${pay_amount:.4f} USDT</b>\n"
            f"⚠️ <b>Se requiere el monto EXACTO — cualquier otro monto NO será aprobado automáticamente.</b>\n\n"
            "🤖 <b>¡Detectaremos tu pago automáticamente!</b>"
        )
        order_label = "Pedido"
        id_label    = "Tu Binance Pay ID"
    else:
        steps = (
            "1️⃣ Open <b>Binance App</b>\n"
            "2️⃣ Go to <b>Pay</b> → <b>Send</b>\n"
            f"3️⃣ Search by Binance ID: <code>{BINANCE_PAY_ID}</code>\n"
            f"4️⃣ Send EXACTLY: <b>${pay_amount:.4f} USDT</b>\n"
            f"⚠️ <b>EXACT amount required — any other amount will NOT be approved automatically.</b>\n\n"
            "🤖 <b>We'll detect your payment automatically!</b>"
        )
        order_label = "Order"
        id_label    = "Your Binance Pay ID"

    text = (
        f"🟠 <b>Binance Pay — {'Step 2 of 2' if lang=='en' else 'Paso 2 de 2'}</b>\n\n"
        f"✅ {id_label}: <code>{payer_id}</code>\n"
        f"🆔 {order_label}: <b>#{order_id}</b>\n\n"
        f"📲 <b>{'Send to' if lang=='en' else 'Envía a'} Binance Pay ID:</b>\n"
        f"<code>{BINANCE_PAY_ID}</code>\n\n"
        f"{steps}"
    )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup as IKM
    kb = IKM([[
        InlineKeyboardButton(
            "📸 " + ("Send proof manually" if lang=="en" else "Enviar comprobante manual"),
            callback_data=f"proof_{order_id}"
        )
    ], [
        InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"cancel_{order_id}")
    ]])

    sent = await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

    # Save the instruction message ID so it can be deleted on payment/timeout
    await db.save_instruction_message(
        order_id,
        chat_id=sent.chat_id,
        msg_id=sent.message_id,
    )

    # Launch background monitor with payer ID
    asyncio.create_task(monitor_binance_pay_payment(
        bot=context.bot,
        order_id=order_id,
        expected_amount=pay_amount,
        payer_binance_id=payer_id,
        user_id=update.effective_user.id,
        service_name=item["name"],
        lang=lang,
        qty=qty,
        timeout_seconds=900,
    ))

    # Clear context
    for k in ("bp_order_id", "bp_service_id", "bp_lang", "bp_item_type", "bp_qty"):
        context.user_data.pop(k, None)

    return ConversationHandler.END


async def initiate_balance_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: pay_balance_<service_id> — deduct credits and auto-deliver."""
    query = update.callback_query
    await query.answer()

    # service_id may contain underscores
    service_id = query.data[len("pay_balance_"):]
    svc = SERVICES.get(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    user_id = query.from_user.id
    lang    = await db.get_user_lang(user_id)

    from utils.delivery import apply_discount
    qty = context.user_data.pop("order_qty", 1)
    unit_disc, total_price, disc_rate = apply_discount(svc["price"], qty)

    # ── Re-check balance at time of purchase ──────────────────────────────────
    user         = await db.get_user(user_id)
    user_credits = float(user["credits"]) if user and user.get("credits") else 0.0

    if user_credits < total_price:
        short = total_price - user_credits
        err = (
            f"❌ Insufficient balance.\n"
            f"You have ${user_credits:.2f} but need ${total_price:.2f} "
            f"(${short:.2f} short)."
            if lang == "en" else
            f"❌ Saldo insuficiente.\n"
            f"Tienes ${user_credits:.2f} pero necesitas ${total_price:.2f} "
            f"(faltan ${short:.2f})."
        )
        await query.answer(err, show_alert=True)
        return

    # ── Deduct credits atomically before creating order ───────────────────────
    await db.use_credits(user_id, total_price)

    # ── Create order ──────────────────────────────────────────────────────────
    order_id = await db.create_order(user_id, service_id, total_price, "balance")
    await db.update_order_status(order_id, "paid", admin_note="Paid with wallet balance")

    new_credits = user_credits - total_price
    qty_label   = f" x{qty}" if qty > 1 else ""
    disc_note   = (f" (-{int(disc_rate*100)}%)" if disc_rate > 0 else "")

    # ── Auto-deliver from stock ───────────────────────────────────────────────
    from utils.delivery import auto_deliver
    stock_delivered = await auto_deliver(
        context.bot, order_id, service_id, user_id, lang, qty=qty)

    if not stock_delivered:
        # No stock — admin notified, show "pending delivery" message to user
        order    = await db.get_order(order_id)
        user_obj = await db.get_user(user_id)
        await notify_admins_new_order(context.bot, order, user_obj)

        if lang == "en":
            text = (
                f"✅ <b>Order #{order_id} placed!</b>\n\n"
                f"💳 Paid with wallet balance\n"
                f"🛒 {svc['emoji']} <b>{svc['name']}{qty_label}</b>{disc_note}\n"
                f"💵 ${total_price:.2f} USDT\n"
                f"💰 Remaining balance: <b>${new_credits:.2f} USDT</b>\n\n"
                "We'll deliver within 24 hours ⏱️"
            )
        else:
            text = (
                f"✅ <b>¡Pedido #{order_id} realizado!</b>\n\n"
                f"💳 Pagado con saldo de billetera\n"
                f"🛒 {svc['emoji']} <b>{svc['name']}{qty_label}</b>{disc_note}\n"
                f"💵 ${total_price:.2f} USDT\n"
                f"💰 Saldo restante: <b>${new_credits:.2f} USDT</b>\n\n"
                "Entregamos en menos de 24 horas ⏱️"
            )
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
        except Exception:
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))

    # ── Referral credit ───────────────────────────────────────────────────────
    from handlers.referrals import handle_first_purchase_referral
    await handle_first_purchase_referral(context.bot, user_id)


async def cancel_binance_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel while still in step 1 (before payer ID was submitted)."""
    lang     = context.user_data.pop("bp_lang", "en")
    order_id = context.user_data.pop("bp_order_id", None)   # pop BEFORE the loop
    for k in ("bp_service_id", "bp_item_type", "bp_qty"):
        context.user_data.pop(k, None)

    if order_id:
        await db.update_order_status(order_id, "cancelled", admin_note="Cancelled by user (step 1)")

    text = t("cancelled", lang)
    kb   = main_menu_kb(lang)
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)
    return ConversationHandler.END


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
    """
    Callback: cancel_<order_id>
    Cancels a pending order and returns user to main menu.
    NOTE: query.answer() is called EXACTLY ONCE to avoid Telegram double-answer error.
    """
    query    = update.callback_query
    order_id = int(query.data.split("_")[1])
    order    = await db.get_order(order_id)
    lang     = await db.get_user_lang(query.from_user.id)

    # ── Guard: order doesn't exist or belongs to someone else ────────────────
    if not order or order["user_id"] != query.from_user.id:
        await query.answer(
            "Order not found." if lang == "en" else "Pedido no encontrado.",
            show_alert=True
        )
        return

    # ── Guard: already paid or delivered ─────────────────────────────────────
    if order["status"] not in ("pending",):
        await query.answer(
            "This order can't be cancelled." if lang == "en"
            else "Este pedido ya no se puede cancelar.",
            show_alert=True
        )
        return

    # ── Cancel in DB (monitor stops itself on next poll when status != pending) ─
    await db.update_order_status(order_id, "cancelled", admin_note="Cancelled by user")

    # ── Acknowledge button press ──────────────────────────────────────────────
    await query.answer()

    # ── Show cancellation message + main menu ─────────────────────────────────
    if lang == "en":
        text = f"❌ <b>Order #{order_id} cancelled.</b>\n\nYou've been returned to the main menu."
    else:
        text = f"❌ <b>Pedido #{order_id} cancelado.</b>\n\nFuiste devuelto al menú principal."

    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
    except Exception:
        # Message might be too old to edit — send a new one
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
