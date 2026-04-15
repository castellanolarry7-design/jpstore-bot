"""
balance.py – User wallet: view balance and top-up (Recargar)
"""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from strings import t
from utils.keyboards import main_menu_kb
from config import BINANCE_PAY_ID

# Conversation state
WAITING_TOPUP_PAYER_ID = 30   # unique state — won't clash with other convs

# Top-up amounts available
TOPUP_AMOUNTS = [5.0, 10.0, 20.0, 50.0]


# ── Show Balance ──────────────────────────────────────────────────────────────

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang    = await db.get_user_lang(user_id)
    user    = await db.get_user(user_id)
    credits = float(user["credits"]) if user and user.get("credits") else 0.0

    if lang == "en":
        text = (
            f"💰 <b>Your Wallet</b>\n\n"
            f"Available balance: <b>${credits:.2f} USDT</b>\n\n"
            "Credits are applied automatically when you make a purchase.\n"
            "Tap <b>Top Up</b> to add funds to your wallet."
        )
        btn_topup = "💳 Top Up"
        btn_home  = t("btn_home", lang)
    else:
        text = (
            f"💰 <b>Tu Billetera</b>\n\n"
            f"Saldo disponible: <b>${credits:.2f} USDT</b>\n\n"
            "Los créditos se aplican automáticamente al hacer una compra.\n"
            "Presiona <b>Recargar</b> para añadir fondos."
        )
        btn_topup = "💳 Recargar"
        btn_home  = t("btn_home", lang)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_topup, callback_data="recargar")],
        [InlineKeyboardButton(btn_home,  callback_data="home")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


# ── Show Recargar Amount Picker ───────────────────────────────────────────────

async def show_recargar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = await db.get_user_lang(query.from_user.id)

    if lang == "en":
        text = (
            "💳 <b>Top Up Wallet</b>\n\n"
            "Select the amount you want to add to your wallet (USDT):"
        )
    else:
        text = (
            "💳 <b>Recargar Billetera</b>\n\n"
            "Selecciona el monto que deseas agregar a tu billetera (USDT):"
        )

    amount_buttons = [
        [
            InlineKeyboardButton(f"💵 $5.00",  callback_data="topup_5"),
            InlineKeyboardButton(f"💵 $10.00", callback_data="topup_10"),
        ],
        [
            InlineKeyboardButton(f"💵 $20.00", callback_data="topup_20"),
            InlineKeyboardButton(f"💵 $50.00", callback_data="topup_50"),
        ],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="balance")],
    ]
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(amount_buttons)
    )


# ── Select Top-Up Amount → Show Payment Method ────────────────────────────────

