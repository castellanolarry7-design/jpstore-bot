"""
balance.py – User wallet: view balance and top-up (Recargar)
"""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from strings import t
from utils.keyboards import main_menu_kb, safe_edit
from config import BINANCE_PAY_ID

# Conversation states
WAITING_TOPUP_PAYER_ID = 30   # unique state — won't clash with other convs
WAITING_CUSTOM_TOPUP   = 31   # user types a custom amount


# ── Show Balance ──────────────────────────────────────────────────────────────

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang    = await db.get_user_lang(user_id)
    user    = await db.get_user(user_id)
    credits = float(user["credits"]) if user and user.get("credits") else 0.0

    if lang == "es":
        text = (
            f"💰 <b>Tu Billetera</b>\n\n"
            f"Saldo disponible: <b>${credits:.2f} USDT</b>\n\n"
            "Los créditos se aplican automáticamente al hacer una compra.\n"
            "Presiona <b>Recargar</b> para añadir fondos."
        )
        btn_topup = "💳 Recargar"
    else:
        text = (
            f"💰 <b>Your Wallet</b>\n\n"
            f"Available balance: <b>${credits:.2f} USDT</b>\n\n"
            "Credits are applied automatically when you make a purchase.\n"
            "Tap <b>Top Up</b> to add funds to your wallet."
        )
        btn_topup = "💳 Top Up"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_topup, callback_data="recargar")],
        [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
    ])
    await safe_edit(query, text, reply_markup=kb)


# ── Show Recargar Amount Picker ───────────────────────────────────────────────

async def show_recargar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = await db.get_user_lang(query.from_user.id)

    if lang == "es":
        text   = "💳 <b>Recargar Billetera</b>\n\nSelecciona el monto (USDT) o elige monto personalizado:"
        custom = "✏️ Monto personalizado"
    else:
        text   = "💳 <b>Top Up Wallet</b>\n\nSelect an amount (USDT) or enter a custom amount:"
        custom = "✏️ Custom amount"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 $5",  callback_data="topup_5"),
            InlineKeyboardButton("💵 $10", callback_data="topup_10"),
        ],
        [
            InlineKeyboardButton("💵 $20", callback_data="topup_20"),
            InlineKeyboardButton("💵 $50", callback_data="topup_50"),
        ],
        [InlineKeyboardButton(custom, callback_data="topup_custom")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="balance")],
    ])
    await safe_edit(query, text, reply_markup=InlineKeyboardMarkup(kb.inline_keyboard))


# ── Custom amount entry ───────────────────────────────────────────────────────

async def ask_custom_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: topup_custom — ask user to type a custom amount."""
    query = update.callback_query
    await query.answer()
    lang  = await db.get_user_lang(query.from_user.id)

    if lang == "es":
        text = (
            "✏️ <b>Monto personalizado</b>\n\n"
            "Escribe el monto en USDT que deseas recargar.\n"
            "<i>Mínimo $1.00 · Máximo $500.00</i>\n\n"
            "Ejemplo: <code>15.50</code>"
        )
    else:
        text = (
            "✏️ <b>Custom Amount</b>\n\n"
            "Type the amount in USDT you want to top up.\n"
            "<i>Minimum $1.00 · Maximum $500.00</i>\n\n"
            "Example: <code>15.50</code>"
        )

    await safe_edit(query, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "❌ " + ("Cancel" if lang == "en" else "Cancelar"),
            callback_data="recargar"
        )
    ]]))
    return WAITING_CUSTOM_TOPUP


async def receive_custom_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """MessageHandler in WAITING_CUSTOM_TOPUP — validates and shows payment picker."""
    lang = await db.get_user_lang(update.effective_user.id)

    try:
        amount = float(update.message.text.strip().replace(",", "."))
        if amount < 1.0 or amount > 500.0:
            raise ValueError
    except ValueError:
        err = ("⚠️ Invalid amount. Enter a number between $1.00 and $500.00 (e.g. 15.50)"
               if lang == "en" else
               "⚠️ Monto inválido. Ingresa un número entre $1.00 y $500.00 (ej: 15.50)")
        await update.message.reply_text(err)
        return WAITING_CUSTOM_TOPUP

    # Round to 2 decimal places
    amount = round(amount, 2)
    context.user_data["topup_amount"] = amount

    if lang == "es":
        text = (
            f"💳 <b>Recarga personalizada — ${amount:.2f} USDT</b>\n\n"
            "Elige tu método de pago:"
        )
    else:
        text = (
            f"💳 <b>Custom Top-Up — ${amount:.2f} USDT</b>\n\n"
            "Choose your payment method:"
        )

    # Format amount as string safe for callback (no trailing zeros issue)
    amt_str = f"{amount:.2f}"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 USDT TRC20 (TRON)", callback_data=f"topup_pay_trc20_{amt_str}")],
        [InlineKeyboardButton("🟡 USDT BEP20 (BSC)",  callback_data=f"topup_pay_bep20_{amt_str}")],
        [InlineKeyboardButton("🟠 Binance Pay",        callback_data=f"topup_pay_binance_{amt_str}")],
        [InlineKeyboardButton(t("btn_back", lang),     callback_data="recargar")],
    ])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    return ConversationHandler.END


# ── Select Top-Up Amount → Show Payment Method ────────────────────────────────

async def recargar_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: topup_<amount>  e.g. topup_10"""
    query = update.callback_query
    await query.answer()

    amount_str = query.data.split("_")[1]
    amount = float(amount_str)
    lang   = await db.get_user_lang(query.from_user.id)

    context.user_data["topup_amount"] = amount

    if lang == "es":
        text = f"💳 <b>Recarga — ${amount:.2f} USDT</b>\n\nElige tu método de pago:"
    else:
        text = f"💳 <b>Top Up — ${amount:.2f} USDT</b>\n\nChoose your payment method:"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 USDT TRC20 (TRON)",  callback_data=f"topup_pay_trc20_{amount_str}")],
        [InlineKeyboardButton("🟡 USDT BEP20 (BSC)",   callback_data=f"topup_pay_bep20_{amount_str}")],
        [InlineKeyboardButton("🟠 Binance Pay",         callback_data=f"topup_pay_binance_{amount_str}")],
        [InlineKeyboardButton(t("btn_back", lang),       callback_data="recargar")],
    ])
    await safe_edit(query, text, reply_markup=kb)


