"""
membership.py – Mandatory group/channel join gate (per-chat status tracking)

The gate message shows ✅ / ❌ for each required chat in real time.
Pressing "Verify" refreshes the status without leaving the message.
The bot must be admin in both chats for get_chat_member() to work.
"""
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import REQUIRED_GROUP, REQUIRED_CHANNEL

# Each entry: (chat_id_var, public_url, display_label)
# The URL must be the public t.me link so non-members can open/join.
_CHATS = [
    (REQUIRED_CHANNEL, "https://t.me/ReseliBotChannel", "📢 Official Channel"),
    (REQUIRED_GROUP,   "https://t.me/ReseliBotGroup",   "💬 Official Group"),
]


# ── Core check ────────────────────────────────────────────────────────────────

async def check_membership_detail(
    bot: Bot, user_id: int
) -> list[tuple[str, str, str, bool]]:
    """
    Returns one entry per required chat:
      (chat_id, url, label, is_member)

    is_member is True only if the user has an active membership status.
    If the bot can't check (not admin, chat not found, etc.) → treated as not joined.
    """
    result = []
    for chat_id, url, label in _CHATS:
        if not chat_id:
            continue
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            joined = member.status not in ("left", "kicked", "banned")
        except Exception:
            joined = False
        result.append((chat_id, url, label, joined))
    return result


async def check_membership(
    bot: Bot, user_id: int
) -> tuple[bool, list[tuple[str, str]]]:
    """
    Backward-compatible wrapper.
    Returns (all_joined, missing_list[(url, label)]).
    """
    if not REQUIRED_GROUP and not REQUIRED_CHANNEL:
        return True, []

    detail  = await check_membership_detail(bot, user_id)
    missing = [(url, label) for _, url, label, joined in detail if not joined]
    return len(missing) == 0, missing


# ── Message builder ───────────────────────────────────────────────────────────

def build_gate_message(
    statuses: list[tuple[str, str, str, bool]]
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Build the live-status gate message.

    For each chat shows ✅ (joined) or ❌ (not joined yet).
    Only pending chats have a [Join →] button.
    Always in English regardless of user language.
    """
    all_joined = all(joined for _, _, _, joined in statuses)

    # ── Text ──────────────────────────────────────────────────────────────────
    status_lines = ""
    for _, _, label, joined in statuses:
        icon = "✅" if joined else "❌"
        status_lines += f"{icon}  {label}\n"

    if all_joined:
        text = (
            "✅ <b>All requirements met!</b>\n\n"
            + status_lines
            + "\nYou're all set. Tap <b>Enter the store</b> below 👇"
        )
    else:
        text = (
            "🔒 <b>Access Restricted</b>\n\n"
            "To use the bot you must join the following:\n\n"
            + status_lines
            + "\nJoin the ones marked ❌ then press <b>Verify</b> 👇"
        )

    # ── Keyboard ──────────────────────────────────────────────────────────────
    buttons = []

    # One row per pending chat with a direct join link
    for _, url, label, joined in statuses:
        if not joined:
            buttons.append([
                InlineKeyboardButton(f"➡️ Join {label}", url=url)
            ])

    # Verify / Enter button
    if all_joined:
        buttons.append([
            InlineKeyboardButton("🚀 Enter the store", callback_data="check_membership")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("✅ I joined — Verify", callback_data="check_membership")
        ])

    return text, InlineKeyboardMarkup(buttons)


# ── Legacy helper (kept for any remaining callers) ────────────────────────────

def join_required_message(
    lang: str, missing: list[tuple[str, str]]
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Backward-compatible version that takes a missing list.
    Builds a simple gate message (no per-chat status).
    Used as a fallback if detail check is not available.
    """
    join_btns = [
        [InlineKeyboardButton(f"➡️ Join {label}", url=url)]
        for url, label in missing
    ]
    join_btns.append([
        InlineKeyboardButton("✅ I joined — Verify", callback_data="check_membership")
    ])

    status_lines = "".join(f"❌  {label}\n" for _, label in missing)
    text = (
        "🔒 <b>Access Restricted</b>\n\n"
        "To use the bot you must join the following:\n\n"
        + status_lines
        + "\nJoin the ones marked ❌ then press <b>Verify</b> 👇"
    )

    return text, InlineKeyboardMarkup(join_btns)
