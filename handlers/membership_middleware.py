"""
membership_middleware.py – Global TypeHandler (group=-1) that runs before every update.

• Whitelisted updates (admin callbacks, language, /start itself) are always allowed through.
• For all other updates: checks if the user is a member of all required chats.
• If NOT a member: sends/edits the membership gate and raises ApplicationHandlerStop
  so no other handler processes this update.
• Caches membership result per-user for 5 minutes to avoid Telegram API spam.
• When a previously-approved user is no longer a member (cache expired),
  they get a friendly explanation instead of the bot silently ignoring them.
"""
import time
import logging

from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

import database as db
from config import ADMIN_IDS
from utils.membership import check_membership_detail, build_gate_message
from handlers.start import _get_welcome_photo, _send_gate, _edit_gate

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5 minutes)
_CACHE_TTL = 300

# Callback data that must always pass through even when not a member
_ALWAYS_ALLOW_CALLBACKS = {
    "check_membership",
    "home",
    "language",
}
_ALWAYS_ALLOW_CALLBACK_PREFIXES = (
    "setlang_",
    "admin_",      # admins must never get blocked
)

# Commands that always pass through
_ALWAYS_ALLOW_COMMANDS = {
    "/start",
    "/weboadmin",
    "/setphoto",
    "/estadisticas",
    "/addstock",
    "/stock",
    "/cancel",
    "/cancelar",
}


def _is_whitelisted(update: Update) -> bool:
    """Return True if this update should bypass the membership gate."""
    if update.callback_query:
        data = update.callback_query.data or ""
        if data in _ALWAYS_ALLOW_CALLBACKS:
            return True
        if any(data.startswith(p) for p in _ALWAYS_ALLOW_CALLBACK_PREFIXES):
            return True
        return False

    if update.message:
        text = (update.message.text or "").strip()
        if text.startswith("/"):
            cmd = text.split()[0].split("@")[0].lower()
            return cmd in _ALWAYS_ALLOW_COMMANDS
        return False

    # All other update types (edited messages, inline, chat_member, etc.) — allow
    return True


async def membership_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    TypeHandler callback registered in group=-1.
    Raises ApplicationHandlerStop when the user fails the membership check.
    """
    user = update.effective_user
    if user is None:
        return  # no user context — let it pass

    user_id = user.id

    # Admins are always allowed through — never gate them
    if user_id in ADMIN_IDS:
        return

    # Whitelisted updates always pass
    if _is_whitelisted(update):
        return

    # ── Check cache ───────────────────────────────────────────────────────────
    cache       = context.user_data.setdefault("_membership_cache", {})
    cached_at   = cache.get("checked_at", 0)
    cached_ok   = cache.get("all_ok", None)
    now         = time.time()

    if cached_ok is True and (now - cached_at) < _CACHE_TTL:
        return  # cached positive result — allow through

    # ── Live membership check ─────────────────────────────────────────────────
    try:
        statuses = await check_membership_detail(context.bot, user_id)
    except Exception as e:
        logger.warning(f"[MembershipMiddleware] check failed for {user_id}: {e}")
        return  # on error, don't block

    all_ok = all(is_member for _, _, _, is_member in statuses)

    # Update cache
    cache["checked_at"] = now
    cache["all_ok"]     = all_ok

    if all_ok:
        return  # member — let through

    # ── Not a member — was this a previously-approved user? ───────────────────
    was_previously_ok = cached_ok is True  # had a valid cached True that has now expired

    lang = await db.get_user_lang(user_id)
    gate_text, gate_kb = build_gate_message(statuses)

    if was_previously_ok:
        if lang == "es":
            notice = (
                "⚠️ <b>Parece que saliste de uno de nuestros canales requeridos.</b>\n"
                "Por eso el bot dejó de responder. ¡Vuelve a unirte para continuar!\n\n"
            )
        else:
            notice = (
                "⚠️ <b>It looks like you left one of our required channels.</b>\n"
                "That's why the bot stopped responding — rejoin to continue!\n\n"
            )
        gate_text = notice + gate_text

    try:
        if update.callback_query:
            await update.callback_query.answer()
            await _edit_gate(update.callback_query, gate_text, gate_kb)
        elif update.message:
            await _send_gate(update, gate_text, gate_kb)
    except Exception as e:
        logger.warning(f"[MembershipMiddleware] could not send gate to {user_id}: {e}")

    raise ApplicationHandlerStop
