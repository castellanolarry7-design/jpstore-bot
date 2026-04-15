"""
admin.py – Panel de administración completo con gestión de stock
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, filters, CommandHandler,
)
from config import ADMIN_IDS, ADMIN_PASSWORD, SERVICES, METHODS
import database as db
from utils.notifications import notify_order_delivered, notify_order_status

# ── Conversation states ────────────────────────────────────────────────────────
WAITING_ADMIN_PASSWORD = 20
WAITING_DELIVERY_INFO  = 10
WAITING_BROADCAST_MSG  = 11
WAITING_STOCK_ADD_CREDS = 21   # receiving credentials after picking a service


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_authed(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True once admin has entered the password this session."""
    return context.user_data.get("admin_authed", False)


def _all_services() -> dict:
    return {**SERVICES, **METHODS}


def _svc_name(service_id: str) -> str:
    all_s = _all_services()
    svc = all_s.get(service_id, {})
    return f"{svc.get('emoji','📦')} {svc.get('name', service_id)}"


def _stock_icon(qty: int) -> str:
    if qty == 0:   return "🔴"
    if qty <= 3:   return "🟡"
    return "🟢"


# ── Main panel keyboard ────────────────────────────────────────────────────────

def _admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Pedidos pendientes",  callback_data="admin_pending"),
         InlineKeyboardButton("📊 Estadísticas",        callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Usuarios",            callback_data="admin_users"),
         InlineKeyboardButton("📢 Broadcast",           callback_data="admin_broadcast")],
        [InlineKeyboardButton("📦 Gestión de Stock",    callback_data="admin_stock")],
    ])


# ── Stock management keyboards ────────────────────────────────────────────────

def _stock_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Ver stock",           callback_data="admin_stock_view")],
        [InlineKeyboardButton("➕ Agregar credenciales", callback_data="admin_stock_add_pick")],
        [InlineKeyboardButton("🗑️ Eliminar item",       callback_data="admin_stock_del_pick")],
        [InlineKeyboardButton("◀️ Panel admin",         callback_data="admin_panel")],
    ])


async def _services_pick_kb(action: str) -> InlineKeyboardMarkup:
    """Show all services+methods as buttons for picking, with live stock count."""
    levels = await db.get_stock_levels_dict()
    rows = []
    for sid, svc in _all_services().items():
        qty  = levels.get(sid, 0)
        icon = _stock_icon(qty)
        label = f"{icon} {svc['emoji']} {svc['name']} ({qty})"
        rows.append([InlineKeyboardButton(label, callback_data=f"{action}_{sid}")])
    rows.append([InlineKeyboardButton("◀️ Volver", callback_data="admin_stock")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════════════════════
# /admin ENTRY — password gate
# ══════════════════════════════════════════════════════════════════════════════

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /admin command."""
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 No tienes permisos.")
        return ConversationHandler.END

    if is_authed(context):
        await _show_panel(update, context)
        return ConversationHandler.END

    # Not yet authenticated — ask password
    await update.message.reply_text(
        "🔐 <b>Panel Admin — JPStore</b>\n\n"
        "Ingresa la contraseña de administrador:",
        parse_mode="HTML"
    )
    return WAITING_ADMIN_PASSWORD


async def admin_check_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the admin password attempt."""
    entered = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    if not ADMIN_PASSWORD or entered != ADMIN_PASSWORD:
        await update.message.reply_text(
            "❌ <b>Contraseña incorrecta.</b>\n"
            "Usa /admin para intentar de nuevo.",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    context.user_data["admin_authed"] = True
    await _show_panel(update, context)
    return ConversationHandler.END


async def _show_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "⚙️ <b>Panel de Administración</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bienvenido. Elige una opción:"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=_admin_main_kb())
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=_admin_main_kb())


# ── Callback: admin_panel (show panel from button) ────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("🚫 Solo admins.", show_alert=True)
        return
    if not is_authed(context):
        await query.answer("🔐 Sesión expirada. Usa /admin.", show_alert=True)
        return
    await query.edit_message_text(
        "⚙️ <b>Panel de Administración</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bienvenido. Elige una opción:",
        parse_mode="HTML",
        reply_markup=_admin_main_kb()
    )


# ══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS
# ══════════════════════════════════════════════════════════════════════════════

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    stats = await db.get_stats()
    text = (
        "📊 <b>Estadísticas de la Tienda</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
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


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS PENDIENTES
# ══════════════════════════════════════════════════════════════════════════════

async def admin_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    orders = await db.get_pending_orders()
    if not orders:
        await query.edit_message_text(
            "✅ No hay pedidos pendientes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
            ])
        )
        return

    for o in orders[:5]:
        svc = _all_services().get(o["service_id"], {})
        username_str = f"@{o['username']}" if o.get("username") else f"ID:{o['user_id']}"
        text = (
            f"⏳ <b>Pedido #{o['order_id']}</b>\n"
            f"👤 {o['first_name']} ({username_str})\n"
            f"🛒 {svc.get('name', o['service_id'])}\n"
            f"💵 ${o['amount']:.2f} | {o['payment_method'].upper()}\n"
            f"🧾 Comprobante: {'✅' if o.get('payment_proof') else '❌'}\n"
            f"📅 {o['created_at']}"
        )
        await query.message.reply_text(
            text, parse_mode="HTML",
            reply_markup=_admin_order_kb(o["order_id"], o["user_id"])
        )

    await query.edit_message_text(
        f"📋 <b>{len(orders)} pedido(s) pendiente(s)</b> — primeros 5.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
        ])
    )


