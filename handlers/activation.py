"""
activation.py – Credential collection flow for activation-required products.

After payment is confirmed for a product that requires account activation,
the bot collects the buyer's email, password, and optional 2FA code.
This info is sent to admins so they can activate the account manually.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from config import ADMIN_IDS

# Conversation states
WAITING_ACT_EMAIL    = 70
WAITING_ACT_PASSWORD = 71
WAITING_ACT_2FA      = 72


async def activation_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point: callback data = act_start_<order_id>
    Triggered by the button sent after payment is confirmed.
    """
    query = update.callback_query
    await query.answer()

    order_id = int(query.data[len("act_start_"):])
    context.user_data["act_order_id"] = order_id

    order = await db.get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Orden no encontrada. Contacta soporte.")
        return ConversationHandler.END

    lang = await db.get_user_lang(query.from_user.id)

    all_s = {**db.get_static_services(), **db.get_cached_db_products()}
    svc   = all_s.get(order["service_id"], {})
    name  = svc.get("name", order["service_id"])
    emoji = svc.get("emoji", "📦")

    if lang == "es":
        text = (
            f"📋 <b>Activación de cuenta</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>{name}</b>\n"
            f"🆔 Pedido #{order_id}\n\n"
            "Para activar tu servicio necesitamos acceso temporal a tu cuenta.\n\n"
            "🔒 <b>Tus datos están protegidos</b> — solo los usamos para la activación y no se guardan después.\n\n"
            "📧 <b>Paso 1/3</b> — Escribe tu <b>correo electrónico</b>:"
        )
    else:
        text = (
            f"📋 <b>Account Activation</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>{name}</b>\n"
            f"🆔 Order #{order_id}\n\n"
            "To activate your service we need temporary access to your account.\n\n"
            "🔒 <b>Your data is protected</b> — we only use it for activation and don't keep it afterward.\n\n"
            "📧 <b>Step 1/3</b> — Please send your <b>email address</b>:"
        )

    await query.edit_message_text(text, parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup([[
                                      InlineKeyboardButton("❌ Cancelar / Cancel", callback_data="act_cancel")
                                  ]]))
    return WAITING_ACT_EMAIL


async def receive_act_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    context.user_data["act_email"] = email

    lang = await db.get_user_lang(update.effective_user.id)

    if lang == "es":
        text = (
            f"✅ Email: <code>{email}</code>\n\n"
            "🔑 <b>Paso 2/3</b> — Escribe tu <b>contraseña</b>:"
        )
    else:
        text = (
            f"✅ Email: <code>{email}</code>\n\n"
            "🔑 <b>Step 2/3</b> — Send your <b>password</b>:"
        )

    await update.message.reply_text(text, parse_mode="HTML",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("❌ Cancelar / Cancel", callback_data="act_cancel")
                                    ]]))
    return WAITING_ACT_PASSWORD


async def receive_act_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text.strip()
    context.user_data["act_password"] = password

    lang = await db.get_user_lang(update.effective_user.id)

    if lang == "es":
        text = (
            "🔐 <b>Paso 3/3</b> — ¿Tienes <b>verificación en 2 pasos (2FA)</b> activada?\n\n"
            "Si sí, escribe el código de respaldo o indica cómo enviártelo.\n"
            "Si no tienes 2FA, pulsa <b>Sin 2FA</b>."
        )
    else:
        text = (
            "🔐 <b>Step 3/3</b> — Do you have <b>2-Step Verification (2FA)</b> enabled?\n\n"
            "If yes, send your backup code or explain how to send it to you.\n"
            "If you don't have 2FA, tap <b>No 2FA</b>."
        )

    await update.message.reply_text(text, parse_mode="HTML",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton(
                                            "✅ Sin 2FA / No 2FA",
                                            callback_data="act_no2fa"
                                        )],
                                        [InlineKeyboardButton("❌ Cancelar / Cancel", callback_data="act_cancel")],
                                    ]))
    return WAITING_ACT_2FA


