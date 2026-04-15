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
        [InlineKeyboardButton(t("btn_balance",   lang), callback_data="balance"),
         InlineKeyboardButton(t("btn_recargar",  lang), callback_data="recargar")],
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
    rows = []
    if stock_qty == 0:
        rows.append([InlineKeyboardButton(
            "🔴 " + ("Out of stock" if lang == "en" else "Sin stock"),
            callback_data="noop"
        )])
    elif stock_qty > 0:
        # Route through quantity selector (+/- interface)
        rows.append([InlineKeyboardButton(
            "🛒 " + ("Buy — select quantity" if lang == "en" else "Comprar — elegir cantidad"),
            callback_data=f"qtysel_{service_id}"
        )])
    else:
        # No stock info — direct buy, qty=1
        rows.append([InlineKeyboardButton(t("btn_buy_now", lang), callback_data=f"buy_{service_id}")])
    rows.append([InlineKeyboardButton(t("btn_to_catalog", lang), callback_data="catalog")])
    return InlineKeyboardMarkup(rows)


def qty_control_kb(service_id: str, unit_price: float, qty: int,
                   max_stock: int, lang: str = "en") -> InlineKeyboardMarkup:
    """
    +/- quantity selector.
    Row 1: ➖  [qty]  ➕
    Row 2: 🛒 Buy xN — $XX.XX  (with discount label if applicable)
    Row 3: discount hint when close to next tier
    Row 4: ◀️ Back
    """
    from utils.delivery import apply_discount
    _, total, rate = apply_discount(unit_price, qty)

    disc_label = f" (-{int(rate*100)}%)" if rate > 0 else ""
    if lang == "en":
        buy_label = f"🛒 Buy x{qty} — ${total:.2f} USDT{disc_label}"
    else:
        buy_label = f"🛒 Comprar x{qty} — ${total:.2f} USDT{disc_label}"

    # Hint about next discount tier
    hint = None
    if rate == 0 and max_stock >= 6:
        gap = 6 - qty
        if gap > 0:
            hint = (f"💡 +{gap} more → 10% off" if lang == "en"
                    else f"💡 +{gap} más → 10% descuento")
    elif rate < 0.15 and max_stock >= 16:
        gap = 16 - qty
        if gap > 0:
            hint = (f"💡 +{gap} more → 15% off" if lang == "en"
                    else f"💡 +{gap} más → 15% descuento")

    # ➖ button goes to max(1, qty-1), ➕ goes to min(max_stock, qty+1)
    prev_qty = max(1, qty - 1)
    next_qty = min(max_stock, qty + 1)

    rows = [
        [
            InlineKeyboardButton("➖", callback_data=f"qtyctrl_{service_id}_{prev_qty}"),
            InlineKeyboardButton(str(qty),  callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"qtyctrl_{service_id}_{next_qty}"),
        ],
        [InlineKeyboardButton(buy_label, callback_data=f"qty_{service_id}_{qty}")],
    ]
    if hint:
        rows.append([InlineKeyboardButton(hint, callback_data="noop")])
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data=f"service_{service_id}")])
    return InlineKeyboardMarkup(rows)


def quantity_kb(service_id: str, unit_price: float, max_stock: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Legacy fixed-options selector — kept for backward compat."""
    return qty_control_kb(service_id, unit_price, 1, max_stock, lang)


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
        [InlineKeyboardButton("✅ Marcar PAGADO",  callback_data=f"admin_paid_{order_id}"),
         InlineKeyboardButton("🚀 ENTREGAR",       callback_data=f"admin_deliver_{order_id}")],
        [InlineKeyboardButton("❌ Cancelar",       callback_data=f"admin_cancel_{order_id}")],
    ])


def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Pedidos pendientes",  callback_data="admin_pending"),
         InlineKeyboardButton("📊 Estadísticas",        callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Usuarios",            callback_data="admin_users"),
         InlineKeyboardButton("📢 Broadcast",           callback_data="admin_broadcast")],
        [InlineKeyboardButton("📦 Gestión de Stock",    callback_data="admin_stock")],
    ])


def back_to_orders_kb(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_my_orders", lang), callback_data="my_orders")],
        [InlineKeyboardButton(t("btn_home", lang),      callback_data="home")],
    ])
