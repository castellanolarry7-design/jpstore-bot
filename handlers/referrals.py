"""
referrals.py – Referral program handler
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import BOT_USERNAME, REFERRAL_REWARD
import database as db
from strings import t


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

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)


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


async def handle_first_purchase_referral(bot, buyer_id: int) -> None:
    """
    Called after a buyer's first purchase is confirmed.
    Credits the referrer $1 and notifies them.
    """
    referrer_id = await db.mark_first_purchase(buyer_id)
    if not referrer_id:
        return  # no referrer or already credited

    credited = await db.credit_referral(referrer_id, buyer_id)
    if not credited:
        return

    buyer       = await db.get_user(buyer_id)
    referrer    = await db.get_user(referrer_id)
    referrer_lang = referrer.get("lang", "en") if referrer else "en"
    buyer_name  = buyer.get("first_name", "Someone") if buyer else "Someone"

    try:
        await bot.send_message(
            chat_id=referrer_id,
            text=t("referral_credited", referrer_lang, name=buyer_name),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[Referral notify] Could not notify {referrer_id}: {e}")
