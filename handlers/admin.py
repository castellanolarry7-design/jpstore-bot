"""
admin.py – Panel de administración completo
  • Gestión de stock (agregar / ver / eliminar credenciales)
  • Gestión de productos (crear / eliminar productos dinámicos)
  • Pedidos pendientes + entrega manual
  • Estadísticas
  • Broadcast
  • Limpieza de pedidos huérfanos
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
WAITING_ADMIN_PASSWORD  = 20
WAITING_DELIVERY_INFO   = 10
WAITING_BROADCAST_MSG   = 11
WAITING_STOCK_ADD_CREDS = 21   # receiving credentials after picking a service

# Product creation states
WAITING_PROD_NAME        = 40
WAITING_PROD_EMOJI       = 41
WAITING_PROD_PRICE       = 42
WAITING_PROD_DESC_EN     = 43
WAITING_PROD_DESC_ES     = 44
WAITING_PROD_DELIVERY_EN = 45
WAITING_PROD_DELIVERY_ES = 46
WAITING_PROD_PHOTO       = 47   # optional image upload step

# Photo management state (for existing products)
WAITING_SET_PHOTO = 48

# Welcome photo state (for /setphoto command)
WAITING_WELCOME_PHOTO = 49


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_authed(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True once admin has entered the password this session."""
    return context.user_data.get("admin_authed", False)


def _all_services() -> dict:
    """Static + DB-cached products + methods."""
    return {**SERVICES, **db.get_cached_db_products(), **METHODS}


def _catalog_services() -> dict:
    """Services available in the catalog (SERVICES + DB products, not METHODS)."""
    return {**SERVICES, **db.get_cached_db_products()}


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
        [InlineKeyboardButton("🛍️ Gestionar Productos", callback_data="admin_products")],
        [InlineKeyboardButton("🧹 Limpiar pedidos viejos", callback_data="admin_cleanup")],
    ])


# ── Stock management keyboards ────────────────────────────────────────────────

