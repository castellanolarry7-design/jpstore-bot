import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [int(x) for x in os.getenv("ADMIN_ID", "0").split(",") if x.strip()]
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "JPStoreBot")  # set via @BotFather

# ── Wallets Crypto ────────────────────────────────────────
USDT_TRC20: str = os.getenv("USDT_TRC20_ADDRESS", "")
USDT_BEP20: str = os.getenv("USDT_BEP20_ADDRESS", "")

# ── Crypto monitoring APIs ────────────────────────────────
# TronGrid (TRC20): https://www.trongrid.io  → free account → get API key
TRONGRID_API_KEY: str  = os.getenv("TRONGRID_API_KEY", "")
# BSCScan (BEP20):  https://bscscan.com/apis → free account → get API key
BSCSCAN_API_KEY: str   = os.getenv("BSCSCAN_API_KEY", "")

# ── Binance Pay ───────────────────────────────────────────
BINANCE_PAY_ID: str     = os.getenv("BINANCE_PAY_ID", "800595536")  # Tu Binance ID
BINANCE_API_KEY: str    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
BINANCE_PAY_ENABLED: bool = True  # Siempre habilitado (pago manual por ID)

# ── Database ─────────────────────────────────────────────
# Set DATABASE_URL to a PostgreSQL URL (recommended for production).
# Example (Supabase / Railway Postgres):
#   postgresql://user:password@host:5432/dbname
# If not set, falls back to local SQLite store.db
DATABASE_URL:  str = os.getenv("DATABASE_URL", "")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "store.db")

# ── Top-Up amounts (USD) ─────────────────────────────────
TOPUP_AMOUNTS: list[float] = [5.0, 10.0, 20.0, 50.0]

# ── Admin stock password ──────────────────────────────────
# Set this in your .env / Railway variables as ADMIN_PASSWORD
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

# ── Referral reward ───────────────────────────────────────
REFERRAL_REWARD: float = 1.00   # USD credit per successful referral

# ── Store info ────────────────────────────────────────────
STORE_NAME        = "🛒 JPStore AI"
STORE_DESCRIPTION = "Your premium AI services & methods store"
SUPPORT_USERNAME  = "@xpsolidity"