async def recargar_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: topup_<amount>  e.g. topup_10"""
    query = update.callback_query
    await query.answer()

    amount_str = query.data.split("_")[1]
    amount = float(amount_str)
    lang   = await db.get_user_lang(query.from_user.id)

    # Store chosen amount for the next step
    context.user_data["topup_amount"] = amount

    if lang == "en":
        text = (
            f"💳 <b>Top Up — ${amount:.2f} USDT</b>\n\n"
            "Choose your payment method:"
        )
    else:
        text = (
            f"💳 <b>Recarga — ${amount:.2f} USDT</b>\n\n"
            "Elige tu método de pago:"
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 USDT TRC20 (TRON)",  callback_data=f"topup_pay_trc20_{amount_str}")],
        [InlineKeyboardButton("🟡 USDT BEP20 (BSC)",   callback_data=f"topup_pay_bep20_{amount_str}")],
        [InlineKeyboardButton("🟠 Binance Pay",         callback_data=f"topup_pay_binance_{amount_str}")],
        [InlineKeyboardButton(t("btn_back", lang),       callback_data="recargar")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


# ── Initiate Top-Up Payment (TRC20 / BEP20) ──────────────────────────────────

async def initiate_topup_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: topup_pay_<network>_<amount>"""
    query = update.callback_query
    await query.answer()

    parts   = query.data.split("_")   # ['topup', 'pay', 'trc20', '10']
    network = parts[2]
    amount  = float(parts[3])
    user_id = query.from_user.id
    lang    = await db.get_user_lang(user_id)

    from config import USDT_TRC20, USDT_BEP20
    from payments.crypto_monitor import unique_amount, monitor_crypto_payment

    # Create a topup order
    order_id = await db.create_order(
        user_id, "topup", amount, network, item_type="topup"
    )
    pay_amount = unique_amount(amount, order_id)

    if network == "trc20":
        address  = USDT_TRC20 or "⚠️ Not configured"
        net_name = "🔵 <b>USDT TRC20 (TRON)</b>"
        net_warn = t("warning_trc20", lang)
    else:
        address  = USDT_BEP20 or "⚠️ Not configured"
        net_name = "🟡 <b>USDT BEP20 (BSC)</b>"
        net_warn = t("warning_bep20", lang)

    if lang == "en":
        text = (
            f"📋 <b>Top-Up Order #{order_id}</b>\n\n"
            f"💰 Amount: <b>${pay_amount:.2f} USDT</b>\n"
            f"💳 {net_name}\n\n"
            f"📤 <b>Send to address:</b>\n"
            f"<code>{address}</code>\n\n"
            f"💵 <b>Send EXACTLY: <u>${pay_amount:.2f} USDT</u></b>\n"
            f"<i>(unique amount to track your top-up)</i>\n\n"
            f"{net_warn}\n\n"
            "🤖 <b>Payment detected automatically — credits added instantly!</b>"
        )
    else:
        text = (
            f"📋 <b>Recarga #{order_id}</b>\n\n"
            f"💰 Monto: <b>${pay_amount:.2f} USDT</b>\n"
            f"💳 {net_name}\n\n"
            f"📤 <b>Envía a la dirección:</b>\n"
            f"<code>{address}</code>\n\n"
            f"💵 <b>Envía EXACTAMENTE: <u>${pay_amount:.2f} USDT</u></b>\n"
            f"<i>(monto único para rastrear tu recarga)</i>\n\n"
            f"{net_warn}\n\n"
            "🤖 <b>¡Pago detectado automáticamente — créditos añadidos al instante!</b>"
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📸 " + ("Send proof manually" if lang == "en" else "Enviar comprobante manual"),
            callback_data=f"proof_{order_id}"
        )],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"cancel_{order_id}")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    # Save instruction message for later deletion
    await db.save_instruction_message(
        order_id,
        chat_id=query.message.chat_id,
        msg_id=query.message.message_id,
    )

    # Launch blockchain monitor
    asyncio.create_task(monitor_crypto_payment(
        bot=context.bot,
        order_id=order_id,
        network=network,
        expected_amount=pay_amount,
        user_id=user_id,
        service_name=f"Top-Up ${amount:.2f}",
        lang=lang,
        qty=1,
        timeout_seconds=900,
    ))


# ── Initiate Top-Up via Binance Pay (asks payer ID) ──────────────────────────

