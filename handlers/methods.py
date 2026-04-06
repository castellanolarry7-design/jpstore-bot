"""
methods.py – Methods section handler
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import METHODS, USDT_TRC20, USDT_BEP20, BINANCE_PAY_ENABLED, BINANCE_PAY_ID
import database as db
from strings import t
from utils.notifications import notify_admins_new_order


def _method_price_str(method: dict, lang: str) -> str:
    return f"${method['price']:.2f} USDT"


def methods_catalog_kb(lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for m in METHODS.values():
        price_str = f"${m['price']:.2f} USDT"
        buttons.append([
            InlineKeyboardButton(
                f"{m['emoji']} {m['name']} — {price_str}",
                callback_data=f"method_{m['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(t("btn_home", lang), callback_data="home")])
    return InlineKeyboardMarkup(buttons)


def method_detail_kb(method_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_buy_now", lang), callback_data=f"mbuy_{method_id}")],
        [InlineKeyboardButton(t("btn_back", lang),    callback_data="methods")],
    ])


def method_payment_kb(method_id: str, lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🔵 USDT TRC20",  callback_data=f"mpay_trc20_{method_id}")],
        [InlineKeyboardButton("🟡 USDT BEP20",  callback_data=f"mpay_bep20_{method_id}")],
        [InlineKeyboardButton("🟠 Binance Pay", callback_data=f"mpay_binance_{method_id}")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data=f"method_{method_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


# ── Show all methods ──────────────────────────────────────────────────────────

async def show_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = await db.get_user_lang(query.from_user.id)
    await query.edit_message_text(
        t("methods_title", lang),
        parse_mode="HTML",
        reply_markup=methods_catalog_kb(lang)
    )


# ── Show method detail ────────────────────────────────────────────────────────

async def show_method_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    method_id = query.data.split("_", 1)[1]  # method_<id>
    method = METHODS.get(method_id)
    if not method:
        await query.answer("Method not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)
    desc = method["description"].get(lang) or method["description"]["en"]
    delivery = method["delivery"].get(lang) or method["delivery"]["en"]

    text = t("method_detail", lang,
             emoji=method["emoji"],
             name=method["name"],
             description=desc,
             price=f"${method['price']:.2f} USDT",
             delivery=delivery)

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=method_detail_kb(method_id, lang)
    )


# ── Show payment options for method ──────────────────────────────────────────

async def show_method_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    method_id = query.data.split("_", 1)[1]  # mbuy_<id>
    method = METHODS.get(method_id)
    if not method:
        await query.answer("Method not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)
    text = t("choose_payment", lang,
             emoji=method["emoji"],
             name=method["name"],
             price=f"{method['price']:.2f}")

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=method_payment_kb(method_id, lang)
    )


# ── Initiate method payment ───────────────────────────────────────────────────

async def initiate_method_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: mpay_<network>_<method_id>"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_", 2)   # ['mpay', 'trc20'|'bep20'|'binance', method_id]
    network   = parts[1]
    method_id = parts[2]
    method    = METHODS.get(method_id)
    if not method:
        await query.answer("Method not found.", show_alert=True)
        return

    lang = await db.get_user_lang(query.from_user.id)

    # ── Binance Pay (manual by ID) ─────────────────────────────────────────────
    if network == "binance":
        order_id = await db.create_order(
            user_id=query.from_user.id,
            service_id=method_id,
            amount=method["price"],
            payment_method="binance_pay",
            item_type="method",
        )

        if lang == "en":
            steps = (
                "1️⃣ Open <b>Binance App</b>\n"
                "2️⃣ Go to <b>Pay</b> → <b>Send</b>\n"
                "3️⃣ Search by ID: <code>{bp_id}</code>\n"
                "4️⃣ Enter amount: <b>${price} USDT</b>\n"
                "5️⃣ Press the button below to send proof ✅"
            )
            warning = "⚠️ Send the <b>exact amount</b> in <b>USDT</b>."
            order_label = "Order"
        else:
            steps = (
                "1️⃣ Abre la <b>App de Binance</b>\n"
                "2️⃣ Ve a <b>Pay</b> → <b>Enviar</b>\n"
                "3️⃣ Busca por ID: <code>{bp_id}</code>\n"
                "4️⃣ Ingresa el monto: <b>${price} USDT</b>\n"
                "5️⃣ Presiona el botón abajo para enviar comprobante ✅"
            )
            warning = "⚠️ Envía el <b>monto exacto</b> en <b>USDT</b>."
            order_label = "Pedido"

        text = (
            f"🟠 <b>Binance Pay</b>\n\n"
            f"{method['emoji']} <b>{method['name']}</b>\n"
            f"💵 <b>${method['price']:.2f} USDT</b>\n"
            f"🆔 {order_label}: <b>#{order_id}</b>\n\n"
            f"📲 <b>Binance Pay ID:</b>\n"
            f"<code>{BINANCE_PAY_ID}</code>\n\n"
            + steps.format(bp_id=BINANCE_PAY_ID, price=f"{method['price']:.2f}") +
            f"\n\n{warning}"
        )

        from utils.keyboards import order_confirm_kb
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=order_confirm_kb(order_id, lang)
        )
        return

    # ── TRC20 / BEP20 ─────────────────────────────────────────────────────────
    order_id = await db.create_order(
        user_id=query.from_user.id,
        service_id=method_id,
        amount=method["price"],
        payment_method=network,
        item_type="method",
    )

    if network == "trc20":
        address  = USDT_TRC20 or "⚠️ Address not configured"
        net_name = "🔵 <b>USDT TRC20 (TRON)</b>"
        warning  = t("warning_trc20", lang)
    else:
        address  = USDT_BEP20 or "⚠️ Address not configured"
        net_name = "🟡 <b>USDT BEP20 (BSC)</b>"
        warning  = t("warning_bep20", lang)

    text = t("payment_crypto", lang,
             order_id=order_id,
             emoji=method["emoji"],
             name=method["name"],
             price=f"{method['price']:.2f}",
             network=net_name,
             address=address,
             warning=warning)

    from utils.keyboards import order_confirm_kb
    await query.edit_message_text(text, parse_mode="HTML",
                                   reply_markup=order_confirm_kb(order_id, lang))


async def _poll_method_binance(bot, user_id, order_id, prepay_id, method, lang):
    from payments.binance_pay import poll_payment
    try:
        final = await poll_payment(prepay_id, timeout_seconds=900, interval=15)
    except Exception as e:
        print(f"[Binance Method polling] {e}")
        return

    order = await db.get_order(order_id)
    if not order or order["status"] != "pending":
        return

    if final == "PAID":
        await db.update_order_status(order_id, "paid", admin_note="Auto Binance Pay – method")
        user = await db.get_user(user_id)
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>{'Payment confirmed!' if lang=='en' else '¡Pago confirmado!'}</b>\n\n"
                f"{'Order' if lang=='en' else 'Pedido'} #{order_id} – {method['emoji']} <b>{method['name']}</b>\n\n"
                + ("We'll deliver your method shortly! ⚡" if lang == "en"
                   else "¡Te entregaremos el método en breve! ⚡")
            ),
            parse_mode="HTML"
        )
        await notify_admins_new_order(bot, order, user)
    elif final in ("EXPIRED", "CANCELED"):
        await db.update_order_status(order_id, "cancelled", admin_note=f"Binance: {final}")
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ " + (f"Order #{order_id} expired/cancelled." if lang == "en"
                           else f"Pedido #{order_id} expirado/cancelado."),
            parse_mode="HTML"
        )
