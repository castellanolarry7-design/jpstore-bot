"""
notifications.py – Envío de notificaciones a admins y usuarios
"""
from telegram import Bot
from config import ADMIN_IDS, SERVICES
from utils.keyboards import admin_order_kb


async def notify_admins_new_order(bot: Bot, order: dict, user: dict) -> None:
    """Notifica a todos los admins cuando llega un pedido nuevo."""
    service = SERVICES.get(order["service_id"], {})
    username_str = f"@{user['username']}" if user.get("username") else f"ID: {user['user_id']}"

    text = (
        "🆕 <b>NUEVO PEDIDO</b>\n\n"
        f"🆔 Pedido #<b>{order['order_id']}</b>\n"
        f"👤 Cliente: {user['first_name']} ({username_str})\n"
        f"🛒 Servicio: {service.get('name', order['service_id'])}\n"
        f"💵 Monto: <b>${order['amount']:.2f} USDT</b>\n"
        f"💳 Método: {order['payment_method'].upper()}\n"
        f"📅 Fecha: {order['created_at']}\n"
    )
    if order.get("payment_proof"):
        text += f"\n🧾 Comprobante adjunto ✅"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
                reply_markup=admin_order_kb(order["order_id"], order["user_id"])
            )
            # Si hay comprobante tipo foto, reenviarla
            if order.get("payment_proof") and not order["payment_proof"].startswith("TX:"):
                await bot.send_photo(chat_id=admin_id, photo=order["payment_proof"],
                                     caption=f"Comprobante pedido #{order['order_id']}")
        except Exception as e:
            print(f"[WARN] No se pudo notificar al admin {admin_id}: {e}")


async def notify_order_delivered(bot: Bot, user_id: int, order: dict, delivery_info: str) -> None:
    """Notifica al usuario que su pedido fue entregado."""
    service = SERVICES.get(order["service_id"], {})
    text = (
        f"🎉 <b>¡Tu pedido fue entregado!</b>\n\n"
        f"🆔 Pedido #<b>{order['order_id']}</b>\n"
        f"🛒 Servicio: {service.get('name', order['service_id'])}\n\n"
        f"📦 <b>Información de acceso:</b>\n"
        f"<code>{delivery_info}</code>\n\n"
        "¡Gracias por tu compra! Si tienes problemas, contáctanos. 💙"
    )
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
    except Exception as e:
        print(f"[WARN] No se pudo notificar al usuario {user_id}: {e}")


async def notify_new_user(bot: Bot, user: dict, referred_by_name: str = None) -> None:
    """Notifica a los admins cuando un usuario inicia el bot por primera vez."""
    from config import ADMIN_IDS
    username_str = f"@{user['username']}" if user.get("username") else "no username"
    ref_line = f"\n🎁 Referred by: <b>{referred_by_name}</b>" if referred_by_name else ""

    text = (
        "👤 <b>New User!</b>\n\n"
        f"👋 <b>{user['first_name']}</b> ({username_str})\n"
        f"🆔 ID: <code>{user['user_id']}</code>"
        f"{ref_line}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception as e:
            print(f"[WARN] Could not notify admin {admin_id}: {e}")


async def notify_order_status(bot: Bot, user_id: int, order_id: int, status: str, note: str = None) -> None:
    """Notificación genérica de cambio de estado."""
    icons = {"paid": "✅", "cancelled": "❌", "pending": "⏳", "delivered": "🎉"}
    labels = {"paid": "PAGO CONFIRMADO", "cancelled": "CANCELADO", "pending": "PENDIENTE", "delivered": "ENTREGADO"}
    icon = icons.get(status, "ℹ️")
    label = labels.get(status, status.upper())
    text = f"{icon} <b>Pedido #{order_id} — {label}</b>"
    if note:
        text += f"\n\n📝 Nota: {note}"
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
    except Exception as e:
        print(f"[WARN] No se pudo notificar al usuario {user_id}: {e}")
