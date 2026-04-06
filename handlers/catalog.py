"""
catalog.py – Service catalog
"""
from telegram import Update
from telegram.ext import ContextTypes
from config import SERVICES
import database as db
from strings import t
from utils.keyboards import catalog_kb, service_detail_kb, payment_method_kb


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = await db.get_user_lang(query.from_user.id)
    await query.edit_message_text(
        t("catalog_title", lang),
        parse_mode="HTML",
        reply_markup=catalog_kb(lang)
    )


async def show_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    service_id = query.data.split("_", 1)[1]
    svc = SERVICES.get(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)
    desc     = svc["description"].get(lang) or svc["description"]["en"]
    delivery = svc["delivery"].get(lang) or svc["delivery"]["en"]

    text = t("service_detail", lang,
             emoji=svc["emoji"],
             name=svc["name"],
             description=desc,
             price=f"${svc['price']:.2f} USDT",
             delivery=delivery)

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=service_detail_kb(service_id, lang)
    )


async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    service_id = query.data.split("_", 1)[1]
    svc = SERVICES.get(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)
    text = t("choose_payment", lang,
             emoji=svc["emoji"],
             name=svc["name"],
             price=f"{svc['price']:.2f}")

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=payment_method_kb(service_id, lang)
    )
