"""
delivery.py – Auto-delivery logic
When a payment is confirmed, tries to grab stock items and send them to the user.
If stock is empty, notifies admin to deliver manually.
"""
import database as db
from config import ADMIN_IDS, SERVICES, METHODS


def _format_credential(content: str) -> str:
    """
    Format a single stock item for the delivery message.
    • URLs  → displayed as a clickable hyperlink (no <code> needed, can't be copied)
    • Anything else → <code>…</code>  (tap once to copy in Telegram)
    """
    c = content.strip()
    if c.startswith("http://") or c.startswith("https://"):
        return f'🔗 <a href="{c}">{c}</a>'
    return f"<code>{c}</code>"


def build_delivery_message(
    emoji: str, name: str, order_id, lang: str, items: list[dict]
) -> str:
    """Build a polished delivery message for any number of stock items."""
    qty_label = f" ×{len(items)}" if len(items) > 1 else ""

    # Format each credential line
    lines = []
    for i, it in enumerate(items):
        cred = _format_credential(it["content"])
        prefix = f"{i+1}. " if len(items) > 1 else ""
        lines.append(f"{prefix}{cred}")
    creds_block = "\n".join(lines)

    if lang == "en":
        return (
            f"✅ <b>Order delivered!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>{name}{qty_label}</b>\n"
            f"🆔 Order <b>#{order_id}</b>\n\n"
            f"🔑 <b>Your access:</b>\n"
            f"{creds_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Tap the credentials to copy them instantly.</i>\n"
            f"📩 Questions? Contact support — we're here for you! 💙"
        )
    else:
        return (
            f"✅ <b>¡Pedido entregado!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>{name}{qty_label}</b>\n"
            f"🆔 Pedido <b>#{order_id}</b>\n\n"
            f"🔑 <b>Tu acceso:</b>\n"
            f"{creds_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Toca las credenciales para copiarlas al instante.</i>\n"
            f"📩 ¿Dudas? Contáctanos — ¡estamos para ayudarte! 💙"
        )


def calculate_discount(qty: int) -> float:
    """Returns discount rate: 0.10 for qty>5, 0.15 for qty>15."""
    if qty > 15:
        return 0.15
    if qty > 5:
        return 0.10
    return 0.0


def apply_discount(unit_price: float, qty: int) -> tuple[float, float, float]:
    """
    Returns (unit_price_after_discount, total_price, discount_rate).
    """
    rate        = calculate_discount(qty)
    unit_disc   = round(unit_price * (1 - rate), 2)
    total       = round(unit_disc * qty, 2)
    return unit_disc, total, rate


async def auto_deliver(
    bot,
    order_id: int,
    service_id: str,
    user_id: int,
    lang: str,
    qty: int = 1,
) -> bool:
    """
    Try to auto-deliver a stock item for the given order.
    Returns True if delivered, False if stock was empty (manual delivery needed).
    """
    svc   = SERVICES.get(service_id) or METHODS.get(service_id) or {}
    name  = svc.get("name", service_id)
    emoji = svc.get("emoji", "📦")

    # ── Activation-required products: skip stock, request account credentials ──
    if db.is_activation_required(service_id):
        lang_label = "es" if lang == "es" else "en"
        if lang == "es":
            msg = (
                f"✅ <b>¡Pago confirmado!</b>\n\n"
                f"{emoji} <b>{name}</b>\n"
                f"🆔 Pedido #{order_id}\n\n"
                "Para activar tu servicio necesitamos los datos de tu cuenta.\n"
                "Pulsa el botón de abajo para proporcionarlos de forma segura. 🔒"
            )
        else:
            msg = (
                f"✅ <b>Payment confirmed!</b>\n\n"
                f"{emoji} <b>{name}</b>\n"
                f"🆔 Order #{order_id}\n\n"
                "To activate your service we need your account credentials.\n"
                "Tap the button below to provide them securely. 🔒"
            )
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔑 Proporcionar datos / Provide credentials",
                callback_data=f"act_start_{order_id}"
            )
        ]])
        try:
            await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            print(f"[Activation] Could not send credential request to {user_id}: {e}")
        return True   # handled — no stock needed

    items = await db.take_stock_items_multi(service_id, order_id, qty)

    if items:
        # ── Delivered automatically ───────────────────────────────────────────
        ids_str = ", ".join(f"#{it['id']}" for it in items)

        await db.update_order_status(
            order_id, "delivered",
            delivery_info="\n".join(it["content"] for it in items),
            admin_note=f"Auto-delivered {len(items)}x from stock (items {ids_str})"
        )

        msg = build_delivery_message(emoji, name, order_id, lang, items)
        try:
            await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML",
                                   disable_web_page_preview=True)
        except Exception as e:
            print(f"[Delivery] Error sending credentials to user {user_id}: {e}")

        # Warn admin if partial delivery (ran out mid-order)
        partial = len(items) < qty
        remaining = await db.get_stock_level(service_id)
        admin_msg = (
            f"{'⚠️ Entrega parcial' if partial else '✅ Auto-entrega exitosa'}\n\n"
            f"📦 Pedido #{order_id} — {name}\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"📊 Entregados: {len(items)}/{qty} | Stock restante: {remaining}"
        )
        if partial:
            admin_msg += f"\n\n🔴 Faltan {qty - len(items)} unidades — entrega manual requerida."
        elif remaining <= 3:
            admin_msg += f"\n\n⚠️ ¡Stock bajo! Solo quedan {remaining} unidades."

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="HTML")
            except Exception:
                pass

        return not partial

    else:
        # ── No stock — notify admin to deliver manually ───────────────────────
        admin_msg = (
            f"🔴 <b>Stock vacío — entrega manual requerida</b>\n\n"
            f"📦 Pedido #{order_id} — {name} x{qty}\n"
            f"👤 User ID: <code>{user_id}</code>\n\n"
            "No hay stock disponible. Entrega manualmente desde el panel admin."
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="HTML")
            except Exception:
                pass

        if lang == "en":
            msg = (
                f"✅ <b>Payment confirmed!</b>\n\n"
                f"{emoji} <b>{name}</b> — Order #{order_id}\n\n"
                "We're preparing your access. "
                "You'll receive your credentials within 24 hours ⏱️"
            )
        else:
            msg = (
                f"✅ <b>¡Pago confirmado!</b>\n\n"
                f"{emoji} <b>{name}</b> — Pedido #{order_id}\n\n"
                "Estamos preparando tu acceso. "
                "Recibirás tus credenciales en menos de 24 horas ⏱️"
            )
        try:
            await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
        except Exception as e:
            print(f"[Delivery] Error notifying user {user_id}: {e}")

        return False