def _stock_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Ver stock",            callback_data="admin_stock_view")],
        [InlineKeyboardButton("➕ Agregar credenciales", callback_data="admin_stock_add_pick")],
        [InlineKeyboardButton("🗑️ Eliminar item",        callback_data="admin_stock_del_pick")],
        [InlineKeyboardButton("◀️ Panel admin",          callback_data="admin_panel")],
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
# /weboadmin ENTRY — password gate
# ══════════════════════════════════════════════════════════════════════════════

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /weboadmin command."""
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 No tienes permisos.")
        return ConversationHandler.END

    if is_authed(context):
        await _show_panel(update, context)
        return ConversationHandler.END

    # Not yet authenticated — ask password
    await update.message.reply_text(
        "🔐 <b>Panel Admin — ReseliBot</b>\n\n"
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
            "Usa /weboadmin para intentar de nuevo.",
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
        await update.callback_query.edit_message_text(text, parse_mode="HTML",
                                                       reply_markup=_admin_main_kb())


# ── Callback: admin_panel ────────────────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("🚫 Solo admins.", show_alert=True)
        return
    if not is_authed(context):
        await query.answer("🔐 Sesión expirada. Usa /weboadmin.", show_alert=True)
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
        f"⏳ Pendientes / en pago: <b>{stats['pending_orders']}</b>\n"
        f"🎉 Pedidos entregados: <b>{stats['delivered_orders']}</b>\n\n"
        f"💰 <b>Ingresos</b>\n"
        f"   📅 Hoy:        <b>${stats.get('today_revenue', 0):.2f} USDT</b>\n"
        f"   📆 Últimos 7d: <b>${stats.get('week_revenue', 0):.2f} USDT</b>\n"
        f"   🏆 Total:      <b>${stats['total_revenue']:.2f} USDT</b>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
        ])
    )


# ══════════════════════════════════════════════════════════════════════════════
# LIMPIAR PEDIDOS VIEJOS
# ══════════════════════════════════════════════════════════════════════════════

async def admin_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    cancelled = await db.cancel_stale_pending_orders(older_than_minutes=30)
    if cancelled:
        msg = f"🧹 <b>{cancelled} pedido(s) caducado(s) cancelado(s)</b>\n\nEran pedidos pendientes con más de 30 minutos sin actividad."
    else:
        msg = "✅ <b>No hay pedidos huérfanos.</b>\n\nTodos los pedidos pendientes tienen menos de 30 minutos."

    await query.edit_message_text(
        msg, parse_mode="HTML",
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
            "✅ No hay pedidos pendientes ni en espera de entrega.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
            ])
        )
        return

    STATUS_ICONS = {"pending": "⏳", "paid": "💳"}
    for o in orders[:5]:
        svc = _all_services().get(o["service_id"], {})
        username_str = f"@{o['username']}" if o.get("username") else f"ID:{o['user_id']}"
        icon = STATUS_ICONS.get(o["status"], "❓")
        text = (
            f"{icon} <b>Pedido #{o['order_id']}</b> [{o['status'].upper()}]\n"
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
        f"📋 <b>{len(orders)} pedido(s) pendiente(s)/pagado(s)</b> — primeros 5.",
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
                text=f"📢 <b>Mensaje de ReseliBot</b>\n\n{message_text}",
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
        cred = float(u.get("credits") or 0)
        text += f"• {u['first_name']} ({ustr}) — <code>{u['user_id']}</code>"
        if cred > 0:
            text += f" 💰${cred:.2f}"
        text += "\n"
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
        await query.answer("🔐 Sesión expirada. Usa /weboadmin.", show_alert=True)
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

    del_buttons = [
        InlineKeyboardButton(f"🗑️ #{item['id']}",
                             callback_data=f"admin_stock_delitem_{item['id']}")
        for item in items[:10]
    ]
    kb_rows = [del_buttons[i:i+3] for i in range(0, len(del_buttons), 3)]
    kb_rows += [
        [InlineKeyboardButton(f"➕ Agregar a {svc_name[:20]}",
                              callback_data=f"admin_stock_add_{service_id}")],
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
    """
    Entry point for stock_add_conv.
    Triggered by callbacks: admin_stock_add_<service_id>
    NOTE: The callback 'admin_stock_add_pick' also matches the ConversationHandler pattern —
    we guard against it here and redirect to the picker instead.
    """
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return ConversationHandler.END

    service_id = query.data.replace("admin_stock_add_", "", 1)

    # ── Guard: "pick" comes from the main stock menu button, not a real service ──
    if service_id == "pick":
        await query.edit_message_text(
            "➕ <b>Agregar Stock — Elige el servicio:</b>",
            parse_mode="HTML",
            reply_markup=await _services_pick_kb("admin_stock_add")
        )
        return ConversationHandler.END

    svc_name = _svc_name(service_id)
    current  = await db.get_stock_level(service_id)

    context.user_data["stock_add_service_id"]   = service_id
    context.user_data["stock_add_service_name"] = svc_name

    await query.edit_message_text(
        f"➕ <b>Agregar credenciales — {svc_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Stock actual: <b>{current}</b> disponibles\n\n"
        "Envía las credenciales <b>una por línea</b>:\n\n"
        "<code>usuario@email.com:contraseña</code>\n"
        "<code>usuario2@email.com:contraseña2</code>\n\n"
        "Puedes pegar todas a la vez. Envía /cancelar para abortar.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data="admin_stock")]
        ])
    )
    return WAITING_STOCK_ADD_CREDS


async def admin_stock_receive_creds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives pasted credentials and saves to stock."""
    if not is_admin(update.effective_user.id) or not is_authed(context):
        return ConversationHandler.END

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
    return ConversationHandler.END


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
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "✅ Operación cancelada.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Gestión de Stock", callback_data="admin_stock")]
            ])
        )
    return ConversationHandler.END


