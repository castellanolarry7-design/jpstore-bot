"""
catalog.py – Service catalog with stock display and quantity selector
"""
from telegram import Update
from telegram.ext import ContextTypes
from config import SERVICES
import database as db
from strings import t
from utils.keyboards import (
    catalog_kb, service_detail_kb, payment_method_kb,
    quantity_kb, stock_badge,
)
from utils.delivery import apply_discount


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang         = await db.get_user_lang(query.from_user.id)
    stock_levels = await db.get_stock_levels_dict()
    await query.edit_message_text(
        t("catalog_title", lang),
        parse_mode="HTML",
        reply_markup=catalog_kb(lang, stock_levels)
    )


async def show_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    service_id = query.data.split("_", 1)[1]
    svc = SERVICES.get(service_id)
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

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=service_detail_kb(service_id, lang, stock_qty)
    )


async def show_quantity_selector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: qtysel_<service_id> — shows quantity buttons with discount labels."""
    query = update.callback_query
    await query.answer()

    service_id = query.data.split("_", 1)[1]
    svc = SERVICES.get(service_id)
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

    if lang == "en":
        header = (
            f"{svc['emoji']} <b>{svc['name']}</b>\n"
            f"💵 Unit price: <b>${svc['price']:.2f} USDT</b>\n"
            f"📦 Available: <b>{stock_qty}</b>\n\n"
            "🛒 <b>How many do you want?</b>\n\n"
            "🟡 <b>6+</b> units → <b>10% discount</b>\n"
            "🟢 <b>16+</b> units → <b>15% discount</b>"
        )
    else:
        header = (
            f"{svc['emoji']} <b>{svc['name']}</b>\n"
            f"💵 Precio unitario: <b>${svc['price']:.2f} USDT</b>\n"
            f"📦 Disponibles: <b>{stock_qty}</b>\n\n"
            "🛒 <b>¿Cuántos quieres?</b>\n\n"
            "🟡 <b>6+</b> unidades → <b>10% de descuento</b>\n"
            "🟢 <b>16+</b> unidades → <b>15% de descuento</b>"
        )

    await query.edit_message_text(
        header, parse_mode="HTML",
        reply_markup=quantity_kb(service_id, svc["price"], stock_qty, lang)
    )


async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: qty_<service_id>_<qty> — stores quantity and shows payment methods."""
    query = update.callback_query
    await query.answer()

    parts      = query.data.split("_", 2)   # ['qty', service_id, qty]
    service_id = parts[1]
    qty        = int(parts[2])

    svc = SERVICES.get(service_id)
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

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=payment_method_kb(service_id, lang)
    )


async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: buy_<service_id> — direct buy without qty selector (fallback)."""
    query = update.callback_query
    await query.answer()

    service_id = query.data.split("_", 1)[1]
    svc = SERVICES.get(service_id)
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

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=payment_method_kb(service_id, lang)
    )
