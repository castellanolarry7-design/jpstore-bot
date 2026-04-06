"""
keyboards.py – Reusable inline keyboards (language-aware)
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import SERVICES
from strings import t


def main_menu_kb(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_catalog",   lang), callback_data="catalog"),
         InlineKeyboardButton(t("btn_methods",   lang), callback_data="methods")],
        [InlineKeyboardButton(t("btn_my_orders", lang), callback_data="my_orders")],
        [InlineKeyboardButton(t("btn_referrals", lang), callback_data="referrals"),
         InlineKeyboardButton(t("btn_support",   lang), callback_data="support")],
        [InlineKeyboardButton(t("btn_language",  lang), callback_data="language")],
    ])


def language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en"),
         InlineKeyboardButton("🇪🇸 Español", callback_data="setlang_es")],
    ])


def catalog_kb(lang: str = "en") -> InlineKeyboardMarkup:
    buttons = []
    for svc in SERVICES.values():
        buttons.append([
            InlineKeyboardButton(
                f"{svc['emoji']} {svc['name']} — ${svc['price']:.2f} USDT",
                callback_data=f"service_{svc['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(t("btn_home", lang), callback_data="home")])
    return InlineKeyboardMarkup(buttons)


def service_detail_kb(service_id: str, lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_buy_now", lang),    callback_data=f"buy_{service_id}")],
        [InlineKeyboardButton(t("btn_to_catalog", lang), callback_data="catalog")],
    ])


def payment_method_kb(service_id: str, lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 USDT TRC20 (TRON)",  callback_data=f"pay_trc20_{service_id}")],
        [InlineKeyboardButton("🟡 USDT BEP20 (BSC)",   callback_data=f"pay_bep20_{service_id}")],
        [InlineKeyboardButton("🟠 Binance Pay",         callback_data=f"pay_binance_{service_id}")],
        [InlineKeyboardButton(t("btn_back", lang),       callback_data=f"service_{service_id}")],
    ])


def order_confirm_kb(order_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_proof", lang),  callback_data=f"proof_{order_id}")],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"cancel_{order_id}")],
    ])


def admin_order_kb(order_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Mark PAID",    callback_data=f"admin_paid_{order_id}"),
            InlineKeyboardButton("🚀 DELIVER",      callback_data=f"admin_deliver_{order_id}"),
        ],
        [
            InlineKeyboardButton("❌ Cancel",        callback_data=f"admin_cancel_{order_id}"),
            InlineKeyboardButton("💬 Message user",  callback_data=f"admin_msg_{user_id}"),
        ],
    ])


def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Pending Orders",  callback_data="admin_pending")],
        [InlineKeyboardButton("📊 Statistics",      callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Users",           callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast",       callback_data="admin_broadcast")],
    ])


def back_to_orders_kb(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_my_orders", lang), callback_data="my_orders")],
        [InlineKeyboardButton(t("btn_home", lang),      callback_data="home")],
    ])
