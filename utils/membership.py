"""
membership.py – Mandatory group/channel join gate
Users must be members of REQUIRED_GROUP and REQUIRED_CHANNEL to use the bot.
The bot must be an admin in both chats for get_chat_member() to work.
"""
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import REQUIRED_GROUP, REQUIRED_CHANNEL

# Link labels
_CHATS = [
    (REQUIRED_CHANNEL, "https://t.me/ReseliBotChannel", "📢 Canal oficial"),
    (REQUIRED_GROUP,   "https://t.me/ReseliBotGroup",   "💬 Grupo oficial"),
]


async def check_membership(bot: Bot, user_id: int) -> tuple[bool, list[tuple[str, str]]]:
    """
    Check if the user is a member of all required chats.
    Returns (all_joined: bool, missing: list[(url, label)])
    """
    if not REQUIRED_GROUP and not REQUIRED_CHANNEL:
        return True, []

    missing = []
    for chat_id, url, label in _CHATS:
        if not chat_id:
            continue
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ("left", "kicked", "banned"):
                missing.append((url, label))
        except Exception:
            # If bot can't check (not admin, chat doesn't exist, etc.) — assume not joined
            missing.append((url, label))

    return len(missing) == 0, missing


def join_required_message(lang: str, missing: list[tuple[str, str]]) -> tuple[str, InlineKeyboardMarkup]:
    """
    Build the 'you must join' message and keyboard.
    Returns (text, keyboard).
    """
    join_btns = [[InlineKeyboardButton(label, url=url)] for url, label in missing]
    join_btns.append([InlineKeyboardButton(
        "✅ Ya me uní — Verificar" if lang == "es" else "✅ I joined — Verify",
        callback_data="check_membership"
    )])

    if lang == "es":
        text = (
            "🔒 <b>Acceso restringido</b>\n\n"
            "Para usar el bot debes unirte obligatoriamente a:\n\n"
            + "".join(f"• {label}\n" for _, label in missing)
            + "\nUna vez que te hayas unido, pulsa el botón de verificar 👇"
        )
    else:
        text = (
            "🔒 <b>Access restricted</b>\n\n"
            "To use the bot you must join:\n\n"
            + "".join(f"• {label}\n" for _, label in missing)
            + "\nOnce you've joined, press the verify button below 👇"
        )

    return text, InlineKeyboardMarkup(join_btns)