# ── Eliminar item de stock ──────────────────────────────────────────────────────

async def admin_stock_del_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        InlineKeyboardButton(f"🗑️ #{item['id']}",
                             callback_data=f"admin_stock_delitem_{item['id']}")
        for item in items
    ]
    kb_rows = [del_buttons[i:i+3] for i in range(0, len(del_buttons), 3)]
    kb_rows.append([InlineKeyboardButton("◀️ Volver", callback_data="admin_stock_del_pick")])

    await query.edit_message_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb_rows)
    )


async def admin_stock_del_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    item_id = int(query.data.replace("admin_stock_delitem_", "", 1))
    deleted = await db.delete_stock_item(item_id)

    if deleted:
        await query.answer(f"✅ Item #{item_id} eliminado.", show_alert=True)
        await query.edit_message_text(
            f"✅ <b>Item <code>#{item_id}</code> eliminado correctamente.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Gestión de Stock", callback_data="admin_stock")]
            ])
        )
    else:
        await query.answer(f"❌ Item #{item_id} no encontrado.", show_alert=True)


# ══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE PRODUCTOS DINÁMICOS
# ══════════════════════════════════════════════════════════════════════════════

async def admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Products management menu."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        await query.answer("🔐 Sesión expirada. Usa /weboadmin.", show_alert=True)
        return

    db_prods = await db.get_all_db_products()

    lines = ["🛍️ <b>Gestionar Productos</b>\n━━━━━━━━━━━━━━━━━━━━━━━"]
    if db_prods:
        lines.append(f"<i>Productos creados desde el bot ({len(db_prods)}):</i>\n")
        for p in db_prods:
            lines.append(f"  {p['emoji']} <b>{p['name']}</b> — ${float(p['price']):.2f} USDT"
                         f"  <code>[{p['service_id']}]</code>")
    else:
        lines.append("\n<i>No hay productos dinámicos creados aún.</i>")
    lines.append("\n<i>Los productos estáticos del config.py no se muestran aquí.</i>")

    prod_buttons = []
    for p in db_prods:
        has_photo = bool(p.get("photo_file_id"))
        photo_icon = "🖼️" if has_photo else "📷"
        prod_buttons.append([
            InlineKeyboardButton(
                f"🗑️ Eliminar {p['emoji']} {p['name'][:18]}",
                callback_data=f"admin_prod_del_{p['id']}"
            ),
            InlineKeyboardButton(
                f"{photo_icon} Foto",
                callback_data=f"admin_prod_photo_{p['service_id']}"
            ),
        ])

    # Photo management for static services
    from config import SERVICES as _STATIC
    static_btns = []
    for sid, svc in _STATIC.items():
        static_btns.append([InlineKeyboardButton(
            f"📷 Foto: {svc['emoji']} {svc['name'][:22]}",
            callback_data=f"admin_prod_photo_{sid}"
        )])

    kb = InlineKeyboardMarkup(prod_buttons + [
        [InlineKeyboardButton("📷 Poner foto a productos estáticos", callback_data="admin_static_photos")],
        [InlineKeyboardButton("➕ Crear nuevo producto", callback_data="admin_prod_add")],
        [InlineKeyboardButton("◀️ Panel admin",          callback_data="admin_panel")],
    ])

    await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)


async def admin_static_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of static services to set photos."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    from config import SERVICES as _STATIC
    btns = []
    for sid, svc in _STATIC.items():
        btns.append([InlineKeyboardButton(
            f"📷 {svc['emoji']} {svc['name'][:30]}",
            callback_data=f"admin_prod_photo_{sid}"
        )])
    btns.append([InlineKeyboardButton("◀️ Gestionar Productos", callback_data="admin_products")])

    await query.edit_message_text(
        "📷 <b>Fotos de productos estáticos</b>\n\n"
        "Selecciona un producto para subir o cambiar su imagen:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(btns)
    )