def _admin_order_kb(order_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Marcar PAGADO",  callback_data=f"admin_paid_{order_id}"),
         InlineKeyboardButton("🚀 ENTREGAR",       callback_data=f"admin_deliver_{order_id}")],
        [InlineKeyboardButton("❌ Cancelar",        callback_data=f"admin_cancel_{order_id}")],
    ])


async def admin_mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

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
            [InlineKeyboardButton("✅ Pago marcado",   callback_data="noop")],
        ])
    )


async def admin_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    order_id = int(query.data.split("_")[2])
    order = await db.get_order(order_id)
    if not order:
        return
    await db.update_order_status(order_id, "cancelled", admin_note="Cancelado por admin")
    await notify_order_status(context.bot, order["user_id"], order_id, "cancelled",
                              "Tu pedido fue cancelado. Contáctanos para más información.")
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"❌ Pedido #{order_id} cancelado.")


# ── Deliver ────────────────────────────────────────────────────────────────────

async def admin_deliver_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return ConversationHandler.END

    order_id = int(query.data.split("_")[2])
    order = await db.get_order(order_id)
    svc   = _all_services().get(order["service_id"], {})
    context.user_data["deliver_order_id"] = order_id

    await query.message.reply_text(
        f"🚀 <b>Entregar pedido #{order_id}</b>\n"
        f"Servicio: {svc.get('name', order['service_id'])}\n\n"
        "Escribe la información de acceso que se enviará al cliente:\n"
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
    await db.update_order_status(order_id, "delivered",
                                 delivery_info=delivery_info, admin_note="Entregado por admin")
    await notify_order_delivered(context.bot, order["user_id"], order, delivery_info)
    await update.message.reply_text(
        f"🎉 <b>Pedido #{order_id} entregado!</b>\n\n"
        f"<code>{delivery_info}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
        ])
    )
    context.user_data.pop("deliver_order_id", None)
    return ConversationHandler.END


# ── Broadcast ──────────────────────────────────────────────────────────────────

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return ConversationHandler.END

    await query.message.reply_text(
        "📢 <b>Broadcast</b>\n\n"
        "Escribe el mensaje para todos los usuarios:\n"
        "<i>/cancelar para abortar</i>",
        parse_mode="HTML"
    )
    return WAITING_BROADCAST_MSG


