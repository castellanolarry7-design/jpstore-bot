"""
strings.py – Multilingual text system (English / Spanish / Hindi / Indonesian / Urdu / Chinese)
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
        "hi": (
            "👋 <b>{store_name} में आपका स्वागत है!</b>\n\n"
            "🌟 <i>{description}</i>\n\n"
            "💳 <b>भुगतान के तरीके:</b> USDT TRC20 · USDT BEP20 · Binance Pay\n\n"
            "नीचे एक विकल्प चुनें 👇"
        ),
        "id": (
            "👋 <b>Selamat datang di {store_name}!</b>\n\n"
            "🌟 <i>{description}</i>\n\n"
            "💳 <b>Metode pembayaran:</b> USDT TRC20 · USDT BEP20 · Binance Pay\n\n"
            "Pilih opsi di bawah 👇"
        ),
        "ur": (
            "👋 <b>{store_name} میں خوش آمدید!</b>\n\n"
            "🌟 <i>{description}</i>\n\n"
            "💳 <b>ادائیگی کے طریقے:</b> USDT TRC20 · USDT BEP20 · Binance Pay\n\n"
            "نیچے سے ایک آپشن منتخب کریں 👇"
        ),
        "zh": (
            "👋 <b>欢迎来到 {store_name}！</b>\n\n"
            "🌟 <i>{description}</i>\n\n"
            "💳 <b>支付方式：</b>USDT TRC20 · USDT BEP20 · Binance Pay\n\n"
            "请在下方选择一个选项 👇"
        ),
    },
    "choose_language": {
        "en": "🌐 <b>Choose your language:</b>",
        "es": "🌐 <b>Elige tu idioma:</b>",
        "hi": "🌐 <b>अपनी भाषा चुनें:</b>",
        "id": "🌐 <b>Pilih bahasa Anda:</b>",
        "ur": "🌐 <b>اپنی زبان منتخب کریں:</b>",
        "zh": "🌐 <b>选择您的语言：</b>",
    },
    "language_set": {
        "en": "✅ Language set to <b>English</b>.",
        "es": "✅ Idioma configurado a <b>Español</b>.",
        "hi": "✅ भाषा <b>हिंदी</b> पर सेट की गई।",
        "id": "✅ Bahasa diubah ke <b>Indonesia</b>.",
        "ur": "✅ زبان <b>اردو</b> پر سیٹ کی گئی۔",
        "zh": "✅ 语言已设置为<b>中文</b>。",
    },

    # ── MENU BUTTONS ─────────────────────────────────────────────────────────
    "btn_catalog": {
        "en": "🛍️ Catalog",
        "es": "🛍️ Catálogo",
        "hi": "🛍️ कैटलॉग",
        "id": "🛍️ Katalog",
        "ur": "🛍️ کیٹلاگ",
        "zh": "🛍️ 商品目录",
    },
    "btn_methods": {
        "en": "⚡ Methods",
        "es": "⚡ Métodos",
        "hi": "⚡ तरीके",
        "id": "⚡ Metode",
        "ur": "⚡ طریقے",
        "zh": "⚡ 方法",
    },
    "btn_balance": {
        "en": "💰 Balance",
        "es": "💰 Balance",
        "hi": "💰 बैलेंस",
        "id": "💰 Saldo",
        "ur": "💰 بیلنس",
        "zh": "💰 余额",
    },
    "btn_recargar": {
        "en": "💳 Top Up",
        "es": "💳 Recargar",
        "hi": "💳 टॉप अप",
        "id": "💳 Isi Saldo",
        "ur": "💳 ٹاپ اپ",
        "zh": "💳 充值",
    },
    "btn_my_orders": {
        "en": "📦 My Orders",
        "es": "📦 Mis Pedidos",
        "hi": "📦 मेरे ऑर्डर",
        "id": "📦 Pesanan Saya",
        "ur": "📦 میرے آرڈر",
        "zh": "📦 我的订单",
    },
    "btn_referrals": {
        "en": "🎁 Referrals",
        "es": "🎁 Referidos",
        "hi": "🎁 रेफरल",
        "id": "🎁 Referral",
        "ur": "🎁 ریفرل",
        "zh": "🎁 推荐",
    },
    "btn_support": {
        "en": "💬 Support",
        "es": "💬 Soporte",
        "hi": "💬 सपोर्ट",
        "id": "💬 Dukungan",
        "ur": "💬 سپورٹ",
        "zh": "💬 客服",
    },
    "btn_language": {
        "en": "🌐 Language",
        "es": "🌐 Idioma",
        "hi": "🌐 भाषा",
        "id": "🌐 Bahasa",
        "ur": "🌐 زبان",
        "zh": "🌐 语言",
    },
    "btn_back": {
        "en": "◀️ Back",
        "es": "◀️ Volver",
        "hi": "◀️ वापस",
        "id": "◀️ Kembali",
        "ur": "◀️ واپس",
        "zh": "◀️ 返回",
    },
    "btn_home": {
        "en": "🏠 Home",
        "es": "🏠 Inicio",
        "hi": "🏠 होम",
        "id": "🏠 Beranda",
        "ur": "🏠 ہوم",
        "zh": "🏠 主页",
    },
    "btn_buy_now": {
        "en": "🛒 Buy Now",
        "es": "🛒 Comprar ahora",
        "hi": "🛒 अभी खरीदें",
        "id": "🛒 Beli Sekarang",
        "ur": "🛒 ابھی خریدیں",
        "zh": "🛒 立即购买",
    },
    "btn_cancel": {
        "en": "❌ Cancel Order",
        "es": "❌ Cancelar pedido",
        "hi": "❌ ऑर्डर रद्द करें",
        "id": "❌ Batalkan Pesanan",
        "ur": "❌ آرڈر منسوخ کریں",
        "zh": "❌ 取消订单",
    },
    "btn_to_catalog": {
        "en": "◀️ Back to Catalog",
        "es": "◀️ Volver al catálogo",
        "hi": "◀️ कैटलॉग पर वापस",
        "id": "◀️ Kembali ke Katalog",
        "ur": "◀️ کیٹلاگ پر واپس",
        "zh": "◀️ 返回目录",
    },

    # ── CATALOG ───────────────────────────────────────────────────────────────
    "catalog_title": {
        "en": "🛍️ <b>Service Catalog</b>\n\nSelect a service to see details:",
        "es": "🛍️ <b>Catálogo de Servicios</b>\n\nSelecciona un servicio para ver detalles:",
        "hi": "🛍️ <b>सेवा कैटलॉग</b>\n\nविवरण देखने के लिए एक सेवा चुनें:",
        "id": "🛍️ <b>Katalog Layanan</b>\n\nPilih layanan untuk melihat detailnya:",
        "ur": "🛍️ <b>سروس کیٹلاگ</b>\n\nتفصیلات دیکھنے کے لیے ایک سروس منتخب کریں:",
        "zh": "🛍️ <b>服务目录</b>\n\n选择一项服务查看详情：",
    },
    "service_detail": {
        "en": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Price:</b> {price}\n🚀 <b>Delivery:</b> {delivery}",
        "es": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Precio:</b> {price}\n🚀 <b>Entrega:</b> {delivery}",
        "hi": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>मूल्य:</b> {price}\n🚀 <b>डिलीवरी:</b> {delivery}",
        "id": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Harga:</b> {price}\n🚀 <b>Pengiriman:</b> {delivery}",
        "ur": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>قیمت:</b> {price}\n🚀 <b>ڈیلیوری:</b> {delivery}",
        "zh": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>价格：</b>{price}\n🚀 <b>交付：</b>{delivery}",
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
        "hi": (
            "💳 <b>भुगतान विधि</b>\n\n"
            "सेवा: {emoji} <b>{name}</b>\n"
            "राशि: <b>${price} USDT</b>\n\n"
            "भुगतान का तरीका चुनें:"
        ),
        "id": (
            "💳 <b>Metode Pembayaran</b>\n\n"
            "Layanan: {emoji} <b>{name}</b>\n"
            "Jumlah: <b>${price} USDT</b>\n\n"
            "Pilih cara pembayaran Anda:"
        ),
        "ur": (
            "💳 <b>ادائیگی کا طریقہ</b>\n\n"
            "سروس: {emoji} <b>{name}</b>\n"
            "رقم: <b>${price} USDT</b>\n\n"
            "ادائیگی کا طریقہ منتخب کریں:"
        ),
        "zh": (
            "💳 <b>支付方式</b>\n\n"
            "服务：{emoji} <b>{name}</b>\n"
            "金额：<b>${price} USDT</b>\n\n"
            "请选择您的支付方式："
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
        "hi": (
            "📋 <b>ऑर्डर #{order_id} बनाया गया</b>\n\n"
            "🛒 सेवा: {emoji} <b>{name}</b>\n"
            "💵 सटीक राशि: <b>${price} USDT</b>\n"
            "💳 नेटवर्क: {network}\n\n"
            "📤 <b>इस पते पर भेजें:</b>\n"
            "<code>{address}</code>\n\n"
            "{warning}\n\n"
            "✅ भुगतान के बाद, प्रमाण भेजने के लिए बटन दबाएं।"
        ),
        "id": (
            "📋 <b>Pesanan #{order_id} dibuat</b>\n\n"
            "🛒 Layanan: {emoji} <b>{name}</b>\n"
            "💵 Jumlah tepat: <b>${price} USDT</b>\n"
            "💳 Jaringan: {network}\n\n"
            "📤 <b>Kirim ke alamat ini:</b>\n"
            "<code>{address}</code>\n\n"
            "{warning}\n\n"
            "✅ Setelah membayar, tekan tombol untuk mengirimkan bukti."
        ),
        "ur": (
            "📋 <b>آرڈر #{order_id} بنایا گیا</b>\n\n"
            "🛒 سروس: {emoji} <b>{name}</b>\n"
            "💵 عین رقم: <b>${price} USDT</b>\n"
            "💳 نیٹ ورک: {network}\n\n"
            "📤 <b>اس پتے پر بھیجیں:</b>\n"
            "<code>{address}</code>\n\n"
            "{warning}\n\n"
            "✅ ادائیگی کے بعد، ثبوت بھیجنے کے لیے بٹن دبائیں۔"
        ),
        "zh": (
            "📋 <b>订单 #{order_id} 已创建</b>\n\n"
            "🛒 服务：{emoji} <b>{name}</b>\n"
            "💵 精确金额：<b>${price} USDT</b>\n"
            "💳 网络：{network}\n\n"
            "📤 <b>发送到此地址：</b>\n"
            "<code>{address}</code>\n\n"
            "{warning}\n\n"
            "✅ 付款后，请按下按钮发送您的凭证。"
        ),
    },
    "warning_trc20": {
        "en": "⚠️ Send <b>ONLY</b> on the <b>TRON (TRC20)</b> network. Wrong network = lost funds.",
        "es": "⚠️ Envía ÚNICAMENTE por la red <b>TRON (TRC20)</b>. Red incorrecta = fondos perdidos.",
        "hi": "⚠️ केवल <b>TRON (TRC20)</b> नेटवर्क पर भेजें। गलत नेटवर्क = धन खो जाएगा।",
        "id": "⚠️ Kirim HANYA melalui jaringan <b>TRON (TRC20)</b>. Jaringan salah = dana hilang.",
        "ur": "⚠️ صرف <b>TRON (TRC20)</b> نیٹ ورک پر بھیجیں۔ غلط نیٹ ورک = رقم ضائع ہوگی۔",
        "zh": "⚠️ 请仅通过 <b>TRON (TRC20)</b> 网络发送。错误网络 = 资金丢失。",
    },
    "warning_bep20": {
        "en": "⚠️ Send <b>ONLY</b> on the <b>BSC (BEP20)</b> network. Wrong network = lost funds.",
        "es": "⚠️ Envía ÚNICAMENTE por la red <b>BSC (BEP20)</b>. Red incorrecta = fondos perdidos.",
        "hi": "⚠️ केवल <b>BSC (BEP20)</b> नेटवर्क पर भेजें। गलत नेटवर्क = धन खो जाएगा।",
        "id": "⚠️ Kirim HANYA melalui jaringan <b>BSC (BEP20)</b>. Jaringan salah = dana hilang.",
        "ur": "⚠️ صرف <b>BSC (BEP20)</b> نیٹ ورک پر بھیجیں۔ غلط نیٹ ورک = رقم ضائع ہوگی۔",
        "zh": "⚠️ 请仅通过 <b>BSC (BEP20)</b> 网络发送。错误网络 = 资金丢失。",
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
        "hi": (
            "📸 <b>भुगतान प्रमाण भेजें</b>\n\n"
            "ऑर्डर #{order_id}\n\n"
            "आप भेज सकते हैं:\n"
            "• 📷 लेनदेन का स्क्रीनशॉट\n"
            "• 🔗 TX हैश/ID (टेक्स्ट के रूप में)\n\n"
            "<i>रद्द करने के लिए /cancel टाइप करें।</i>"
        ),
        "id": (
            "📸 <b>Kirim bukti pembayaran</b>\n\n"
            "Pesanan #{order_id}\n\n"
            "Anda bisa mengirim:\n"
            "• 📷 Screenshot transaksi\n"
            "• 🔗 Hash TX/ID (sebagai teks)\n\n"
            "<i>Ketik /cancel untuk membatalkan.</i>"
        ),
        "ur": (
            "📸 <b>ادائیگی کا ثبوت بھیجیں</b>\n\n"
            "آرڈر #{order_id}\n\n"
            "آپ بھیج سکتے ہیں:\n"
            "• 📷 ٹرانزیکشن کا اسکرین شاٹ\n"
            "• 🔗 TX ہیش/ID (ٹیکسٹ کے طور پر)\n\n"
            "<i>منسوخ کرنے کے لیے /cancel ٹائپ کریں۔</i>"
        ),
        "zh": (
            "📸 <b>发送付款凭证</b>\n\n"
            "订单 #{order_id}\n\n"
            "您可以发送：\n"
            "• 📷 交易截图\n"
            "• 🔗 TX 哈希/ID（作为文本）\n\n"
            "<i>输入 /cancel 取消。</i>"
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
        "hi": (
            "✅ <b>प्रमाण प्राप्त हुआ!</b>\n\n"
            "ऑर्डर #{order_id}\n\n"
            "हम आपका भुगतान सत्यापित करेंगे और <b>24 घंटे</b> के भीतर डिलीवर करेंगे ⏱️"
        ),
        "id": (
            "✅ <b>Bukti diterima!</b>\n\n"
            "Pesanan #{order_id}\n\n"
            "Kami akan memverifikasi pembayaran Anda dan mengirimkan dalam <b>24 jam</b> ⏱️"
        ),
        "ur": (
            "✅ <b>ثبوت موصول ہوا!</b>\n\n"
            "آرڈر #{order_id}\n\n"
            "ہم آپ کی ادائیگی کی تصدیق کریں گے اور <b>24 گھنٹوں</b> کے اندر ڈیلیور کریں گے ⏱️"
        ),
        "zh": (
            "✅ <b>凭证已收到！</b>\n\n"
            "订单 #{order_id}\n\n"
            "我们将验证您的付款并在 <b>24 小时</b>内交付 ⏱️"
        ),
    },
    "btn_proof": {
        "en": "✅ I paid – send proof",
        "es": "✅ Ya pagué – enviar comprobante",
        "hi": "✅ मैंने भुगतान किया – प्रमाण भेजें",
        "id": "✅ Saya sudah bayar – kirim bukti",
        "ur": "✅ میں نے ادائیگی کی – ثبوت بھیجیں",
        "zh": "✅ 我已付款 – 发送凭证",
    },

    # ── MY ORDERS ─────────────────────────────────────────────────────────────
    "my_orders_empty": {
        "en": "📦 <b>My Orders</b>\n\nYou don't have any orders yet. Explore the catalog!",
        "es": "📦 <b>Mis Pedidos</b>\n\nAún no tienes pedidos. ¡Explora el catálogo!",
        "hi": "📦 <b>मेरे ऑर्डर</b>\n\nआपके अभी तक कोई ऑर्डर नहीं हैं। कैटलॉग देखें!",
        "id": "📦 <b>Pesanan Saya</b>\n\nAnda belum memiliki pesanan. Jelajahi katalog!",
        "ur": "📦 <b>میرے آرڈر</b>\n\nآپ کے ابھی تک کوئی آرڈر نہیں ہیں۔ کیٹلاگ دیکھیں!",
        "zh": "📦 <b>我的订单</b>\n\n您还没有任何订单。浏览目录吧！",
    },
    "my_orders_title": {
        "en": "📦 <b>My Orders</b>\n",
        "es": "📦 <b>Mis Pedidos</b>\n",
        "hi": "📦 <b>मेरे ऑर्डर</b>\n",
        "id": "📦 <b>Pesanan Saya</b>\n",
        "ur": "📦 <b>میرے آرڈر</b>\n",
        "zh": "📦 <b>我的订单</b>\n",
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
        "hi": (
            "⚡ <b>तरीके</b>\n\n"
            "कम कीमत पर प्रीमियम AI टूल्स तक पहुंचने के लिए सिद्ध तरीके खरीदें।\n\n"
            "एक तरीका चुनें:"
        ),
        "id": (
            "⚡ <b>Metode</b>\n\n"
            "Beli metode terbukti untuk mengakses alat AI premium dengan harga murah.\n\n"
            "Pilih metode:"
        ),
        "ur": (
            "⚡ <b>طریقے</b>\n\n"
            "کم قیمت پر پریمیم AI ٹولز تک رسائی کے لیے آزمودہ طریقے خریدیں۔\n\n"
            "ایک طریقہ منتخب کریں:"
        ),
        "zh": (
            "⚡ <b>方法</b>\n\n"
            "购买经过验证的方法，以极低的价格访问高级 AI 工具。\n\n"
            "选择一种方法："
        ),
    },
    "method_detail": {
        "en": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Price:</b> {price}\n🚀 <b>Delivery:</b> {delivery}",
        "es": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Precio:</b> {price}\n🚀 <b>Entrega:</b> {delivery}",
        "hi": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>मूल्य:</b> {price}\n🚀 <b>डिलीवरी:</b> {delivery}",
        "id": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>Harga:</b> {price}\n🚀 <b>Pengiriman:</b> {delivery}",
        "ur": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>قیمت:</b> {price}\n🚀 <b>ڈیلیوری:</b> {delivery}",
        "zh": "{emoji} <b>{name}</b>\n\n{description}\n\n💵 <b>价格：</b>{price}\n🚀 <b>交付：</b>{delivery}",
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
        "hi": (
            "🎁 <b>रेफरल प्रोग्राम</b>\n\n"
            "अपना लिंक शेयर करें और हर दोस्त की पहली खरीद पर <b>$1.00 क्रेडिट</b> कमाएं!\n\n"
            "🔗 <b>आपका रेफरल लिंक:</b>\n"
            "<code>{link}</code>\n\n"
            "👥 रेफर किए गए दोस्त: <b>{count}</b>\n"
            "💰 कमाए गए क्रेडिट: <b>${credits:.2f} USDT</b>\n\n"
            "💡 क्रेडिट अगले ऑर्डर पर स्वचालित रूप से लागू होते हैं।"
        ),
        "id": (
            "🎁 <b>Program Referral</b>\n\n"
            "Bagikan link Anda dan dapatkan <b>kredit $1,00</b> untuk setiap teman yang melakukan pembelian!\n\n"
            "🔗 <b>Link referral Anda:</b>\n"
            "<code>{link}</code>\n\n"
            "👥 Teman yang direferral: <b>{count}</b>\n"
            "💰 Kredit yang diperoleh: <b>${credits:.2f} USDT</b>\n\n"
            "💡 Kredit diterapkan secara otomatis pada pesanan Anda berikutnya."
        ),
        "ur": (
            "🎁 <b>ریفرل پروگرام</b>\n\n"
            "اپنا لنک شیئر کریں اور ہر دوست کی پہلی خریداری پر <b>$1.00 کریڈٹ</b> کمائیں!\n\n"
            "🔗 <b>آپ کا ریفرل لنک:</b>\n"
            "<code>{link}</code>\n\n"
            "👥 ریفر کیے گئے دوست: <b>{count}</b>\n"
            "💰 کمایا گیا کریڈٹ: <b>${credits:.2f} USDT</b>\n\n"
            "💡 کریڈٹ آپ کے اگلے آرڈر پر خودکار طریقے سے لاگو ہوتے ہیں۔"
        ),
        "zh": (
            "🎁 <b>推荐计划</b>\n\n"
            "分享您的链接，每位完成购买的朋友可获得 <b>$1.00 积分</b>！\n\n"
            "🔗 <b>您的推荐链接：</b>\n"
            "<code>{link}</code>\n\n"
            "👥 已推荐好友：<b>{count}</b>\n"
            "💰 已获得积分：<b>${credits:.2f} USDT</b>\n\n"
            "💡 积分将自动应用于您的下一笔订单。"
        ),
    },
    "referral_welcome_bonus": {
        "en": "🎉 You joined via a referral link! Your friend will earn $1.00 credit when you make your first purchase.",
        "es": "🎉 ¡Entraste a través de un link de referido! Tu amigo ganará $1.00 de crédito cuando hagas tu primera compra.",
        "hi": "🎉 आप एक रेफरल लिंक के माध्यम से जुड़े! जब आप अपनी पहली खरीद करेंगे तो आपके दोस्त को $1.00 क्रेडिट मिलेगा।",
        "id": "🎉 Anda bergabung melalui link referral! Teman Anda akan mendapatkan kredit $1,00 ketika Anda melakukan pembelian pertama.",
        "ur": "🎉 آپ ریفرل لنک کے ذریعے شامل ہوئے! جب آپ اپنی پہلی خریداری کریں گے تو آپ کے دوست کو $1.00 کریڈٹ ملے گا۔",
        "zh": "🎉 您通过推荐链接加入！当您完成首次购买时，您的朋友将获得 $1.00 积分。",
    },
    "referral_credited": {
        "en": "💰 <b>+$1.00 credit earned!</b>\nYour referral <b>{name}</b> just made their first purchase. Credit added to your account!",
        "es": "💰 <b>¡+$1.00 de crédito ganado!</b>\nTu referido <b>{name}</b> acaba de hacer su primera compra. ¡Crédito añadido a tu cuenta!",
        "hi": "💰 <b>+$1.00 क्रेडिट मिला!</b>\nआपके रेफरल <b>{name}</b> ने अभी अपनी पहली खरीद की। क्रेडिट आपके खाते में जोड़ा गया!",
        "id": "💰 <b>+$1,00 kredit diperoleh!</b>\nReferral Anda <b>{name}</b> baru saja melakukan pembelian pertama mereka. Kredit ditambahkan ke akun Anda!",
        "ur": "💰 <b>+$1.00 کریڈٹ ملا!</b>\nآپ کے ریفرل <b>{name}</b> نے ابھی اپنی پہلی خریداری کی۔ کریڈٹ آپ کے اکاؤنٹ میں شامل کر دیا گیا!",
        "zh": "💰 <b>获得 +$1.00 积分！</b>\n您的推荐人 <b>{name}</b> 刚刚完成了他们的第一次购买。积分已添加到您的账户！",
    },
    "btn_copy_link": {
        "en": "📋 Copy Link",
        "es": "📋 Copiar Link",
        "hi": "📋 लिंक कॉपी करें",
        "id": "📋 Salin Link",
        "ur": "📋 لنک کاپی کریں",
        "zh": "📋 复制链接",
    },
    "btn_share_link": {
        "en": "📤 Share",
        "es": "📤 Compartir",
        "hi": "📤 शेयर करें",
        "id": "📤 Bagikan",
        "ur": "📤 شیئر کریں",
        "zh": "📤 分享",
    },

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
        "hi": (
            "💬 <b>सपोर्ट</b>\n\n"
            "📩 हमसे संपर्क करें: {username}\n\n"
            "⏱️ औसत प्रतिक्रिया समय: <b>2 घंटे से कम</b>\n"
            "🕐 समय: सोमवार–रविवार, सुबह 9 बजे – रात 10 बजे"
        ),
        "id": (
            "💬 <b>Dukungan</b>\n\n"
            "📩 Hubungi kami: {username}\n\n"
            "⏱️ Waktu respons rata-rata: <b>kurang dari 2 jam</b>\n"
            "🕐 Jam: Senin–Minggu, 9 pagi – 10 malam"
        ),
        "ur": (
            "💬 <b>سپورٹ</b>\n\n"
            "📩 ہم سے رابطہ کریں: {username}\n\n"
            "⏱️ اوسط جواب کا وقت: <b>2 گھنٹے سے کم</b>\n"
            "🕐 اوقات: پیر سے اتوار، صبح 9 بجے – رات 10 بجے"
        ),
        "zh": (
            "💬 <b>客服</b>\n\n"
            "📩 联系我们：{username}\n\n"
            "⏱️ 平均响应时间：<b>2小时以内</b>\n"
            "🕐 工作时间：周一至周日，早9点 – 晚10点"
        ),
    },
    "cancelled": {
        "en": "❌ Operation cancelled.",
        "es": "❌ Operación cancelada.",
        "hi": "❌ ऑपरेशन रद्द किया गया।",
        "id": "❌ Operasi dibatalkan.",
        "ur": "❌ آپریشن منسوخ کر دیا گیا۔",
        "zh": "❌ 操作已取消。",
    },
}

# All supported language codes
SUPPORTED_LANGS = ("en", "es", "hi", "id", "ur", "zh")


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated string for a given key and language."""
    lang = lang if lang in SUPPORTED_LANGS else "en"
    entry = STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("en") or f"[{key}]"
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