# ── Crear producto — conversación multi-paso ──────────────────────────────────

async def admin_product_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return ConversationHandler.END

    context.user_data.pop("new_prod", None)   # clear any previous draft
    await query.edit_message_text(
        "🛍️ <b>Crear nuevo producto — Paso 1/8</b>\n\n"
        "¿Cuál es el <b>nombre</b> del producto?\n"
        "<i>Ejemplo: Spotify Premium 1 Mes</i>\n\n"
        "/cancelar para abortar.",
        parse_mode="HTML"
    )
    return WAITING_PROD_NAME


async def admin_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 60:
        await update.message.reply_text("⚠️ El nombre debe tener entre 2 y 60 caracteres.")
        return WAITING_PROD_NAME
    context.user_data["new_prod"] = {"name": name}
    await update.message.reply_text(
        f"✅ Nombre: <b>{name}</b>\n\n"
        "🎨 <b>Paso 2/8:</b> Envía el <b>emoji</b> del producto.\n"
        "<i>Ejemplo: 🎵  🎮  🤖  ✨</i>",
        parse_mode="HTML"
    )
    return WAITING_PROD_EMOJI


async def admin_product_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    emoji = update.message.text.strip()
    if len(emoji) > 8:
        emoji = emoji[:8]
    context.user_data["new_prod"]["emoji"] = emoji
    await update.message.reply_text(
        f"✅ Emoji: {emoji}\n\n"
        "💵 <b>Paso 3/8:</b> ¿Cuál es el <b>precio en USDT</b>?\n"
        "<i>Ejemplo: 9.99</i>",
        parse_mode="HTML"
    )
    return WAITING_PROD_PRICE


async def admin_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = float(update.message.text.strip().replace(",", "."))
        if price <= 0 or price > 9999:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Precio inválido. Escribe un número como 9.99")
        return WAITING_PROD_PRICE
    context.user_data["new_prod"]["price"] = price
    await update.message.reply_text(
        f"✅ Precio: <b>${price:.2f} USDT</b>\n\n"
        "📝 <b>Paso 4/8:</b> Escribe la <b>descripción en inglés</b>.\n"
        "<i>Ejemplo: 1 Month Premium Spotify account with full access.</i>",
        parse_mode="HTML"
    )
    return WAITING_PROD_DESC_EN


async def admin_product_desc_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_prod"]["desc_en"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ Descripción EN guardada.\n\n"
        "📝 <b>Paso 5/8:</b> Escribe la <b>descripción en español</b>.",
        parse_mode="HTML"
    )
    return WAITING_PROD_DESC_ES


async def admin_product_desc_es(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_prod"]["desc_es"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ Descripción ES guardada.\n\n"
        "⏱️ <b>Paso 6/8:</b> <b>Tiempo de entrega (inglés)</b>.\n"
        "<i>Ejemplo: Instant delivery</i>",
        parse_mode="HTML"
    )
    return WAITING_PROD_DELIVERY_EN


async def admin_product_delivery_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_prod"]["delivery_en"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ Entrega EN guardada.\n\n"
        "⏱️ <b>Paso 7/8:</b> <b>Tiempo de entrega (español)</b>.\n"
        "<i>Ejemplo: Entrega inmediata</i>",
        parse_mode="HTML"
    )
    return WAITING_PROD_DELIVERY_ES