async def initiate_topup_binance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: topup_pay_binance_<amount> — asks for payer Binance ID."""
    query = update.callback_query
    await query.answer()

    parts  = query.data.split("_")   # ['topup', 'pay', 'binance', '10']
    amount = float(parts[3])
    user_id = query.from_user.id
    lang    = await db.get_user_lang(user_id)

    # Create the topup order now so we have an order_id
    order_id = await db.create_order(
        user_id, "topup", amount, "binance_pay", item_type="topup"
    )
    context.user_data["topup_bp_order_id"] = order_id
    context.user_data["topup_bp_amount"]   = amount
    context.user_data["topup_bp_lang"]     = lang

    if lang == "en":
        msg = (
            f"🟠 <b>Binance Pay Top-Up — Step 1 of 2</b>\n\n"
            f"💰 Amount: <b>${amount:.2f} USDT</b>\n\n"
            "Please send us <b>your Binance Pay ID</b> (numeric ID of your account).\n\n"
            "📍 <i>Binance App → Pay → My QR → number below the QR code</i>"
        )
    else:
        msg = (
            f"🟠 <b>Recarga Binance Pay — Paso 1 de 2</b>\n\n"
            f"💰 Monto: <b>${amount:.2f} USDT</b>\n\n"
            "Envíanos <b>tu ID de Binance Pay</b> (número de tu cuenta).\n\n"
            "📍 <i>Binance App → Pay → Mi QR → número debajo del código QR</i>"
        )
    cancel_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ " + ("Cancel" if lang == "en" else "Cancelar"),
                             callback_data="cancel_topup")
    ]])
    await query.edit_message_text(msg, parse_mode="HTML", reply_markup=cancel_kb)
    return WAITING_TOPUP_PAYER_ID


# ── Receive Payer ID for Top-Up Binance Pay ───────────────────────────────────

async def receive_topup_payer_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    payer_id = update.message.text.strip()
    order_id = context.user_data.get("topup_bp_order_id")
    amount   = context.user_data.get("topup_bp_amount", 0.0)
    lang     = context.user_data.get("topup_bp_lang", "en")

    if not order_id:
        await update.message.reply_text("❌ Session expired. Please start again.")
        return ConversationHandler.END

    if len(payer_id) < 5 or not any(c.isdigit() for c in payer_id):
        err = ("⚠️ That doesn't look like a valid Binance Pay ID. Try again:"
               if lang == "en" else
               "⚠️ Eso no parece un ID de Binance Pay válido. Intenta de nuevo:")
        await update.message.reply_text(err)
        return WAITING_TOPUP_PAYER_ID

    from payments.binance_monitor import monitor_binance_pay_payment

    # Use exact top-up amount — payer ID verification means no unique cents needed
    pay_amount = round(amount, 2)
    await db.set_order_payer(order_id, payer_id, pay_amount)

    if lang == "en":
        steps = (
            "1️⃣ Open <b>Binance App</b>\n"
            "2️⃣ Go to <b>Pay → Send</b>\n"
            f"3️⃣ Search Binance ID: <code>{BINANCE_PAY_ID}</code>\n"
            f"4️⃣ Send EXACTLY: <b>${pay_amount:.2f} USDT</b>\n\n"
            "🤖 <b>We'll detect it automatically and add credits instantly!</b>"
        )
    else:
        steps = (
            "1️⃣ Abre <b>Binance App</b>\n"
            "2️⃣ Ve a <b>Pay → Enviar</b>\n"
            f"3️⃣ Busca el ID: <code>{BINANCE_PAY_ID}</code>\n"
            f"4️⃣ Envía EXACTAMENTE: <b>${pay_amount:.2f} USDT</b>\n\n"
            "🤖 <b>¡Lo detectamos automáticamente y añadimos créditos al instante!</b>"
        )

    text = (
        f"🟠 <b>Binance Pay — {'Step 2 of 2' if lang=='en' else 'Paso 2 de 2'}</b>\n\n"
        f"✅ {'Your Binance Pay ID' if lang=='en' else 'Tu ID de Binance Pay'}: <code>{payer_id}</code>\n"
        f"💰 {'Top-Up' if lang=='en' else 'Recarga'}: <b>#{order_id}</b>\n\n"
        f"📲 <b>{'Send to' if lang=='en' else 'Envía a'} Binance Pay ID:</b>\n"
        f"<code>{BINANCE_PAY_ID}</code>\n\n"
        f"{steps}"
    )

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📸 " + ("Send proof manually" if lang == "en" else "Enviar comprobante manual"),
            callback_data=f"proof_{order_id}"
        )
    ], [
        InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"cancel_{order_id}")
    ]])

    sent = await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

    # Save instruction message
    await db.save_instruction_message(order_id, chat_id=sent.chat_id, msg_id=sent.message_id)

    # Launch Binance Pay monitor
    asyncio.create_task(monitor_binance_pay_payment(
        bot=context.bot,
        order_id=order_id,
        expected_amount=pay_amount,
        payer_binance_id=payer_id,
        user_id=update.effective_user.id,
        service_name=f"Top-Up ${amount:.2f}",
        lang=lang,
        qty=1,
        timeout_seconds=900,
    ))

    # Clear context
    for k in ("topup_bp_order_id", "topup_bp_amount", "topup_bp_lang"):
        context.user_data.pop(k, None)

    return ConversationHandler.END


async def cancel_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.pop("topup_bp_lang", "en")
    order_id = context.user_data.pop("topup_bp_order_id", None)
    context.user_data.pop("topup_bp_amount", None)
    if order_id:
        await db.update_order_status(order_id, "cancelled", admin_note="Cancelled by user (topup step 1)")
    text = t("cancelled", lang)
    kb   = main_menu_kb(lang)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)
    return ConversationHandler.END
