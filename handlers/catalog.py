"""
catalog.py – Service catalog with stock display and quantity selector
"""
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes
from config import SERVICES
import database as db
from strings import t
from utils.keyboards import (
    catalog_kb, service_detail_kb, payment_method_kb,
    qty_control_kb, stock_badge,
)
from utils.delivery import apply_discount


def _all_catalog_services() -> dict:
    """Merge static SERVICES with dynamically-created DB products."""
    return {**SERVICES, **db.get_cached_db_products()}


async def _show_text(query, text: str, reply_markup, parse_mode: str = "HTML") -> None:
    """
    Edit the current message to text. If it's a photo message, delete it first
    and send a new text message (Telegram can't edit a photo into plain text in-place).
    """
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.chat.send_message(text, parse_mode=parse_mode, reply_markup=reply_markup)


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang         = await db.get_user_lang(query.from_user.id)
    stock_levels = await db.get_stock_levels_dict()
    await _show_text(
        query,
        t("catalog_title", lang),
        reply_markup=catalog_kb(lang, stock_levels)
    )


async def show_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    service_id = query.data.split("_", 1)[1]
    svc = _all_catalog_services().get(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    lang      = await db.get_user_lang(query.from_user.id)
    stock_qty = await db.get_stock_level(service_id)
    desc      = svc["description"].get(lang) or svc["description"]["en"]
    delivery  = svc["delivery"].get(lang) or svc["delivery"]["en"]

    stock_line = f"\n📦 <b>{'Stock' if lang=='en' else 'Disponibilidad'}:</b> {stock_badge(stock_qty, lang)}"

    text = t("service_detail", lang,
             emoji=svc["emoji"],
             name=svc["name"],
             description=desc,
             price=f"${svc['price']:.2f} USDT",
             delivery=delivery) + stock_line

    kb = service_detail_kb(service_id, lang, stock_qty)

    # ── Check if the service has a photo ─────────────────────────────────────
    photo_id = await db.get_service_photo(service_id)

    if photo_id:
        # Delete the current message and send a photo with caption
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await query.message.chat.send_photo(
                photo=photo_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception:
            # If photo fails (e.g. file expired), fall back to text
            await query.message.chat.send_message(text, parse_mode="HTML", reply_markup=kb)
    else:
        await _show_text(query, text, reply_markup=kb)


def _qty_header(svc: dict, qty: int, stock_qty: int, lang: str) -> str:
    """Builds the text shown above the +/- selector."""
    _, total, rate = apply_discount(svc["price"], qty)
    disc_note = f" <i>(-{int(rate*100)}%)</i>" if rate > 0 else ""
    if lang == "en":
        return (
            f"{svc['emoji']} <b>{svc['name']}</b>\n"
            f"💵 Unit price: <b>${svc['price']:.2f} USDT</b>  "
            f"📦 Stock: <b>{stock_qty}</b>\n\n"
            f"🛒 Quantity: <b>{qty}</b>  →  Total: <b>${total:.2f} USDT</b>{disc_note}"
        )
    else:
        return (
            f"{svc['emoji']} <b>{svc['name']}</b>\n"
            f"💵 Precio unitario: <b>${svc['price']:.2f} USDT</b>  "
            f"📦 Stock: <b>{stock_qty}</b>\n\n"
            f"🛒 Cantidad: <b>{qty}</b>  →  Total: <b>${total:.2f} USDT</b>{disc_note}"
        )


async def show_quantity_selector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: qtysel_<service_id> — shows +/- quantity selector starting at 1."""
    query = update.callback_query
    await query.answer()

    # service_id may contain underscores (e.g. gemini_pro_1m)
    service_id = query.data[len("qtysel_"):]
    svc = _all_catalog_services().get(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    lang      = await db.get_user_lang(query.from_user.id)
    stock_qty = await db.get_stock_level(service_id)

    if stock_qty == 0:
        await query.answer(
            "Out of stock — contact support." if lang == "en"
            else "Sin stock — contacta soporte.",
            show_alert=True
        )
        return

    qty = 1
    await _show_text(
        query,
        _qty_header(svc, qty, stock_qty, lang),
        reply_markup=qty_control_kb(service_id, svc["price"], qty, stock_qty, lang)
    )


async def qty_control(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: qtyctrl_<service_id>_<qty> — updates the +/- display when user presses ➕/➖."""
    query = update.callback_query
    await query.answer()

    # Strip prefix then rsplit on last _ to get qty (service_id may contain _)
    data       = query.data[len("qtyctrl_"):]
    service_id, qty_str = data.rsplit("_", 1)
    qty        = int(qty_str)

    svc = _all_catalog_services().get(service_id)
    if not svc:
        return

    lang      = await db.get_user_lang(query.from_user.id)
    stock_qty = await db.get_stock_level(service_id)
    qty       = max(1, min(qty, stock_qty))

    try:
        await _show_text(
            query,
            _qty_header(svc, qty, stock_qty, lang),
            reply_markup=qty_control_kb(service_id, svc["price"], qty, stock_qty, lang)
        )
    except Exception:
        pass  # ignore "message not modified" if user spam-clicks same value


async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: qty_<service_id>_<qty> — user pressed the Buy button → show payment methods."""
    query = update.callback_query
    await query.answer()

    # Strip prefix then rsplit to separate qty (service_id may contain _)
    data       = query.data[len("qty_"):]
    service_id, qty_str = data.rsplit("_", 1)
    qty        = int(qty_str)

    svc = _all_catalog_services().get(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    lang      = await db.get_user_lang(query.from_user.id)
    stock_qty = await db.get_stock_level(service_id)

    if qty > stock_qty:
        await query.answer(
            f"Only {stock_qty} units available." if lang == "en"
            else f"Solo hay {stock_qty} unidades disponibles.",
            show_alert=True
        )
        return

    # Store chosen qty in user_data for the payment handler to read
    context.user_data["order_qty"] = qty

    unit_disc, total, rate = apply_discount(svc["price"], qty)
    disc_note = ""
    if rate > 0:
        disc_note = (
            f"\n💸 <b>{'Discount' if lang=='en' else 'Descuento'}: {int(rate*100)}% off</b>"
            f" (${svc['price']:.2f} → ${unit_disc:.2f}/{'unit' if lang=='en' else 'unidad'})"
        )

    if lang == "en":
        text = (
            f"🛒 <b>{svc['emoji']} {svc['name']} x{qty}</b>\n"
            f"💵 Total: <b>${total:.2f} USDT</b>{disc_note}\n\n"
            "Choose your payment method:"
        )
    else:
        text = (
            f"🛒 <b>{svc['emoji']} {svc['name']} x{qty}</b>\n"
            f"💵 Total: <b>${total:.2f} USDT</b>{disc_note}\n\n"
            "Elige tu método de pago:"
        )

    user         = await db.get_user(query.from_user.id)
    user_credits = float(user["credits"]) if user and user.get("credits") else 0.0

    await _show_text(
        query, text,
        reply_markup=payment_method_kb(service_id, lang,
                                       user_credits=user_credits, total_price=total)
    )


async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: buy_<service_id> — direct buy without qty selector (fallback)."""
    query = update.callback_query
    await query.answer()

    service_id = query.data.split("_", 1)[1]
    svc = _all_catalog_services().get(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)
    # Reset qty to 1 if arriving via direct buy
    context.user_data.setdefault("order_qty", 1)

    text = t("choose_payment", lang,
             emoji=svc["emoji"],
             name=svc["name"],
             price=f"{svc['price']:.2f}")

    user         = await db.get_user(query.from_user.id)
    user_credits = float(user["credits"]) if user and user.get("credits") else 0.0

    await _show_text(
        query, text,
        reply_markup=payment_method_kb(service_id, lang,
                                       user_credits=user_credits, total_price=svc["price"])
    )