async def admin_product_delivery_es(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 7/8 — ask for optional product image."""
    context.user_data["new_prod"]["delivery_es"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ Entrega ES guardada.\n\n"
        "🖼️ <b>Paso 8/8 — Imagen del producto (opcional)</b>\n\n"
        "Puedes enviar una <b>foto</b> ahora para que aparezca en el detalle del producto.\n"
        "O pulsa <b>Sin imagen</b> para continuar sin foto.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭️ Sin imagen", callback_data="admin_prod_no_photo"),
        ]])
    )
    return WAITING_PROD_PHOTO


async def admin_product_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 8/8 — admin sends a photo for the new product."""
    if not update.message.photo:
        await update.message.reply_text("⚠️ Envía una imagen o pulsa 'Sin imagen'.")
        return WAITING_PROD_PHOTO

    # Use the largest photo size's file_id
    file_id = update.message.photo[-1].file_id
    context.user_data["new_prod"]["photo_file_id"] = file_id

    p = context.user_data["new_prod"]
    preview = (
        f"🛍️ <b>Vista previa del producto</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{p['emoji']} <b>{p['name']}</b>\n"
        f"💵 ${p['price']:.2f} USDT\n\n"
        f"📝 <b>EN:</b> {p['desc_en']}\n"
        f"📝 <b>ES:</b> {p['desc_es']}\n\n"
        f"⏱️ <b>Entrega EN:</b> {p['delivery_en']}\n"
        f"⏱️ <b>Entrega ES:</b> {p['delivery_es']}\n"
        f"🖼️ <b>Imagen:</b> ✅ incluida\n\n"
        "¿Confirmas la creación de este producto?"
    )
    await update.message.reply_photo(
        photo=file_id,
        caption=preview,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirmar", callback_data="admin_prod_confirm"),
             InlineKeyboardButton("❌ Cancelar",  callback_data="admin_prod_cancel")],
        ])
    )
    return ConversationHandler.END


async def admin_product_no_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 8/8 — admin chose 'no photo', show preview."""
    query = update.callback_query
    await query.answer()
    context.user_data["new_prod"]["photo_file_id"] = None

    p = context.user_data["new_prod"]
    preview = (
        f"🛍️ <b>Vista previa del producto</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{p['emoji']} <b>{p['name']}</b>\n"
        f"💵 ${p['price']:.2f} USDT\n\n"
        f"📝 <b>EN:</b> {p['desc_en']}\n"
        f"📝 <b>ES:</b> {p['desc_es']}\n\n"
        f"⏱️ <b>Entrega EN:</b> {p['delivery_en']}\n"
        f"⏱️ <b>Entrega ES:</b> {p['delivery_es']}\n"
        f"🖼️ <b>Imagen:</b> sin imagen\n\n"
        "¿Confirmas la creación de este producto?"
    )
    await query.edit_message_text(
        preview, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirmar", callback_data="admin_prod_confirm"),
             InlineKeyboardButton("❌ Cancelar",  callback_data="admin_prod_cancel")],
        ])
    )
    return ConversationHandler.END


async def admin_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: user confirmed product creation."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    p = context.user_data.pop("new_prod", None)
    if not p:
        await query.answer("❌ Datos expirados. Vuelve a intentarlo.", show_alert=True)
        return

    try:
        new_id = await db.create_db_product(
            name=p["name"], emoji=p["emoji"], price=p["price"],
            desc_en=p["desc_en"], desc_es=p["desc_es"],
            delivery_en=p["delivery_en"], delivery_es=p["delivery_es"],
            photo_file_id=p.get("photo_file_id"),
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error al crear producto: {e}")
        return

    # Find the generated service_id from the cache
    cached = db.get_cached_db_products()
    sid = next((k for k, v in cached.items() if v.get("_db_id") == new_id), "?")

    await query.edit_message_text(
        f"🎉 <b>Producto creado exitosamente!</b>\n\n"
        f"{p['emoji']} <b>{p['name']}</b>\n"
        f"💵 ${p['price']:.2f} USDT\n"
        f"🔑 ID interno: <code>{sid}</code>\n\n"
        f"Ya aparece en el catálogo para los usuarios.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍️ Gestionar Productos", callback_data="admin_products")],
            [InlineKeyboardButton("◀️ Panel admin",          callback_data="admin_panel")],
        ])
    )


async def admin_product_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback or command: cancel product creation."""
    context.user_data.pop("new_prod", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ Creación de producto cancelada.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Gestionar Productos", callback_data="admin_products")],
                [InlineKeyboardButton("◀️ Panel admin",          callback_data="admin_panel")],
            ])
        )
    else:
        await update.message.reply_text(
            "❌ Creación de producto cancelada.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
            ])
        )
    if hasattr(update, "callback_query") and update.callback_query:
        return ConversationHandler.END