async def receive_act_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User sent a 2FA code as text."""
    twofa    = update.message.text.strip()
    order_id = context.user_data.get("act_order_id")
    email    = context.user_data.get("act_email", "")
    password = context.user_data.get("act_password", "")
    lang     = await db.get_user_lang(update.effective_user.id)

    return await _finish_activation(update, context, order_id, email, password, twofa, lang)


async def skip_act_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User pressed 'No 2FA' button."""
    query = update.callback_query
    await query.answer()

    order_id = context.user_data.get("act_order_id")
    email    = context.user_data.get("act_email", "")
    password = context.user_data.get("act_password", "")
    lang     = await db.get_user_lang(query.from_user.id)

    return await _finish_activation(update, context, order_id, email, password, "", lang,
                                    via_query=query)


async def cancel_activation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User cancelled the activation flow."""
    for k in ("act_order_id", "act_email", "act_password"):
        context.user_data.pop(k, None)

    lang = await db.get_user_lang(update.effective_user.id)
    text = ("❌ Activación cancelada. Contáctanos si necesitas ayuda."
            if lang == "es" else
            "❌ Activation cancelled. Contact support if you need help.")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
    elif update.message:
        await update.message.reply_text(text)

    return ConversationHandler.END


# ── Internal helper ───────────────────────────────────────────────────────────

async def _finish_activation(
    update, context, order_id, email, password, twofa, lang, *, via_query=None
) -> int:
    """Store credentials, notify admins, confirm to user."""
    # Clear user_data
    for k in ("act_order_id", "act_email", "act_password"):
        context.user_data.pop(k, None)

    if not order_id:
        text = "❌ Sesión expirada. Contacta soporte." if lang == "es" else "❌ Session expired. Contact support."
        if via_query:
            await via_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END

    # Save to DB
    await db.save_activation_info(order_id, email, password, twofa)

    # Build admin notification
    order   = await db.get_order(order_id)
    user_id = order["user_id"] if order else update.effective_user.id
    all_s   = {**db.get_static_services(), **db.get_cached_db_products()}
    svc     = all_s.get(order["service_id"], {}) if order else {}
    name    = svc.get("name", order["service_id"] if order else "?")
    emoji   = svc.get("emoji", "📦")

    twofa_line = f"🔐 2FA: <code>{twofa}</code>" if twofa else "🔐 2FA: <i>Sin 2FA / No 2FA</i>"

    admin_text = (
        f"🔑 <b>CREDENCIALES DE ACTIVACIÓN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 {emoji} <b>{name}</b>\n"
        f"🆔 Pedido #{order_id}\n"
        f"👤 User ID: <code>{user_id}</code>\n\n"
        f"📧 Email: <code>{email}</code>\n"
        f"🔑 Password: <code>{password}</code>\n"
        f"{twofa_line}\n\n"
        "⚡ Activa la cuenta y usa <b>ENTREGAR</b> para enviarle el link de reclamación."
    )

    from utils.keyboards import admin_order_kb
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="HTML",
                reply_markup=admin_order_kb(order_id, user_id)
            )
        except Exception as e:
            print(f"[Activation] Could not notify admin {admin_id}: {e}")

    # Confirm to user
    if lang == "es":
        confirm = (
            f"✅ <b>¡Datos recibidos!</b>\n\n"
            f"🆔 Pedido #{order_id}\n\n"
            "Estamos activando tu cuenta. Recibirás el link de reclamación en breve. ⚡\n\n"
            "📩 Si tienes dudas, contacta soporte."
        )
    else:
        confirm = (
            f"✅ <b>Data received!</b>\n\n"
            f"🆔 Order #{order_id}\n\n"
            "We're activating your account. You'll receive the claim link shortly. ⚡\n\n"
            "📩 Questions? Contact support."
        )

    if via_query:
        await via_query.edit_message_text(confirm, parse_mode="HTML")
    else:
        await update.message.reply_text(confirm, parse_mode="HTML")

    return ConversationHandler.END