async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text.strip()
    users = await db.get_all_users()
    sent = failed = 0
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
        f"📢 <b>Broadcast enviado</b>\n✅ {sent} | ❌ {failed}",
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ── Usuarios ───────────────────────────────────────────────────────────────────

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    users = await db.get_all_users()
    text  = f"👥 <b>Usuarios registrados: {len(users)}</b>\n\n"
    for u in users[:20]:
        ustr = f"@{u['username']}" if u.get("username") else "sin @"
        text += f"• {u['first_name']} ({ustr}) — <code>{u['user_id']}</code>\n"
    if len(users) > 20:
        text += f"\n<i>...y {len(users)-20} más</i>"

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
        ])
    )


# ══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE STOCK — Panel completo
# ══════════════════════════════════════════════════════════════════════════════

async def admin_stock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main stock submenu."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        await query.answer("🔐 Sesión expirada. Usa /admin.", show_alert=True)
        return

    levels  = await db.get_all_stock_summary()
    total_a = sum(r["available"] for r in levels)
    total_d = sum(r["delivered"] for r in levels)

    lines = ["📦 <b>Gestión de Stock</b>\n━━━━━━━━━━━━━━━━━━━━━━━"]
    if levels:
        for row in levels:
            icon = _stock_icon(row["available"])
            lines.append(
                f"{icon} <b>{_svc_name(row['service_id'])}</b>\n"
                f"   ├ Disponibles: <b>{row['available']}</b>\n"
                f"   └ Entregadas: {row['delivered']}"
            )
        lines.append(f"\n<i>Total disponible: {total_a} | Total entregado: {total_d}</i>")
    else:
        lines.append("\n<i>No hay stock registrado aún.</i>")

    await query.edit_message_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=_stock_main_kb()
    )


# ── Ver items de un servicio ───────────────────────────────────────────────────

async def admin_stock_view_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show service picker to view items."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    await query.edit_message_text(
        "📊 <b>Ver Stock — Elige un servicio:</b>",
        parse_mode="HTML",
        reply_markup=await _services_pick_kb("admin_stock_items")
    )


async def admin_stock_view_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all available items for a specific service."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    service_id = query.data.replace("admin_stock_items_", "", 1)
    items      = await db.get_stock_items(service_id, limit=30)
    delivered  = await db.get_stock_delivered(service_id, limit=5)
    svc_name   = _svc_name(service_id)

    lines = [f"📦 <b>{svc_name}</b>\n━━━━━━━━━━━━━━━━━━━━━━━"]

    if items:
        lines.append(f"✅ <b>Disponibles ({len(items)}):</b>")
        for item in items:
            # Mask content partially for security (show first 20 chars)
            content_preview = item["content"][:40] + ("…" if len(item["content"]) > 40 else "")
            lines.append(f"  <code>#{item['id']}</code> → {content_preview}")
    else:
        lines.append("🔴 <b>Sin stock disponible</b>")

    if delivered:
        lines.append(f"\n📤 <b>Últimas entregadas ({len(delivered)}):</b>")
        for item in delivered:
            content_preview = item["content"][:30] + "…"
            lines.append(
                f"  ✓ <code>#{item['id']}</code> → {content_preview}"
                f" (pedido #{item['order_id']})"
            )

    # Deletion row per item
    del_buttons = []
    for item in items[:10]:
        del_buttons.append(
            InlineKeyboardButton(
                f"🗑️ #{item['id']}",
                callback_data=f"admin_stock_delitem_{item['id']}"
            )
        )

    kb_rows = []
    # Group delete buttons in pairs
    for i in range(0, len(del_buttons), 3):
        kb_rows.append(del_buttons[i:i+3])

    kb_rows += [
        [InlineKeyboardButton(f"➕ Agregar a {svc_name[:20]}", callback_data=f"admin_stock_add_{service_id}")],
        [InlineKeyboardButton("◀️ Ver todos", callback_data="admin_stock_view"),
         InlineKeyboardButton("📦 Stock", callback_data="admin_stock")],
    ]

    await query.edit_message_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb_rows)
    )


# ── Agregar credenciales ───────────────────────────────────────────────────────