async def admin_prod_photo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Callback: admin_prod_photo_<service_id>
    Shows the photo management menu for a specific product.
    """
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return ConversationHandler.END

    service_id = query.data[len("admin_prod_photo_"):]
    context.user_data["photo_target_sid"] = service_id

    # Get current photo
    current_photo = await db.get_service_photo(service_id)

    # Find product name
    all_s = _all_services()
    svc = all_s.get(service_id)
    svc_label = f"{svc['emoji']} {svc['name']}" if svc else service_id

    has_photo = bool(current_photo)
    btns = [
        [InlineKeyboardButton("📸 Subir / cambiar imagen", callback_data="admin_photo_upload_prompt")],
    ]
    if has_photo:
        btns.append([InlineKeyboardButton("🗑️ Quitar imagen", callback_data="admin_photo_delete")])
    btns.append([InlineKeyboardButton("◀️ Gestionar Productos", callback_data="admin_products")])

    text = (
        f"🖼️ <b>Imagen para:</b> {svc_label}\n\n"
        + ("✅ Este producto <b>tiene</b> imagen asignada.\n" if has_photo
           else "⚠️ Este producto <b>no tiene</b> imagen.\n")
    )

    if has_photo:
        try:
            await query.message.delete()
            await query.message.chat.send_photo(
                photo=current_photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(btns)
            )
        except Exception:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
    else:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
    return ConversationHandler.END


async def admin_photo_upload_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: prompts the admin to send a photo."""
    query = update.callback_query
    await query.answer()
    service_id = context.user_data.get("photo_target_sid", "")
    all_s = _all_services()
    svc = all_s.get(service_id)
    svc_label = f"{svc['emoji']} {svc['name']}" if svc else service_id

    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.chat.send_message(
        f"📸 <b>Envía la imagen para:</b> {svc_label}\n\n"
        "Envía una foto (no archivo) directamente en este chat.\n"
        "/cancelar para abortar.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancelar", callback_data="admin_panel")
        ]])
    )
    return WAITING_SET_PHOTO


async def admin_photo_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """MessageHandler: receives the photo and saves it."""
    if not update.message.photo:
        await update.message.reply_text("⚠️ Debes enviar una imagen. Inténtalo de nuevo.")
        return WAITING_SET_PHOTO

    service_id = context.user_data.get("photo_target_sid")
    if not service_id:
        await update.message.reply_text("❌ Sesión expirada. Vuelve al panel.")
        return ConversationHandler.END

    file_id = update.message.photo[-1].file_id
    await db.set_service_photo(service_id, file_id)

    all_s = _all_services()
    svc = all_s.get(service_id)
    svc_label = f"{svc['emoji']} {svc['name']}" if svc else service_id

    await update.message.reply_photo(
        photo=file_id,
        caption=(
            f"✅ <b>Imagen guardada para:</b> {svc_label}\n\n"
            "Los usuarios verán esta imagen al seleccionar el producto."
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍️ Gestionar Productos", callback_data="admin_products")],
            [InlineKeyboardButton("◀️ Panel admin",          callback_data="admin_panel")],
        ])
    )
    context.user_data.pop("photo_target_sid", None)
    return ConversationHandler.END


async def admin_photo_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: removes the photo from a product."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    service_id = context.user_data.pop("photo_target_sid", None)
    if service_id:
        await db.delete_service_photo(service_id)

    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.chat.send_message(
        "🗑️ <b>Imagen eliminada.</b>\n\nEl producto ya no mostrará foto.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍️ Gestionar Productos", callback_data="admin_products")],
            [InlineKeyboardButton("◀️ Panel admin",          callback_data="admin_panel")],
        ])
    )