# ── Initiate Top-Up Payment (TRC20 / BEP20) ──────────────────────────────────

async def initiate_topup_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: topup_pay_<network>_<amount>"""
    query = update.callback_query
    await query.answer()

    parts   = query.data.split("_")   # ['topup', 'pay', 'trc20', '10'] or ['topup','pay','trc20','15.50']
    network = parts[2]
    amount  = float(parts[3])
    user_id = query.from_user.id
    lang    = await db.get_user_lang(user_id)

    from config import USDT_TRC20, USDT_BEP20
    from payments.crypto_monitor import unique_amount, monitor_crypto_payment

    order_id   = await db.create_order(user_id, "topup", amount, network, item_type="topup")
    pay_amount = unique_amount(amount, order_id)

    if network == "trc20":
        address  = USDT_TRC20 or "⚠️ Not configured"
        net_name = "🔵 <b>USDT TRC20 (TRON)</b>"
        net_warn = t("warning_trc20", lang)
    else:
        address  = USDT_BEP20 or "⚠️ Not configured"
        net_name = "🟡 <b>USDT BEP20 (BSC)</b>"
        net_warn = t("warning_bep20", lang)

    if lang == "es":
        text = (
            f"📋 <b>Recarga #{order_id}</b>\n\n"
            f"💰 Monto: <b>${pay_amount:.4f} USDT</b>\n"
            f"💳 {net_name}\n\n"
            f"📤 <b>Envía a:</b>\n<code>{address}</code>\n\n"
            f"💵 <b>EXACTAMENTE: <u>${pay_amount:.4f} USDT</u></b>\n"
            f"⚠️ <b>Se requiere monto EXACTO.</b>\n\n"
            f"{net_warn}\n\n"
            "🤖 <b>¡Pago detectado automáticamente — créditos añadidos al instante!</b>"
        )
    else:
        text = (
            f"📋 <b>Top-Up Order #{order_id}</b>\n\n"
            f"💰 Amount: <b>${pay_amount:.4f} USDT</b>\n"
            f"💳 {net_name}\n\n"
            f"📤 <b>Send to address:</b>\n<code>{address}</code>\n\n"
            f"💵 <b>Send EXACTLY: <u>${pay_amount:.4f} USDT</u></b>\n"
            f"⚠️ <b>EXACT amount required.</b>\n\n"
            f"{net_warn}\n\n"
            "🤖 <b>Payment detected automatically — credits added instantly!</b>"
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📸 " + ("Send proof manually" if lang == "en" else "Enviar comprobante manual"),
            callback_data=f"proof_{order_id}"
        )],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"cancel_{order_id}")],
    ])
    await safe_edit(query, text, reply_markup=kb)

    await db.save_instruction_message(order_id, chat_id=query.message.chat_id,
                                       msg_id=query.message.message_id)

    asyncio.create_task(monitor_crypto_payment(
        bot=context.bot, order_id=order_id, network=network,
        expected_amount=pay_amount, user_id=user_id,
        service_name=f"Top-Up ${amount:.2f}", lang=lang, qty=1, timeout_seconds=900,
    ))


# ── Initiate Top-Up via Binance Pay (asks payer ID) ──────────────────────────

async def initiate_topup_binance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: topup_pay_binance_<amount> — asks for payer Binance ID."""
    query = update.callback_query
    await query.answer()

    parts  = query.data.split("_")   # ['topup', 'pay', 'binance', '10'] or decimal
    amount = float(parts[3])
    user_id = query.from_user.id
    lang    = await db.get_user_lang(user_id)

    order_id = await db.create_order(user_id, "topup", amount, "binance_pay", item_type="topup")
    context.user_data["topup_bp_order_id"] = order_id
    context.user_data["topup_bp_amount"]   = amount
    context.user_data["topup_bp_lang"]     = lang

    if lang == "es":
        msg = (
            f"🟠 <b>Recarga Binance Pay — Paso 1 de 2</b>\n\n"
            f"💰 Monto: <b>${amount:.2f} USDT</b>\n\n"
            "Envíanos <b>tu ID de Binance Pay</b>.\n\n"
            "📍 <i>Binance App → Pay → Mi QR → número bajo el código QR</i>"
        )
    else:
        msg = (
            f"🟠 <b>Binance Pay Top-Up — Step 1 of 2</b>\n\n"
            f"💰 Amount: <b>${amount:.2f} USDT</b>\n\n"
            "Please send us <b>your Binance Pay ID</b>.\n\n"
            "📍 <i>Binance App → Pay → My QR → number below the QR code</i>"
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

    pay_amount = round(amount, 2)
    await db.set_order_payer(order_id, payer_id, pay_amount)

    if lang == "es":
        steps = (
            "1️⃣ Abre <b>Binance App</b>\n"
            "2️⃣ Ve a <b>Pay → Enviar</b>\n"
            f"3️⃣ Busca el ID: <code>{BINANCE_PAY_ID}</code>\n"
            f"4️⃣ Envía EXACTAMENTE: <b>${pay_amount:.4f} USDT</b>\n"
            "⚠️ <b>Monto EXACTO requerido.</b>\n\n"
            "🤖 <b>¡Créditos añadidos al instante!</b>"
        )
    else:
        steps = (
            "1️⃣ Open <b>Binance App</b>\n"
            "2️⃣ Go to <b>Pay → Send</b>\n"
            f"3️⃣ Search Binance ID: <code>{BINANCE_PAY_ID}</code>\n"
            f"4️⃣ Send EXACTLY: <b>${pay_amount:.4f} USDT</b>\n"
            "⚠️ <b>EXACT amount required.</b>\n\n"
            "🤖 <b>Credits added instantly!</b>"
        )

    text = (
        f"🟠 <b>Binance Pay — {'Step 2 of 2' if lang=='en' else 'Paso 2 de 2'}</b>\n\n"
        f"✅ {'Your Binance Pay ID' if lang=='en' else 'Tu ID'}: <code>{payer_id}</code>\n"
        f"💰 {'Top-Up' if lang=='en' else 'Recarga'} <b>#{order_id}</b>\n\n"
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
    await db.save_instruction_message(order_id, chat_id=sent.chat_id, msg_id=sent.message_id)

    asyncio.create_task(monitor_binance_pay_payment(
        bot=context.bot, order_id=order_id, expected_amount=pay_amount,
        payer_binance_id=payer_id, user_id=update.effective_user.id,
        service_name=f"Top-Up ${amount:.2f}", lang=lang, qty=1, timeout_seconds=900,
    ))

    for k in ("topup_bp_order_id", "topup_bp_amount", "topup_bp_lang"):
        context.user_data.pop(k, None)
    return ConversationHandler.END


async def cancel_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang     = context.user_data.pop("topup_bp_lang", "en")
    order_id = context.user_data.pop("topup_bp_order_id", None)
    context.user_data.pop("topup_bp_amount", None)
    if order_id:
        await db.update_order_status(order_id, "cancelled",
                                     admin_note="Cancelled by user (topup step 1)")
    text = t("cancelled", lang)
    kb   = main_menu_kb(lang)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)
    return ConversationHandler.END
