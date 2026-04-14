"""
admin.py – Panel de administración
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from config import ADMIN_IDS, SERVICES, METHODS, ADMIN_PASSWORD
import database as db
from utils.keyboards import admin_main_kb, admin_order_kb
from utils.notifications import notify_order_delivered, notify_order_status

# Estados de conversación
WAITING_DELIVERY_INFO  = 10
WAITING_BROADCAST_MSG  = 11
WAITING_MSG_TO_USER    = 12
WAITING_STOCK_PASSWORD = 20   # hidden stock commands
WAITING_STOCK_ITEMS    = 21


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


# ══════════════════════════════════════════════════════════════════════════════
# STOCK COMMANDS (hidden — not listed anywhere, password-protected)
# ══════════════════════════════════════════════════════════════════════════════

# ── /addstock <service_id> ────────────────────────────────────────────────────

async def cmd_addstock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /addstock <service_id>"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    args = context.args
    if not args:
        all_ids = list(SERVICES.keys()) + list(METHODS.keys())
        await update.message.reply_text(
            "⚠️ Uso: <code>/addstock &lt;service_id&gt;</code>\n\n"
            "IDs disponibles:\n" + "\n".join(f"  • <code>{i}</code>" for i in all_ids),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    service_id = args[0].strip()
    svc = SERVICES.get(service_id) or METHODS.get(service_id)
    if not svc:
        await update.message.reply_text(
            f"❌ ID <code>{service_id}</code> no encontrado.",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    context.user_data["stock_service_id"] = service_id
    context.user_data["stock_service_name"] = svc["name"]
    context.user_data["stock_action"] = "add"

    await update.message.reply_text(
        "🔐 <b>Comando protegido</b>\n\nIngresa la contraseña de admin:",
        parse_mode="HTML"
    )
    return WAITING_STOCK_PASSWORD


# ── /stock  (ver niveles) ─────────────────────────────────────────────────────

async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /stock — show all stock levels"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    context.user_data["stock_action"] = "view"
    await update.message.reply_text(
        "🔐 <b>Comando protegido</b>\n\nIngresa la contraseña de admin:",
        parse_mode="HTML"
    )
    return WAITING_STOCK_PASSWORD


# ── Verificar contraseña ───────────────────────────────────────────────────────

async def stock_check_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validates the admin password."""
    entered = update.message.text.strip()

    # Delete the password message immediately for security
    try:
        await update.message.delete()
    except Exception:
        pass

    if not ADMIN_PASSWORD or entered != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Contraseña incorrecta.")
        context.user_data.clear()
        return ConversationHandler.END

    action = context.user_data.get("stock_action")

    if action == "view":
        # Show stock levels right away
        levels = await db.get_stock_levels()
        if not levels:
            await update.message.reply_text("📦 No hay stock registrado aún.")
            return ConversationHandler.END

        lines = ["📦 <b>Stock disponible</b>\n"]
        for row in levels:
            svc = SERVICES.get(row["service_id"]) or METHODS.get(row["service_id"]) or {}
            name = svc.get("name", row["service_id"])
            avail = row["available"]
            icon  = "🟢" if avail > 3 else ("🟡" if avail > 0 else "🔴")
            lines.append(
                f"{icon} <b>{name}</b> — "
                f"{avail} disponibles / {row['delivered']} entregadas"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        context.user_data.clear()
        return ConversationHandler.END

    elif action == "add":
        service_id   = context.user_data.get("stock_service_id")
        service_name = context.user_data.get("stock_service_name")
        current      = await db.get_stock_level(service_id)
        await update.message.reply_text(
            f"✅ <b>Acceso concedido</b>\n\n"
            f"Servicio: <b>{service_name}</b>\n"
            f"Stock actual: <b>{current}</b> unidades disponibles\n\n"
            "Envía las credenciales, <b>una por línea</b>:\n"
            "<code>usuario@email.com:contraseña</code>\n"
            "<code>usuario2@email.com:contraseña2</code>\n\n"
            "<i>/cancelar para abortar</i>",
            parse_mode="HTML"
        )
        return WAITING_STOCK_ITEMS

    context.user_data.clear()
    return ConversationHandler.END


# ── Recibir los ítems de stock ─────────────────────────────────────────────────

async def stock_receive_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the stock items (one per line) and saves to DB."""
    service_id   = context.user_data.get("stock_service_id")
    service_name = context.user_data.get("stock_service_name", service_id)

    if not service_id:
        return ConversationHandler.END

    raw_lines = update.message.text.strip().splitlines()
    items = [line.strip() for line in raw_lines if line.strip()]

    if not items:
        await update.message.reply_text(
            "⚠️ No se detectaron ítems. Envía uno por línea."
        )
        return WAITING_STOCK_ITEMS

    added = await db.add_stock_items(service_id, items)
    total = await db.get_stock_level(service_id)

    await update.message.reply_text(
        f"✅ <b>{added} credencial(es) agregada(s)</b>\n\n"
        f"Servicio: <b>{service_name}</b>\n"
        f"Total disponible ahora: <b>{total}</b> unidades\n\n"
        "Puedes enviar más ahora o escribir /cancelar para terminar.",
        parse_mode="HTML"
    )
    return WAITING_STOCK_ITEMS   # stay open to add more


async def stock_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("✅ Operación cancelada.")
    return ConversationHandler.END
