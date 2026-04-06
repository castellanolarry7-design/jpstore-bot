"""
admin.py – Panel de administración
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from config import ADMIN_IDS, SERVICES
import database as db
from utils.keyboards import admin_main_kb, admin_order_kb
from utils.notifications import notify_order_delivered, notify_order_status

# Estados de conversación
WAITING_DELIVERY_INFO = 10
WAITING_BROADCAST_MSG = 11
WAITING_MSG_TO_USER   = 12


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(func):
    """Decorador que verifica si el usuario es admin."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_admin(uid):
            if update.callback_query:
                await update.callback_query.answer("🚫 Solo para administradores.", show_alert=True)
            else:
                await update.message.reply_text("🚫 No tienes permisos para usar este comando.")
            return
        return await func(update, context)
    return wrapper


# ── Comando /admin ─────────────────────────────────────────────────────────────

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "⚙️ <b>Panel de Administración</b>\n\nBienvenido, administrador."
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_main_kb())
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=admin_main_kb())


# ── Estadísticas ───────────────────────────────────────────────────────────────

@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    stats = await db.get_stats()
    text = (
        "📊 <b>Estadísticas de la Tienda</b>\n\n"
        f"👥 Usuarios registrados: <b>{stats['total_users']}</b>\n"
        f"📦 Total pedidos: <b>{stats['total_orders']}</b>\n"
        f"⏳ Pedidos pendientes: <b>{stats['pending_orders']}</b>\n"
        f"🎉 Pedidos entregados: <b>{stats['delivered_orders']}</b>\n"
        f"💰 Ingresos totales: <b>${stats['total_revenue']:.2f} USDT</b>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
        ])
    )


# ── Pedidos pendientes ─────────────────────────────────────────────────────────

@admin_only
async def admin_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    orders = await db.get_pending_orders()

    if not orders:
        await query.edit_message_text(
            "✅ No hay pedidos pendientes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
            ])
        )
        return

    # Mostrar hasta 5 pedidos por mensaje para no saturar
    for o in orders[:5]:
        svc = SERVICES.get(o["service_id"], {})
        username_str = f"@{o['username']}" if o.get("username") else f"ID: {o['user_id']}"
        text = (
            f"⏳ <b>Pedido #{o['order_id']}</b>\n"
            f"👤 {o['first_name']} ({username_str})\n"
            f"🛒 {svc.get('name', o['service_id'])}\n"
            f"💵 ${o['amount']:.2f} USDT | {o['payment_method'].upper()}\n"
            f"🧾 Comprobante: {'✅ Sí' if o.get('payment_proof') else '❌ No'}\n"
            f"📅 {o['created_at']}"
        )
        await query.message.reply_text(
            text, parse_mode="HTML",
            reply_markup=admin_order_kb(o["order_id"], o["user_id"])
        )

    await query.edit_message_text(
        f"📋 <b>{len(orders)} pedido(s) pendiente(s)</b> — mostrando los primeros 5.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
        ])
    )


# ── Aprobar pago ───────────────────────────────────────────────────────────────

@admin_only
async def admin_mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[2])
    order = await db.get_order(order_id)
    if not order:
        await query.answer("Pedido no encontrado.", show_alert=True)
        return

    await db.update_order_status(order_id, "paid", admin_note="Pago verificado por admin")
    await notify_order_status(context.bot, order["user_id"], order_id, "paid",
                              "Tu pago ha sido verificado. Pronto recibirás tus credenciales.")
    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 ENTREGAR ahora", callback_data=f"admin_deliver_{order_id}")],
            [InlineKeyboardButton("✅ Pago marcado", callback_data="noop")],
        ])
    )
    await query.message.reply_text(f"✅ Pedido #{order_id} marcado como PAGADO.")


# ── Entregar servicio ──────────────────────────────────────────────────────────

@admin_only
async def admin_deliver_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[2])
    context.user_data["deliver_order_id"] = order_id
    order = await db.get_order(order_id)
    svc = SERVICES.get(order["service_id"], {})

    await query.message.reply_text(
        f"🚀 <b>Entregar pedido #{order_id}</b>\n"
        f"Servicio: {svc.get('name', order['service_id'])}\n\n"
        "Escribe la información de acceso que se enviará al cliente\n"
        "(usuario, contraseña, link, etc.):\n\n"
        "<i>/cancelar para abortar</i>",
        parse_mode="HTML"
    )
    return WAITING_DELIVERY_INFO


async def admin_deliver_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = context.user_data.get("deliver_order_id")
    if not order_id:
        return ConversationHandler.END

    delivery_info = update.message.text.strip()
    order = await db.get_order(order_id)

    await db.update_order_status(order_id, "delivered", delivery_info=delivery_info,
                                 admin_note="Entregado por admin")
    await notify_order_delivered(context.bot, order["user_id"], order, delivery_info)

    await update.message.reply_text(
        f"🎉 <b>Pedido #{order_id} entregado!</b>\n\n"
        f"El cliente ha recibido la siguiente información:\n"
        f"<code>{delivery_info}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
        ])
    )
    context.user_data.pop("deliver_order_id", None)
    return ConversationHandler.END


# ── Cancelar pedido (admin) ────────────────────────────────────────────────────

@admin_only
async def admin_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[2])
    order = await db.get_order(order_id)
    if not order:
        await query.answer("Pedido no encontrado.", show_alert=True)
        return

    await db.update_order_status(order_id, "cancelled", admin_note="Cancelado por admin")
    await notify_order_status(context.bot, order["user_id"], order_id, "cancelled",
                              "Tu pedido fue cancelado. Contáctanos para más información.")
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"❌ Pedido #{order_id} cancelado.")


# ── Broadcast ──────────────────────────────────────────────────────────────────

@admin_only
async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📢 <b>Broadcast</b>\n\nEscribe el mensaje que quieres enviar a todos los usuarios:\n\n"
        "<i>/cancelar para abortar</i>",
        parse_mode="HTML"
    )
    return WAITING_BROADCAST_MSG


async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text.strip()
    users = await db.get_all_users()

    sent = 0
    failed = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text=f"📢 <b>Mensaje de JPStore</b>\n\n{message_text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📢 <b>Broadcast enviado</b>\n\n"
        f"✅ Enviado: {sent}\n❌ Fallido: {failed}",
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ── Usuarios ───────────────────────────────────────────────────────────────────

@admin_only
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    users = await db.get_all_users()
    text = (
        f"👥 <b>Usuarios registrados: {len(users)}</b>\n\n"
    )
    for u in users[:20]:
        username_str = f"@{u['username']}" if u.get("username") else "sin @"
        text += f"• {u['first_name']} ({username_str}) — ID: <code>{u['user_id']}</code>\n"

    if len(users) > 20:
        text += f"\n<i>...y {len(users)-20} más</i>"

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
        ])
    )


# ── Cancelar conversación ──────────────────────────────────────────────────────

async def admin_cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.", reply_markup=admin_main_kb())
    return ConversationHandler.END


# ── Noop callback (botón decorativo) ──────────────────────────────────────────

async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
