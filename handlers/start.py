"""
start.py – /start command, main menu, and language selector
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import STORE_NAME, STORE_DESCRIPTION, SUPPORT_USERNAME
import database as db
from strings import t
from utils.keyboards import main_menu_kb, language_kb
from utils.notifications import notify_new_user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    # Check if user is brand new BEFORE upserting
    existing = await db.get_user(user.id)
    is_new   = existing is None

    # Parse referral code from deep link: /start ref_XXXXXXXX
    referred_by_id   = None
    referred_by_name = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            code     = arg[4:]
            referrer = await db.get_user_by_referral_code(code)
            if referrer and referrer["user_id"] != user.id:
                referred_by_id   = referrer["user_id"]
                referred_by_name = referrer.get("first_name", "someone")

    await db.upsert_user(user.id, user.username, user.first_name,
                         referred_by=referred_by_id)

    # Record referral link and notify new user bonus
    if is_new and referred_by_id:
        from handlers.referrals import process_referral_start
        new_user_data = await db.get_user(user.id)
        await process_referral_start(context.bot, code, new_user_data)

    # Notify admins of new user (fire & forget)
    if is_new:
        new_user_data = await db.get_user(user.id)
        await notify_new_user(context.bot, new_user_data, referred_by_name)

    lang = await db.get_user_lang(user.id)

    # Show referral welcome bonus message to new referred users
    if is_new and referred_by_id:
        bonus_text = t("referral_welcome_bonus", lang)
        if update.message:
            await update.message.reply_text(bonus_text, parse_mode="HTML")

    text = t("welcome", lang,
             store_name=STORE_NAME,
             description=STORE_DESCRIPTION)

    if update.message:
        await update.message.reply_text(text, parse_mode="HTML",
                                        reply_markup=main_menu_kb(lang))
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML",
                                      reply_markup=main_menu_kb(lang))


async def show_language_selector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = await db.get_user_lang(query.from_user.id)
    await query.edit_message_text(
        t("choose_language", lang),
        parse_mode="HTML",
        reply_markup=language_kb()
    )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: setlang_en | setlang_es"""
    query    = update.callback_query
    new_lang = query.data.split("_")[1]
    await db.set_user_lang(query.from_user.id, new_lang)
    await query.answer(t("language_set", new_lang), show_alert=False)

    text = t("welcome", new_lang,
             store_name=STORE_NAME,
             description=STORE_DESCRIPTION)
    await query.edit_message_text(text, parse_mode="HTML",
                                  reply_markup=main_menu_kb(new_lang))


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang  = await db.get_user_lang(query.from_user.id)
    text  = t("support_text", lang, username=SUPPORT_USERNAME)
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
        ])
    )