async def admin_stock_add_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show service picker for adding stock."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    await query.edit_message_text(
        "➕ <b>Agregar Stock — Elige el servicio:</b>",
        parse_mode="HTML",
        reply_markup=await _services_pick_kb("admin_stock_add")
    )


async def admin_stock_add_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User picked a service → ask for credentials."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return ConversationHandler.END

    service_id = query.data.replace("admin_stock_add_", "", 1)
    svc_name   = _svc_name(service_id)
    current    = await db.get_stock_level(service_id)

    context.user_data["stock_add_service_id"]   = service_id
    context.user_data["stock_add_service_name"] = svc_name

    await query.edit_message_text(
        f"➕ <b>Agregar credenciales — {svc_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Stock actual: <b>{current}</b> disponibles\n\n"
        "Envía las credenciales <b>una por línea</b>:\n\n"
        "<code>usuario@email.com:contraseña</code>\n"
        "<code>usuario2@email.com:contraseña2</code>\n"
        "<code>usuario3@email.com:contraseña3</code>\n\n"
        "Puedes pegar todas a la vez. Envía /cancelar para abortar.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data="admin_stock")]
        ])
    )
    return WAITING_STOCK_ADD_CREDS


async def admin_stock_receive_creds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives pasted credentials and saves to stock."""
    service_id = context.user_data.get("stock_add_service_id")
    svc_name   = context.user_data.get("stock_add_service_name", service_id)

    if not service_id:
        await update.message.reply_text("❌ Sesión perdida. Vuelve al panel.")
        return ConversationHandler.END

    raw_lines = update.message.text.strip().splitlines()
    items = [line.strip() for line in raw_lines if line.strip()]

    if not items:
        await update.message.reply_text("⚠️ No se detectaron ítems. Envía uno por línea.")
        return WAITING_STOCK_ADD_CREDS

    added = await db.add_stock_items(service_id, items)
    total = await db.get_stock_level(service_id)

    context.user_data.pop("stock_add_service_id", None)
    context.user_data.pop("stock_add_service_name", None)
    await update.message.reply_text(
        f"✅ <b>{added} credencial(es) guardada(s)</b>\n\n"
        f"Servicio: <b>{svc_name}</b>\n"
        f"📊 Total disponible: <b>{total}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"➕ Agregar más a {svc_name[:20]}",
                                  callback_data=f"admin_stock_add_{service_id}")],
            [InlineKeyboardButton("📊 Ver stock de este servicio",
                                  callback_data=f"admin_stock_items_{service_id}")],
            [InlineKeyboardButton("📦 Gestión de Stock", callback_data="admin_stock")],
        ])
    )
    return ConversationHandler.END   # close conversation — click "Agregar más" to reopen


async def admin_stock_add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("stock_add_service_id", None)
    context.user_data.pop("stock_add_service_name", None)
    if update.message:
        await update.message.reply_text(
            "✅ Operación cancelada.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Gestión de Stock", callback_data="admin_stock")]
            ])
        )
    return ConversationHandler.END


# ── Eliminar item ──────────────────────────────────────────────────────────────

async def admin_stock_del_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show service picker for deletion."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    await query.edit_message_text(
        "🗑️ <b>Eliminar item — Elige el servicio:</b>",
        parse_mode="HTML",
        reply_markup=await _services_pick_kb("admin_stock_delview")
    )


async def admin_stock_del_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available items for a service with delete buttons."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    service_id = query.data.replace("admin_stock_delview_", "", 1)
    items      = await db.get_stock_items(service_id, limit=20)
    svc_name   = _svc_name(service_id)

    if not items:
        await query.edit_message_text(
            f"🔴 <b>{svc_name}</b> — sin stock disponible para eliminar.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Volver", callback_data="admin_stock_del_pick")]
            ])
        )
        return

    lines = [f"🗑️ <b>Eliminar — {svc_name}</b>\n━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append("Pulsa el botón del ID que quieres eliminar:\n")
    for item in items:
        preview = item["content"][:45] + ("…" if len(item["content"]) > 45 else "")
        lines.append(f"  <code>#{item['id']}</code>  {preview}")

    del_buttons = [
        InlineKeyboardButton(f"🗑️ #{item['id']}", callback_data=f"admin_stock_delitem_{item['id']}")
        for item in items
    ]
    kb_rows = [del_buttons[i:i+3] for i in range(0, len(del_buttons), 3)]
    kb_rows.append([InlineKeyboardButton("◀️ Volver", callback_data="admin_stock_del_pick")])

    await query.edit_message_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb_rows)
    )


async def admin_stock_del_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a specific stock item by ID (confirm step)."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    item_id = int(query.data.replace("admin_stock_delitem_", "", 1))
    deleted = await db.delete_stock_item(item_id)

    if deleted:
        await query.answer(f"✅ Item #{item_id} eliminado.", show_alert=True)
        # Refresh the stock menu
        await query.edit_message_text(
            f"✅ <b>Item <code>#{item_id}</code> eliminado correctamente.</b>\n\n"
            "Vuelve al panel para seguir gestionando el stock.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Gestión de Stock", callback_data="admin_stock")]
            ])
        )
    else:
        await query.answer(
            f"❌ Item #{item_id} no encontrado o ya fue entregado.",
            show_alert=True
        )


# ══════════════════════════════════════════════════════════════════════════════
# CANCEL / NOOP helpers
# ══════════════════════════════════════════════════════════════════════════════

async def admin_cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("deliver_order_id", None)
    if update.message:
        await update.message.reply_text(
            "❌ Operación cancelada.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
            ])
        )
    return ConversationHandler.END


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()


# ── Legacy keyboard (used in other files) ─────────────────────────────────────

def admin_main_kb() -> InlineKeyboardMarkup:
    return _admin_main_kb()


def admin_order_kb(order_id: int, user_id: int) -> InlineKeyboardMarkup:
    return _admin_order_kb(order_id, user_id)


# ── Legacy /addstock and /stock commands (kept for backward compat) ───────────

async def cmd_addstock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if not is_authed(context):
        await update.message.reply_text("🔐 Usa /admin primero para autenticarte.")
        return ConversationHandler.END
    context.user_data["stock_action"] = "add"
    args = context.args
    if not args:
        kb = await _services_pick_kb("admin_stock_add")
        await update.message.reply_text("➕ Elige el servicio:", reply_markup=kb)
        return ConversationHandler.END
    service_id = args[0].strip()
    svc = _all_services().get(service_id)
    if not svc:
        await update.message.reply_text(f"❌ ID <code>{service_id}</code> no encontrado.", parse_mode="HTML")
        return ConversationHandler.END
    context.user_data["stock_add_service_id"]   = service_id
    context.user_data["stock_add_service_name"] = _svc_name(service_id)
    current = await db.get_stock_level(service_id)
    await update.message.reply_text(
        f"➕ <b>{_svc_name(service_id)}</b> — {current} disponibles.\n\n"
        "Envía las credenciales, una por línea:",
        parse_mode="HTML"
    )
    return WAITING_STOCK_ADD_CREDS


async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if not is_authed(context):
        await update.message.reply_text("🔐 Usa /admin primero para autenticarte.")
        return ConversationHandler.END
    levels = await db.get_all_stock_summary()
    if not levels:
        await update.message.reply_text("📦 No hay stock registrado.")
        return ConversationHandler.END
    lines = ["📦 <b>Stock disponible</b>\n"]
    for row in levels:
        icon = _stock_icon(row["available"])
        lines.append(f"{icon} <b>{_svc_name(row['service_id'])}</b> — {row['available']} disp.")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    return ConversationHandler.END


# old aliases
WAITING_STOCK_PASSWORD = WAITING_ADMIN_PASSWORD
WAITING_STOCK_ITEMS    = WAITING_STOCK_ADD_CREDS

async def stock_check_password(*a, **kw):
    return await admin_check_password(*a, **kw)

async def stock_receive_items(*a, **kw):
    return await admin_stock_receive_creds(*a, **kw)

async def stock_cancel(*a, **kw):
    return await admin_stock_add_cancel(*a, **kw)
