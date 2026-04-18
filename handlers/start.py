"""
start.py – /start command, main menu, and language selector
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import STORE_NAME, STORE_DESCRIPTION, SUPPORT_USERNAME, WELCOME_PHOTO_FILE_ID
import database as db
from strings import t
from utils.keyboards import main_menu_kb, language_kb
from utils.notifications import notify_new_user
from utils.membership import check_membership, join_required_message


async def _get_welcome_photo() -> str:
    """
    Return the active welcome photo file_id.
    DB config (set via /setphoto) takes priority over the WELCOME_PHOTO_FILE_ID env var.
    """
    db_photo = await db.get_bot_config("welcome_photo_file_id")
    return db_photo or WELCOME_PHOTO_FILE_ID


async def _send_welcome(update: Update, lang: str, edit: bool = False) -> None:
    """Send or edit the welcome message, with photo if one is configured."""
    text  = t("welcome", lang, store_name=STORE_NAME, description=STORE_DESCRIPTION)
    kb    = main_menu_kb(lang)
    photo = await _get_welcome_photo()

    if update.message:
        if photo:
            try:
                await update.message.reply_photo(
                    photo=photo,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                return
            except Exception:
                pass
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        if photo:
            try:
                await query.message.delete()
            except Exception:
                pass
            try:
                await query.message.chat.send_photo(
                    photo=photo,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                return
            except Exception:
                pass
        # Fallback: text
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await query.message.chat.send_message(text, parse_mode="HTML", reply_markup=kb)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    # ── Membership gate ───────────────────────────────────────────────────────
    all_joined, missing = await check_membership(context.bot, user.id)
    if not all_joined:
        lang  = await db.get_user_lang(user.id) if await db.get_user(user.id) else "en"
        text, kb = join_required_message(lang, missing)
        photo = await _get_welcome_photo()
        if update.message:
            if photo:
                try:
                    await update.message.reply_photo(
                        photo=photo, caption=text,
                        parse_mode="HTML", reply_markup=kb
                    )
                    return
                except Exception:
                    pass
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    # ── Register / update user ────────────────────────────────────────────────
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

    await _send_welcome(update, lang)


async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: user presses '✅ Ya me uní — Verificar'."""
    query = update.callback_query
    await query.answer()
    user  = query.from_user

    all_joined, missing = await check_membership(context.bot, user.id)

    if not all_joined:
        lang = await db.get_user_lang(user.id) if await db.get_user(user.id) else "en"
        text, kb = join_required_message(lang, missing)
        try:
            await query.edit_message_caption(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            try:
                await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                pass
        return

    # All joined — proceed with normal start flow
    existing = await db.get_user(user.id)
    if not existing:
        await db.upsert_user(user.id, user.username, user.first_name)

    lang  = await db.get_user_lang(user.id)
    text  = t("welcome", lang, store_name=STORE_NAME, description=STORE_DESCRIPTION)
    kb    = main_menu_kb(lang)
    photo = await _get_welcome_photo()

    # Delete the gate message and send welcome
    try:
        await query.message.delete()
    except Exception:
        pass

    if photo:
        try:
            await query.message.chat.send_photo(
                photo=photo, caption=text,
                parse_mode="HTML", reply_markup=kb
            )
            return
        except Exception:
            pass
    await query.message.chat.send_message(text, parse_mode="HTML", reply_markup=kb)


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
    """Callback: setlang_en | setlang_es | setlang_hi | setlang_id | setlang_ur | setlang_zh"""
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