async def admin_product_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: admin_prod_del_<db_id> — delete a dynamic product."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id) or not is_authed(context):
        return

    db_id = int(query.data.replace("admin_prod_del_", "", 1))

    # Find product name before deleting
    cached = db.get_cached_db_products()
    prod_name = next(
        (v["name"] for v in cached.values() if v.get("_db_id") == db_id),
        f"#ID{db_id}"
    )

    deleted = await db.delete_db_product(db_id)
    if deleted:
        await query.answer(f"✅ Producto '{prod_name}' eliminado.", show_alert=True)
        await query.edit_message_text(
            f"✅ <b>Producto eliminado: {prod_name}</b>\n\n"
            "Ya no aparecerá en el catálogo.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Gestionar Productos", callback_data="admin_products")],
                [InlineKeyboardButton("◀️ Panel admin",          callback_data="admin_panel")],
            ])
        )
    else:
        await query.answer("❌ Producto no encontrado.", show_alert=True)


# ══════════════════════════════════════════════════════════════════════════════
# /setphoto — Set the bot welcome photo (admin command, no panel auth required)
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_setphoto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    /setphoto — Admin command to set the bot's welcome image.
    Does not require panel password; ADMIN_IDS check is sufficient.
    """
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    # Show current photo if set
    current = await db.get_bot_config("welcome_photo_file_id")
    if current:
        try:
            await update.message.reply_photo(
                photo=current,
                caption=(
                    "📸 <b>Foto de bienvenida actual</b>\n\n"
                    "Envía una nueva imagen para reemplazarla, "
                    "o /cancel para salir sin cambios."
                ),
                parse_mode="HTML",
            )
            return WAITING_WELCOME_PHOTO
        except Exception:
            pass

    await update.message.reply_text(
        "📸 <b>Configurar foto de bienvenida</b>\n\n"
        "Envía la imagen que quieres mostrar al arrancar el bot con /start.\n\n"
        "Usa /cancel para salir sin cambios.",
        parse_mode="HTML",
    )
    return WAITING_WELCOME_PHOTO


async def receive_welcome_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives and persists the new welcome photo file_id to DB config."""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text("⚠️ Envía una imagen (foto). /cancel para salir.")
        return WAITING_WELCOME_PHOTO

    file_id = update.message.photo[-1].file_id
    await db.set_bot_config("welcome_photo_file_id", file_id)

    await update.message.reply_photo(
        photo=file_id,
        caption=(
            "✅ <b>Foto de bienvenida actualizada.</b>\n\n"
            "Los usuarios verán esta imagen al iniciar el bot con /start.\n\n"
            f"<code>{file_id}</code>"
        ),
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# CANCEL / NOOP helpers
# ══════════════════════════════════════════════════════════════════════════════

async def admin_cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("deliver_order_id", None)
    context.user_data.pop("new_prod", None)
    if update.message:
        await update.message.reply_text(
            "❌ Operación cancelada.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Panel admin", callback_data="admin_panel")]
            ])
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
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


# ── Legacy /addstock and /stock commands ─────────────────────────────────────

async def cmd_addstock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if not is_authed(context):
        await update.message.reply_text("🔐 Usa /weboadmin primero para autenticarte.")
        return ConversationHandler.END
    args = context.args
    if not args:
        kb = await _services_pick_kb("admin_stock_add")
        await update.message.reply_text("➕ Elige el servicio:", reply_markup=kb)
        return ConversationHandler.END
    service_id = args[0].strip()
    svc = _all_services().get(service_id)
    if not svc:
        await update.message.reply_text(
            f"❌ ID <code>{service_id}</code> no encontrado.", parse_mode="HTML")
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
        await update.message.reply_text("🔐 Usa /weboadmin primero para autenticarte.")
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
