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


def stock_badge(qty: int, lang: str) -> str:
    """Returns a stock status badge string."""
    if qty == 0:
        return "🔴 " + ("No stock" if lang == "en" else "Sin stock")
    if qty <= 3:
        return f"🟡 {qty} " + ("left" if lang == "en" else "disponibles")
    return f"🟢 {qty} " + ("in stock" if lang == "en" else "disponibles")


def catalog_kb(lang: str = "en", stock_levels: dict = None) -> InlineKeyboardMarkup:
    stock_levels = stock_levels or {}
    buttons = []
    for svc in SERVICES.values():
        qty = stock_levels.get(svc["id"], 0)
        badge = f" | {stock_badge(qty, lang)}" if stock_levels else ""
        buttons.append([
            InlineKeyboardButton(
                f"{svc['emoji']} {svc['name']} — ${svc['price']:.2f}{badge}",
                callback_data=f"service_{svc['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(t("btn_home", lang), callback_data="home")])
    return InlineKeyboardMarkup(buttons)


def service_detail_kb(service_id: str, lang: str = "en", stock_qty: int = -1) -> InlineKeyboardMarkup:
    """
    If stock_qty >= 0, shows a "Select quantity" button instead of direct buy.
    If stock_qty < 0 (unknown), shows direct buy.
    """
    rows = []
    if stock_qty == 0:
        # Out of stock — disable buy, show contact support
        rows.append([InlineKeyboardButton(
            "🔴 " + ("Out of stock" if lang == "en" else "Sin stock"),
            callback_data="noop"
        )])
    elif stock_qty > 0:
        rows.append([InlineKeyboardButton(
            "🛒 " + ("Select quantity" if lang == "en" else "Seleccionar cantidad"),
            callback_data=f"qtysel_{service_id}"
        )])
    else:
        # No stock info — direct buy
        rows.append([InlineKeyboardButton(t("btn_buy_now", lang), callback_data=f"buy_{service_id}")])
    rows.append([InlineKeyboardButton(t("btn_to_catalog", lang), callback_data="catalog")])
    return InlineKeyboardMarkup(rows)


def quantity_kb(service_id: str, unit_price: float, max_stock: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Quantity selector with discount labels."""
    from utils.delivery import apply_discount

    options = [1, 2, 3, 5, 10, 20]
    rows = []
    row = []
    for qty in options:
        if qty > max_stock:
            continue
        _, total, rate = apply_discount(unit_price, qty)
        disc_label = f" (-{int(rate*100)}%)" if rate > 0 else ""
        label = f"{qty}x = ${total:.2f}{disc_label}"
        row.append(InlineKeyboardButton(label, callback_data=f"qty_{service_id}_{qty}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data=f"service_{service_id}")])
    return InlineKeyboardMarkup(rows)


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
