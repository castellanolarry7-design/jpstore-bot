"""
referrals.py – Referral program handler
Credits $1 to the referrer on EVERY purchase made by a referred user.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import BOT_USERNAME, REFERRAL_REWARD
import database as db
from strings import t
from utils.keyboards import safe_edit


async def show_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user    = await db.get_user(user_id)
    lang    = user.get("lang", "en") if user else "en"

    code    = user.get("referral_code", "") if user else ""
    credits = user.get("credits", 0.0) if user else 0.0
    count   = await db.get_referral_count(user_id)
    link    = f"https://t.me/{BOT_USERNAME}?start=ref_{code}"

    text = t("referrals_info", lang,
             link=link, count=count, credits=credits)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 " + ("Share" if lang == "en" else "Compartir"),
                              url=f"https://t.me/share/url?url={link}&text={'Check+out+ReseliBot!' if lang=='en' else '¡Mira+ReseliBot!'}"),
        ],
        [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
    ])

    await safe_edit(query, text, reply_markup=kb, disable_web_page_preview=True)


async def process_referral_start(bot, referrer_code: str, new_user: dict) -> None:
    """
    Called during /start when a referral code is present.
    Records the referral link between referrer and new user.
    """
    referrer = await db.get_user_by_referral_code(referrer_code)
    if not referrer:
        return
    if referrer["user_id"] == new_user["user_id"]:
        return  # Can't refer yourself

    await db.record_referral(referrer["user_id"], new_user["user_id"])


async def handle_purchase_referral(bot, buyer_id: int) -> None:
    """
    Called after EVERY confirmed purchase.
    Credits $1 to the referrer (if the buyer was referred) and notifies them.
    No "first purchase only" restriction — works on every purchase.
    """
    referrer_id = await db.get_referrer_id(buyer_id)
    if not referrer_id:
        return  # buyer was not referred by anyone

    await db.add_referral_credit(referrer_id, buyer_id)

    buyer         = await db.get_user(buyer_id)
    referrer      = await db.get_user(referrer_id)
    referrer_lang = referrer.get("lang", "en") if referrer else "en"
    buyer_name    = buyer.get("first_name", "Someone") if buyer else "Someone"

    try:
        await bot.send_message(
            chat_id=referrer_id,
            text=t("referral_credited", referrer_lang, name=buyer_name),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[Referral notify] Could not notify {referrer_id}: {e}")


# Backward-compatible alias (used across orders.py, monitors, etc.)
async def handle_first_purchase_referral(bot, buyer_id: int) -> None:
    await handle_purchase_referral(bot, buyer_id)
