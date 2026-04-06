"""
strings.py – Bilingual text system (English / Spanish)
Usage: from strings import t
       t('welcome', lang, store_name="JPStore")
"""

STRINGS: dict = {
    # ── GENERAL ──────────────────────────────────────────────────────────────
    "welcome": {
        "en": (
            "👋 <b>Welcome to {store_name}!</b>\n\n"
            "🌟 <i>{description}</i>\n\n"
            "💳 <b>Payment methods:</b> USDT TRC20 · USDT BEP20 · Binance Pay\n\n"
            "Choose an option below 👇"
        ),
        "es": (
            "👋 <b>¡Bienvenido a {store_name}!</b>\n\n"
            "🌟 <i>{description}</i>\n\n"
            "💳 <b>Métodos de pago:</b> USDT TRC20 · USDT BEP20 · Binance Pay\n\n"
            "Elige una opción 👇"
        ),
    },
    "choose_language": {
        "en": "🌐 <b>Choose your language / Elige tu idioma:</b>",
        "es": "🌐 <b>Choose your language / Elige tu idioma:</b>",
    },
    "language_set": {
        "en": "✅ Language set to <b>English</b>.",
        "es": "✅ Idioma configurado a <b>Español</b>.",
    },

    # ── MENU BUTTONS ─────────────────────────────────────────────────────────
    "btn_catalog":    {"en": "🛍️ Catalog",        "es": "🛍️ Catálogo"},
    "btn_methods":    {"en": "⚡ Methods",         "es": "⚡ Métodos"},
    "btn_my_orders":  {"en": "📦 My Orders",       "es": "📦 Mis Pedidos"},
    "btn_referrals":  {"en": "🎁 Referrals",       "es": "🎁 Referidos"},
    "btn_support":    {"en": "💬 Support",         "es": "💬 Soporte"},
    "btn_language":   {"en": "🌐 Language",        "es": "🌐 Idioma"},
    "btn_back":       {"en": "◀️ Back",            "es": "◀️ Volver"},
    "btn_home":       {"en": "🏠 Home",            "es": "🏠 Inicio"},
    "btn_buy_now":    {"en": "🛒 Buy Now",         "es": "🛒 Comprar ahora"},
    "btn_cancel":     {"en": "❌ Cancel Order",    "es": "❌ Cancelar pedido"},
    "btn_to_catalog": {"en": "◀️ Back to Catalog", "es": "◀️ Volver al catálogo"},

    # ── CATALOG ───────────────────────────────────────────────────────────────
    "catalog_title": {
        "en": "🛍️ <b>Service Catalog</b>\n\nSelect a service to see details:",
        "es": "🛍️ <b>Catálogo de Servicios</b>\n\nSelecciona un servicio para ver detalles:",
    },
    "service_detail": {
        "en": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Price:</b> {price}\n🚀 <b>Delivery:</b> {delivery}",
        "es": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Precio:</b> {price}\n🚀 <b>Entrega:</b> {delivery}",
    },
    "choose_payment": {
        "en": (
            "💳 <b>Payment Method</b>\n\n"
            "Service: {emoji} <b>{name}</b>\n"
            "Amount: <b>${price} USDT</b>\n\n"
            "Select how you want to pay:"
        ),
        "es": (
            "💳 <b>Método de Pago</b>\n\n"
            "Servicio: {emoji} <b>{name}</b>\n"
            "Monto: <b>${price} USDT</b>\n\n"
            "Selecciona cómo deseas pagar:"
        ),
    },

    # ── PAYMENT ───────────────────────────────────────────────────────────────
    "payment_crypto": {
        "en": (
            "📋 <b>Order #{order_id} created</b>\n\n"
            "🛒 Service: {emoji} <b>{name}</b>\n"
            "💵 Exact amount: <b>${price} USDT</b>\n"
            "💳 Network: {network}\n\n"
            "📤 <b>Send to this address:</b>\n"
            "<code>{address}</code>\n\n"
            "{warning}\n\n"
            "✅ After paying, press the button to send your proof."
        ),
        "es": (
            "📋 <b>Pedido #{order_id} creado</b>\n\n"
            "🛒 Servicio: {emoji} <b>{name}</b>\n"
            "💵 Monto exacto: <b>${price} USDT</b>\n"
            "💳 Red: {network}\n\n"
            "📤 <b>Envía a esta dirección:</b>\n"
            "<code>{address}</code>\n\n"
            "{warning}\n\n"
            "✅ Después de pagar, presiona el botón para enviar tu comprobante."
        ),
    },
    "warning_trc20": {
        "en": "⚠️ Send <b>ONLY</b> on the <b>TRON (TRC20)</b> network. Wrong network = lost funds.",
        "es": "⚠️ Envía ÚNICAMENTE por la red <b>TRON (TRC20)</b>. Red incorrecta = fondos perdidos.",
    },
    "warning_bep20": {
        "en": "⚠️ Send <b>ONLY</b> on the <b>BSC (BEP20)</b> network. Wrong network = lost funds.",
        "es": "⚠️ Envía ÚNICAMENTE por la red <b>BSC (BEP20)</b>. Red incorrecta = fondos perdidos.",
    },
    "send_proof": {
        "en": (
            "📸 <b>Send your payment proof</b>\n\n"
            "Order #{order_id}\n\n"
            "You can send:\n"
            "• 📷 A screenshot of the transaction\n"
            "• 🔗 The TX hash/ID (as text)\n\n"
            "<i>Type /cancel to abort.</i>"
        ),
        "es": (
            "📸 <b>Envía tu comprobante de pago</b>\n\n"
            "Pedido #{order_id}\n\n"
            "Puedes enviar:\n"
            "• 📷 Captura de pantalla de la transacción\n"
            "• 🔗 Hash/TX ID de la transferencia (texto)\n\n"
            "<i>Escribe /cancelar para cancelar.</i>"
        ),
    },
    "proof_received": {
        "en": (
            "✅ <b>Proof received!</b>\n\n"
            "Order #{order_id}\n\n"
            "We'll verify your payment and deliver within <b>24 hours</b> ⏱️"
        ),
        "es": (
            "✅ <b>Comprobante recibido!</b>\n\n"
            "Pedido #{order_id}\n\n"
            "Verificaremos tu pago y entregaremos en <b>24 horas</b> ⏱️"
        ),
    },
    "btn_proof": {
        "en": "✅ I paid – send proof",
        "es": "✅ Ya pagué – enviar comprobante",
    },

    # ── MY ORDERS ─────────────────────────────────────────────────────────────
    "my_orders_empty": {
        "en": "📦 <b>My Orders</b>\n\nYou don't have any orders yet. Explore the catalog!",
        "es": "📦 <b>Mis Pedidos</b>\n\nAún no tienes pedidos. ¡Explora el catálogo!",
    },
    "my_orders_title": {
        "en": "📦 <b>My Orders</b>\n",
        "es": "📦 <b>Mis Pedidos</b>\n",
    },

    # ── METHODS SECTION ───────────────────────────────────────────────────────
    "methods_title": {
        "en": (
            "⚡ <b>Methods</b>\n\n"
            "Buy proven methods to access premium AI tools at a fraction of the cost.\n\n"
            "Select a method below:"
        ),
        "es": (
            "⚡ <b>Métodos</b>\n\n"
            "Compra métodos probados para acceder a herramientas IA premium a bajo costo.\n\n"
            "Selecciona un método:"
        ),
    },
    "method_detail": {
        "en": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Price:</b> {price}\n🚀 <b>Delivery:</b> {delivery}",
        "es": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Precio:</b> {price}\n🚀 <b>Entrega:</b> {delivery}",
    },

    # ── REFERRALS ─────────────────────────────────────────────────────────────
    "referrals_info": {
        "en": (
            "🎁 <b>Referral Program</b>\n\n"
            "Share your link and earn <b>$1.00 credit</b> for every friend who makes a purchase!\n\n"
            "🔗 <b>Your referral link:</b>\n"
            "<code>{link}</code>\n\n"
            "👥 Friends referred: <b>{count}</b>\n"
            "💰 Credits earned: <b>${credits:.2f} USDT</b>\n\n"
            "💡 Credits are applied automatically to your next order."
        ),
        "es": (
            "🎁 <b>Programa de Referidos</b>\n\n"
            "Comparte tu link y gana <b>$1.00 de crédito</b> por cada amigo que realice una compra.\n\n"
            "🔗 <b>Tu link de referido:</b>\n"
            "<code>{link}</code>\n\n"
            "👥 Amigos referidos: <b>{count}</b>\n"
            "💰 Créditos ganados: <b>${credits:.2f} USDT</b>\n\n"
            "💡 Los créditos se aplican automáticamente a tu próximo pedido."
        ),
    },
    "referral_welcome_bonus": {
        "en": "🎉 You joined via a referral link! Your friend will earn $1.00 credit when you make your first purchase.",
        "es": "🎉 ¡Entraste a través de un link de referido! Tu amigo ganará $1.00 de crédito cuando hagas tu primera compra.",
    },
    "referral_credited": {
        "en": "💰 <b>+$1.00 credit earned!</b>\nYour referral <b>{name}</b> just made their first purchase. Credit added to your account!",
        "es": "💰 <b>¡+$1.00 de crédito ganado!</b>\nTu referido <b>{name}</b> acaba de hacer su primera compra. ¡Crédito añadido a tu cuenta!",
    },
    "btn_copy_link":     {"en": "📋 Copy Link",     "es": "📋 Copiar Link"},
    "btn_share_link":    {"en": "📤 Share",         "es": "📤 Compartir"},

    # ── SUPPORT ───────────────────────────────────────────────────────────────
    "support_text": {
        "en": (
            "💬 <b>Support</b>\n\n"
            "📩 Contact us directly: {username}\n\n"
            "⏱️ Average response time: <b>under 2 hours</b>\n"
            "🕐 Hours: Monday–Sunday, 9am–10pm"
        ),
        "es": (
            "💬 <b>Soporte</b>\n\n"
            "📩 Contáctanos: {username}\n\n"
            "⏱️ Tiempo de respuesta: <b>menos de 2 horas</b>\n"
            "🕐 Horario: Lunes a Domingo, 9am – 10pm"
        ),
    },
    "cancelled": {
        "en": "❌ Operation cancelled.",
        "es": "❌ Operación cancelada.",
    },
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated string for a given key and language."""
    lang = lang if lang in ("en", "es") else "en"
    entry = STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("en") or f"[{key}]"
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