# ─────────────────────────────────────────────────────────────────────────────
# SERVICES CATALOG
# Each entry: id, name, emoji, description (EN/ES), price OR variants, delivery
# ─────────────────────────────────────────────────────────────────────────────
SERVICES: dict = {
    # ── Gemini Pro ────────────────────────────────────────
    "gemini_pro_1m": {
        "id": "gemini_pro_1m", "group": "gemini_pro",
        "name": "Gemini Pro – 1 Month",
        "emoji": "🔷",
        "description": {
            "en": "• Gemini Pro access (Google)\n• Text, code & image generation\n• 1-month access\n• 24/7 support",
            "es": "• Acceso Gemini Pro (Google)\n• Texto, código e imágenes\n• 1 mes de acceso\n• Soporte 24/7",
        },
        "price": 4.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },
    "gemini_pro_1y": {
        "id": "gemini_pro_1y", "group": "gemini_pro",
        "name": "Gemini Pro – 1 Year",
        "emoji": "🔷",
        "description": {
            "en": "• Gemini Pro access for 12 months\n• Text, code & image generation\n• Best value – save 72%\n• 24/7 support",
            "es": "• Acceso Gemini Pro por 12 meses\n• Texto, código e imágenes\n• Mejor precio – ahorra 72%\n• Soporte 24/7",
        },
        "price": 15.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },

    # ── Gemini Ultra ──────────────────────────────────────
    "gemini_ultra_1m": {
        "id": "gemini_ultra_1m", "group": "gemini_ultra",
        "name": "Gemini Ultra – 1 Month",
        "emoji": "🔮",
        "description": {
            "en": "• Full Gemini Ultra access (Google)\n• Text, code & image generation\n• ✅ 30-day guarantee\n• 24/7 support",
            "es": "• Acceso completo Gemini Ultra (Google)\n• Texto, código e imágenes\n• ✅ Garantía 30 días\n• Soporte 24/7",
        },
        "price": 8.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },
    "gemini_ultra_3m": {
        "id": "gemini_ultra_3m", "group": "gemini_ultra",
        "name": "Gemini Ultra – 3 Months",
        "emoji": "🔮",
        "description": {
            "en": "• Full Gemini Ultra access for 3 months\n• Text, code & image generation\n• ✅ 30-day guarantee\n• Save 29% vs monthly",
            "es": "• Acceso Gemini Ultra por 3 meses\n• Texto, código e imágenes\n• ✅ Garantía 30 días\n• Ahorra 29% vs mensual",
        },
        "price": 17.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },

    # ── Grok ──────────────────────────────────────────────
    "grok_1m": {
        "id": "grok_1m", "group": "grok",
        "name": "Grok – 1 Month",
        "emoji": "🤖",
        "description": {
            "en": "• Grok by xAI (X Premium+)\n• Real-time data + advanced chat\n• 1-month guaranteed access",
            "es": "• Grok de xAI (X Premium+)\n• Datos en tiempo real + chat avanzado\n• 1 mes de acceso garantizado",
        },
        "price": 9.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },

    # ── ChatGPT Plus ──────────────────────────────────────
    "chatgpt_1m": {
        "id": "chatgpt_1m", "group": "chatgpt",
        "name": "ChatGPT Plus – 1 Month",
        "emoji": "💬",
        "description": {
            "en": "• GPT-4o, DALL·E 3 & web browsing\n• Custom GPTs access\n• 1-month guaranteed access",
            "es": "• GPT-4o, DALL·E 3 y navegación web\n• GPTs personalizados\n• 1 mes de acceso garantizado",
        },
        "price": 8.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },

    # ── CapCut ────────────────────────────────────────────
    "capcut_1y": {
        "id": "capcut_1y", "group": "capcut",
        "name": "CapCut Pro – 1 Year",
        "emoji": "🎬",
        "description": {
            "en": "• CapCut Pro annual plan\n• All premium templates & AI tools\n• 12 months access",
            "es": "• Plan anual CapCut Pro\n• Todas las plantillas premium y herramientas IA\n• 12 meses de acceso",
        },
        "price": 10.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },
     # ── CapCut ────────────────────────────────────────────
    "capcut_1m": {
        "id": "capcut_1m", "group": "capcutt",
        "name": "CapCut Pro – 1 Month",
        "emoji": "🎬",
        "description": {
            "en": "• CapCut Pro Month plan\n• All premium templates & AI tools\n• 1 month access",
            "es": "• Plan Mensual CapCut Pro\n• Todas las plantillas premium y herramientas IA\n•  1 mes de acceso",
        },
        "price": 1.50,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },


    # ── Adobe ─────────────────────────────────────────────
    "adobe_4m": {
        "id": "adobe_4m", "group": "adobe",
        "name": "Adobe CC – 4 Months",
        "emoji": "🎨",
        "description": {
            "en": "• Adobe Creative Cloud (4 months)\n• Photoshop, Illustrator, Premiere & more\n• Full suite access",
            "es": "• Adobe Creative Cloud (4 meses)\n• Photoshop, Illustrator, Premiere y más\n• Acceso completo a la suite",
        },
        "price": 15.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },

    # ── HeyGen ────────────────────────────────────────────
    "heygen_1m": {
        "id": "heygen_1m", "group": "heygen",
        "name": "HeyGen – 1 Month",
        "emoji": "🧑‍💻",
        "description": {
            "en": "• HeyGen AI video creator\n• Premium avatars & voices\n• Creator plan – 1 month",
            "es": "• HeyGen creador de video IA\n• Avatares y voces premium\n• Plan creador – 1 mes",
        },
        "price": 10.00,
        "delivery": {"en": "Within 24h", "es": "En menos de 24h"},
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# METHODS CATALOG
# "Methods" = step-by-step methods to get AI access yourself, or bulk accounts
# ─────────────────────────────────────────────────────────────────────────────
METHODS: dict = {
    "method_grok_1m": {
        "id": "method_grok_1m",
        "name": "Grok Method – 1 Month",
        "emoji": "⚡",
        "description": {
            "en": (
                "• Proven method to get Grok access for 1 month\n"
                "• Step-by-step guide included\n"
                "• Works with any account\n"
                "• Instant digital delivery"
            ),
            "es": (
                "• Método probado para obtener Grok por 1 mes\n"
                "• Guía paso a paso incluida\n"
                "• Funciona con cualquier cuenta\n"
                "• Entrega digital inmediata"
            ),
        },
        "price": 8.00,
        "delivery": {"en": "Instant", "es": "Inmediata"},
    },
    "method_grok_unlimited": {
        "id": "method_grok_unlimited",
        "name": "Grok Unlimited Monthly Accounts",
        "emoji": "♾️",
        "description": {
            "en": (
                "• Unlimited Grok accounts for the current month\n"
                "• Bulk access – create as many as you need\n"
                "• Full method + automation guide\n"
                "• Valid until end of month"
            ),
            "es": (
                "• Cuentas Grok ilimitadas durante el mes actual\n"
                "• Acceso masivo – crea cuantas necesites\n"
                "• Método completo + guía de automatización\n"
                "• Válido hasta fin de mes"
            ),
        },
        "price": 70.00,
        "delivery": {"en": "Instant", "es": "Inmediata"},
    },
}
