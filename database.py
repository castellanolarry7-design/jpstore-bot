"""
database.py – Dual-backend database layer
  • PostgreSQL (asyncpg) when DATABASE_URL is set  ← production / Railway / Supabase
  • SQLite (aiosqlite) as fallback for local dev

All public functions are identical regardless of backend.
"""
import os, hashlib
from config import DATABASE_URL, DATABASE_PATH

# ── Backend detection ─────────────────────────────────────────────────────────
_USE_PG = bool(DATABASE_URL)

if _USE_PG:
    import asyncpg
    _pool: "asyncpg.Pool | None" = None

    async def _get_pool() -> "asyncpg.Pool":
        global _pool
        if _pool is None:
            url = DATABASE_URL
            # Supabase/some providers give postgres://, asyncpg needs postgresql://
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            _pool = await asyncpg.create_pool(url, min_size=1, max_size=5,
                                               statement_cache_size=0)
        return _pool

    async def _exec(query: str, *args):
        async with (await _get_pool()).acquire() as c:
            await c.execute(query, *args)

    async def _fetch(query: str, *args) -> list[dict]:
        async with (await _get_pool()).acquire() as c:
            rows = await c.fetch(query, *args)
            return [dict(r) for r in rows]

    async def _fetchrow(query: str, *args) -> dict | None:
        async with (await _get_pool()).acquire() as c:
            row = await c.fetchrow(query, *args)
            return dict(row) if row else None

    async def _fetchval(query: str, *args):
        async with (await _get_pool()).acquire() as c:
            return await c.fetchval(query, *args)

else:
    import aiosqlite

    def _q(sql: str) -> str:
        """Convert $1,$2,… placeholders to ? for SQLite."""
        import re
        return re.sub(r'\$\d+', '?', sql)

    async def _exec(query: str, *args):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(_q(query), args)
            await db.commit()

    async def _fetch(query: str, *args) -> list[dict]:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(_q(query), args) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def _fetchrow(query: str, *args) -> dict | None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(_q(query), args) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def _fetchval(query: str, *args):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(_q(query), args) as cur:
                row = await cur.fetchone()
                return row[0] if row else None


# ═════════════════════════════════════════════════════════════════════════════
# SCHEMA CREATION & MIGRATION
# ═════════════════════════════════════════════════════════════════════════════

async def _create_tables_pg(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id              SERIAL PRIMARY KEY,
            service_id      TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            emoji           TEXT DEFAULT '📦',
            price           REAL NOT NULL,
            description_en  TEXT DEFAULT '',
            description_es  TEXT DEFAULT '',
            delivery_en     TEXT DEFAULT 'Instant delivery',
            delivery_es     TEXT DEFAULT 'Entrega inmediata',
            photo_file_id   TEXT DEFAULT NULL,
            is_active       INTEGER DEFAULT 1,
            added_at        TIMESTAMP DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS service_photos (
            service_id  TEXT PRIMARY KEY,
            file_id     TEXT NOT NULL,
            updated_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id         BIGINT PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            lang            TEXT    DEFAULT 'en',
            credits         REAL    DEFAULT 0.0,
            referral_code   TEXT,
            referred_by     BIGINT,
            first_purchase  INTEGER DEFAULT 0,
            joined_at       TIMESTAMP DEFAULT NOW(),
            is_banned       INTEGER DEFAULT 0
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id              SERIAL PRIMARY KEY,
            user_id               BIGINT NOT NULL,
            service_id            TEXT   NOT NULL,
            item_type             TEXT   DEFAULT 'service',
            amount                REAL   NOT NULL,
            expected_amount       REAL,
            credits_used          REAL   DEFAULT 0.0,
            payment_method        TEXT   NOT NULL,
            payment_proof         TEXT,
            payer_binance_id      TEXT,
            status                TEXT   DEFAULT 'pending',
            created_at            TIMESTAMP DEFAULT NOW(),
            updated_at            TIMESTAMP DEFAULT NOW(),
            delivery_info         TEXT,
            admin_note            TEXT,
            instruction_msg_id    BIGINT,
            instruction_chat_id   BIGINT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id          SERIAL PRIMARY KEY,
            referrer_id BIGINT NOT NULL,
            referred_id BIGINT NOT NULL,
            credited    INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT NOW(),
            UNIQUE(referrer_id, referred_id)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id           SERIAL PRIMARY KEY,
            service_id   TEXT    NOT NULL,
            content      TEXT    NOT NULL,
            label        TEXT,
            delivered    INTEGER DEFAULT 0,
            order_id     INTEGER,
            delivered_at TIMESTAMP,
            added_at     TIMESTAMP DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS db_methods (
            id              SERIAL PRIMARY KEY,
            method_id       TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            emoji           TEXT DEFAULT '⚡',
            price           REAL NOT NULL,
            description_en  TEXT DEFAULT '',
            description_es  TEXT DEFAULT '',
            delivery_en     TEXT DEFAULT 'Instant',
            delivery_es     TEXT DEFAULT 'Inmediata',
            is_active       INTEGER DEFAULT 1,
            added_at        TIMESTAMP DEFAULT NOW()
        )
    """)
    # Safe ALTER TABLE ADD COLUMN IF NOT EXISTS (PG 9.6+)
    for tbl, col, typedef in [
        ("users",    "credits",              "REAL DEFAULT 0.0"),
        ("users",    "referral_code",        "TEXT"),
        ("users",    "referred_by",          "BIGINT"),
        ("users",    "first_purchase",       "INTEGER DEFAULT 0"),
        ("users",    "is_banned",            "INTEGER DEFAULT 0"),
        ("orders",   "item_type",            "TEXT DEFAULT 'service'"),
        ("orders",   "credits_used",         "REAL DEFAULT 0.0"),
        ("orders",   "expected_amount",      "REAL"),
        ("orders",   "payer_binance_id",     "TEXT"),
        ("orders",   "instruction_msg_id",   "BIGINT"),
        ("orders",   "instruction_chat_id",  "BIGINT"),
        ("stock",    "label",                "TEXT"),
        ("products", "photo_file_id",        "TEXT DEFAULT NULL"),
    ]:
        try:
            await conn.execute(
                f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {typedef}"
            )
        except Exception:
            pass


async def _create_tables_sqlite(db) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id      TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            emoji           TEXT DEFAULT '📦',
            price           REAL NOT NULL,
            description_en  TEXT DEFAULT '',
            description_es  TEXT DEFAULT '',
            delivery_en     TEXT DEFAULT 'Instant delivery',
            delivery_es     TEXT DEFAULT 'Entrega inmediata',
            photo_file_id   TEXT DEFAULT NULL,
            is_active       INTEGER DEFAULT 1,
            added_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS service_photos (
            service_id  TEXT PRIMARY KEY,
            file_id     TEXT NOT NULL,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            lang            TEXT    DEFAULT 'en',
            credits         REAL    DEFAULT 0.0,
            referral_code   TEXT,
            referred_by     INTEGER,
            first_purchase  INTEGER DEFAULT 0,
            joined_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned       INTEGER DEFAULT 0
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id               INTEGER NOT NULL,
            service_id            TEXT    NOT NULL,
            item_type             TEXT    DEFAULT 'service',
            amount                REAL    NOT NULL,
            expected_amount       REAL,
            credits_used          REAL    DEFAULT 0.0,
            payment_method        TEXT    NOT NULL,
            payment_proof         TEXT,
            payer_binance_id      TEXT,
            status                TEXT    DEFAULT 'pending',
            created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivery_info         TEXT,
            admin_note            TEXT,
            instruction_msg_id    INTEGER,
            instruction_chat_id   INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            credited    INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referrer_id, referred_id)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id   TEXT    NOT NULL,
            content      TEXT    NOT NULL,
            label        TEXT,
            delivered    INTEGER DEFAULT 0,
            order_id     INTEGER,
            delivered_at TIMESTAMP,
            added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS db_methods (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id       TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            emoji           TEXT DEFAULT '⚡',
            price           REAL NOT NULL,
            description_en  TEXT DEFAULT '',
            description_es  TEXT DEFAULT '',
            delivery_en     TEXT DEFAULT 'Instant',
            delivery_es     TEXT DEFAULT 'Inmediata',
            is_active       INTEGER DEFAULT 1,
            added_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.commit()
    # Safe migrations for existing SQLite DBs
    for tbl, existing_cols_query, col_defs in [
        ("users",  "PRAGMA table_info(users)",  {
            "lang": "ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'en'",
            "credits": "ALTER TABLE users ADD COLUMN credits REAL DEFAULT 0.0",
            "referral_code": "ALTER TABLE users ADD COLUMN referral_code TEXT",
            "referred_by": "ALTER TABLE users ADD COLUMN referred_by INTEGER",
            "first_purchase": "ALTER TABLE users ADD COLUMN first_purchase INTEGER DEFAULT 0",
            "is_banned": "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
        }),
        ("orders", "PRAGMA table_info(orders)", {
            "item_type": "ALTER TABLE orders ADD COLUMN item_type TEXT DEFAULT 'service'",
            "credits_used": "ALTER TABLE orders ADD COLUMN credits_used REAL DEFAULT 0.0",
            "expected_amount": "ALTER TABLE orders ADD COLUMN expected_amount REAL",
            "payer_binance_id": "ALTER TABLE orders ADD COLUMN payer_binance_id TEXT",
            "instruction_msg_id": "ALTER TABLE orders ADD COLUMN instruction_msg_id INTEGER",
            "instruction_chat_id": "ALTER TABLE orders ADD COLUMN instruction_chat_id INTEGER",
        }),
        ("stock", "PRAGMA table_info(stock)", {
            "label": "ALTER TABLE stock ADD COLUMN label TEXT",
        }),
        ("products", "PRAGMA table_info(products)", {
            "photo_file_id": "ALTER TABLE products ADD COLUMN photo_file_id TEXT DEFAULT NULL",
        }),
    ]:
        async with db.execute(existing_cols_query) as cur:
            cols = {row[1] for row in await cur.fetchall()}
        for col, sql in col_defs.items():
            if col not in cols:
                await db.execute(sql)
    await db.commit()


async def init_db() -> None:
    if _USE_PG:
        async with (await _get_pool()).acquire() as conn:
            await _create_tables_pg(conn)
    else:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await _create_tables_sqlite(db)
    # Warm up the in-memory caches
    await refresh_products_cache()
    await refresh_methods_cache()


# ═════════════════════════════════════════════════════════════════════════════
# DYNAMIC PRODUCTS CACHE (DB-backed, merged with static SERVICES at runtime)
# ═════════════════════════════════════════════════════════════════════════════

_products_cache: dict = {}   # service_id → SERVICES-format dict


async def refresh_products_cache() -> None:
    """Load active products from DB into the in-memory cache."""
    global _products_cache
    rows = await _fetch("SELECT * FROM products WHERE is_active = 1 ORDER BY added_at ASC")
    _products_cache = {}
    for r in rows:
        _products_cache[r["service_id"]] = {
            "id":          r["service_id"],
            "name":        r["name"],
            "emoji":       r["emoji"],
            "price":       float(r["price"]),
            "description": {
                "en": r.get("description_en") or "",
                "es": r.get("description_es") or "",
            },
            "delivery": {
                "en": r.get("delivery_en") or "Instant delivery",
                "es": r.get("delivery_es") or "Entrega inmediata",
            },
            "photo_file_id": r.get("photo_file_id") or None,
            "_db_id": r["id"],   # kept for deletion
        }


def get_cached_db_products() -> dict:
    """Sync read of the in-memory products cache (always fresh after any create/delete)."""
    return dict(_products_cache)


async def create_db_product(
    name: str, emoji: str, price: float,
    desc_en: str, desc_es: str,
    delivery_en: str, delivery_es: str,
    photo_file_id: str | None = None,
) -> int:
    """Create a new dynamic product and refresh the cache. Returns the new DB row id."""
    import re
    base_sid = re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_")[:25] or "product"
    service_id = base_sid
    # Avoid collision with existing service_ids (static OR DB)
    from config import SERVICES, METHODS
    taken = set(SERVICES) | set(METHODS) | set(_products_cache)
    suffix = 2
    while service_id in taken:
        service_id = f"{base_sid}_{suffix}"[:30]
        suffix += 1
    new_id = await _insert_returning("""
        INSERT INTO products (service_id, name, emoji, price, description_en, description_es,
                              delivery_en, delivery_es, photo_file_id)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id
    """, service_id, name, emoji, price, desc_en, desc_es, delivery_en, delivery_es, photo_file_id)
    await refresh_products_cache()
    return new_id


async def set_service_photo(service_id: str, file_id: str) -> None:
    """
    Store a photo for any product (static or dynamic).
    For dynamic products: updates the products table.
    For static products: upserts into service_photos table.
    """
    from config import SERVICES
    if service_id in _products_cache:
        # Dynamic product — update products table
        await _exec(
            "UPDATE products SET photo_file_id=$1 WHERE service_id=$2",
            file_id, service_id
        )
        await refresh_products_cache()
    else:
        # Static product (or methods) — use service_photos table
        if _USE_PG:
            await _exec("""
                INSERT INTO service_photos (service_id, file_id)
                VALUES ($1, $2)
                ON CONFLICT (service_id) DO UPDATE SET file_id=$2, updated_at=NOW()
            """, service_id, file_id)
        else:
            await _exec("""
                INSERT OR REPLACE INTO service_photos (service_id, file_id)
                VALUES ($1, $2)
            """, service_id, file_id)


async def get_service_photo(service_id: str) -> str | None:
    """
    Get the photo file_id for a product.
    Dynamic products: from in-memory cache (includes photo_file_id).
    Static products: from service_photos table.
    """
    # Check dynamic products cache first
    if service_id in _products_cache:
        return _products_cache[service_id].get("photo_file_id")
    # Check service_photos table for static products
    row = await _fetchrow(
        "SELECT file_id FROM service_photos WHERE service_id=$1", service_id
    )
    return row["file_id"] if row else None


async def delete_service_photo(service_id: str) -> None:
    """Remove the photo from a product."""
    if service_id in _products_cache:
        await _exec(
            "UPDATE products SET photo_file_id=NULL WHERE service_id=$1", service_id
        )
        await refresh_products_cache()
    else:
        await _exec("DELETE FROM service_photos WHERE service_id=$1", service_id)


async def delete_db_product(db_id: int) -> bool:
    """Soft-delete a dynamic product by DB row id. Returns True if deleted."""
    row = await _fetchrow("SELECT id FROM products WHERE id=$1 AND is_active=1", db_id)
    if not row:
        return False
    await _exec("UPDATE products SET is_active=0 WHERE id=$1", db_id)
    await refresh_products_cache()
    return True


async def get_all_db_products() -> list[dict]:
    """Return raw product rows (all active) for admin listing."""
    return await _fetch("SELECT * FROM products WHERE is_active=1 ORDER BY added_at ASC")


# ═════════════════════════════════════════════════════════════════════════════
# DYNAMIC METHODS CACHE (DB-backed, merged with static METHODS at runtime)
# ═════════════════════════════════════════════════════════════════════════════

_methods_cache: dict = {}


async def refresh_methods_cache() -> None:
    """Load active DB methods into the in-memory cache."""
    global _methods_cache
    rows = await _fetch("SELECT * FROM db_methods WHERE is_active = 1 ORDER BY added_at ASC")
    _methods_cache = {}
    for r in rows:
        _methods_cache[r["method_id"]] = {
            "id":          r["method_id"],
            "name":        r["name"],
            "emoji":       r["emoji"],
            "price":       float(r["price"]),
            "description": {
                "en": r.get("description_en") or "",
                "es": r.get("description_es") or "",
            },
            "delivery": {
                "en": r.get("delivery_en") or "Instant",
                "es": r.get("delivery_es") or "Inmediata",
            },
            "_db_id": r["id"],
        }


def get_cached_db_methods() -> dict:
    """Sync read of the in-memory methods cache."""
    return dict(_methods_cache)


async def create_db_method(
    name: str, emoji: str, price: float,
    desc_en: str, desc_es: str,
    delivery_en: str, delivery_es: str,
) -> int:
    """Create a new dynamic method and refresh the cache. Returns the new DB row id."""
    import re
    base_mid = re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_")[:25] or "method"
    method_id = base_mid
    from config import METHODS
    taken = set(METHODS) | set(_methods_cache)
    suffix = 2
    while method_id in taken:
        method_id = f"{base_mid}_{suffix}"[:30]
        suffix += 1
    new_id = await _insert_returning("""
        INSERT INTO db_methods (method_id, name, emoji, price, description_en, description_es,
                                delivery_en, delivery_es)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id
    """, method_id, name, emoji, price, desc_en, desc_es, delivery_en, delivery_es)
    await refresh_methods_cache()
    return new_id


async def update_db_method_price(method_id: str, new_price: float) -> None:
    """Update a DB method's price."""
    await _exec("UPDATE db_methods SET price=$1 WHERE method_id=$2", new_price, method_id)
    await refresh_methods_cache()


async def delete_db_method(db_id: int) -> bool:
    """Soft-delete a dynamic method by DB row id. Returns True if deleted."""
    row = await _fetchrow("SELECT id FROM db_methods WHERE id=$1 AND is_active=1", db_id)
    if not row:
        return False
    await _exec("UPDATE db_methods SET is_active=0 WHERE id=$1", db_id)
    await refresh_methods_cache()
    return True


async def get_all_db_methods() -> list[dict]:
    """Return raw method rows (all active) for admin listing."""
    return await _fetch("SELECT * FROM db_methods WHERE is_active=1 ORDER BY added_at ASC")


# ═════════════════════════════════════════════════════════════════════════════
# INSERT HELPER (handles RETURNING for PG vs lastrowid for SQLite)
# ═════════════════════════════════════════════════════════════════════════════

async def _insert_returning(query: str, *args) -> int:
    """Execute an INSERT and return the generated ID."""
    if _USE_PG:
        # query must end with RETURNING <id_col>
        async with (await _get_pool()).acquire() as c:
            return await c.fetchval(query, *args)
    else:
        import re
        # Strip RETURNING clause for SQLite, use lastrowid
        sql = re.sub(r'\s+RETURNING\s+\w+\s*$', '', query, flags=re.IGNORECASE)
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cur = await db.execute(re.sub(r'\$\d+', '?', sql), args)
            await db.commit()
            return cur.lastrowid


# ═════════════════════════════════════════════════════════════════════════════
# USERS
# ═════════════════════════════════════════════════════════════════════════════

async def upsert_user(user_id: int, username: str | None, first_name: str,
                      referred_by: int | None = None) -> None:
    code = hashlib.md5(str(user_id).encode()).hexdigest()[:8].upper()
    if _USE_PG:
        await _exec("""
            INSERT INTO users (user_id, username, first_name, referral_code, referred_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE SET
                username   = EXCLUDED.username,
                first_name = EXCLUDED.first_name
        """, user_id, username, first_name, code, referred_by)
    else:
        await _exec("""
            INSERT INTO users (user_id, username, first_name, referral_code, referred_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name
        """, user_id, username, first_name, code, referred_by)


async def get_user(user_id: int) -> dict | None:
    return await _fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)


async def get_user_lang(user_id: int) -> str:
    user = await get_user(user_id)
    return user["lang"] if user else "en"


async def set_user_lang(user_id: int, lang: str) -> None:
    await _exec("UPDATE users SET lang = $1 WHERE user_id = $2", lang, user_id)


async def get_all_users() -> list[dict]:
    return await _fetch("SELECT * FROM users ORDER BY joined_at DESC")


async def add_credits(user_id: int, amount: float) -> None:
    await _exec("UPDATE users SET credits = credits + $1 WHERE user_id = $2", amount, user_id)


async def use_credits(user_id: int, amount: float) -> None:
    await _exec(
        "UPDATE users SET credits = GREATEST(0, credits - $1) WHERE user_id = $2"
        if _USE_PG else
        "UPDATE users SET credits = MAX(0, credits - $1) WHERE user_id = $2",
        amount, user_id)


async def mark_first_purchase(user_id: int) -> int | None:
    row = await _fetchrow(
        "SELECT first_purchase, referred_by FROM users WHERE user_id = $1", user_id)
    if not row or row["first_purchase"]:
        return None
    await _exec("UPDATE users SET first_purchase = 1 WHERE user_id = $1", user_id)
    return row["referred_by"]


# ═════════════════════════════════════════════════════════════════════════════
# ORDERS
# ═════════════════════════════════════════════════════════════════════════════

async def create_order(user_id: int, service_id: str, amount: float,
                       payment_method: str, item_type: str = "service",
                       credits_used: float = 0.0) -> int:
    return await _insert_returning("""
        INSERT INTO orders (user_id, service_id, item_type, amount, payment_method, credits_used)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING order_id
    """, user_id, service_id, item_type, amount, payment_method, credits_used)


async def save_instruction_message(order_id: int, chat_id: int, msg_id: int) -> None:
    """Store the payment instruction message so it can be deleted after confirmation."""
    await _exec("""
        UPDATE orders SET instruction_chat_id = $1, instruction_msg_id = $2
        WHERE order_id = $3
    """, chat_id, msg_id, order_id)


async def set_order_payer(order_id: int, payer_binance_id: str,
                          expected_amount: float) -> None:
    await _exec("""
        UPDATE orders
        SET payer_binance_id = $1, expected_amount = $2
        WHERE order_id = $3
    """, payer_binance_id, expected_amount, order_id)


async def update_order_proof(order_id: int, proof: str) -> None:
    await _exec("""
        UPDATE orders SET payment_proof = $1 WHERE order_id = $2
    """, proof, order_id)


async def update_order_status(order_id: int, status: str,
                               admin_note: str = None,
                               delivery_info: str = None) -> None:
    await _exec("""
        UPDATE orders
        SET status        = $1,
            admin_note    = COALESCE($2, admin_note),
            delivery_info = COALESCE($3, delivery_info)
        WHERE order_id = $4
    """, status, admin_note, delivery_info, order_id)


async def get_order(order_id: int) -> dict | None:
    return await _fetchrow("SELECT * FROM orders WHERE order_id = $1", order_id)


async def get_user_orders(user_id: int) -> list[dict]:
    return await _fetch(
        "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC", user_id)


async def get_pending_orders() -> list[dict]:
    """Return orders that need admin attention: pending payment OR paid but not yet delivered."""
    return await _fetch("""
        SELECT o.*, u.username, u.first_name
        FROM orders o JOIN users u ON o.user_id = u.user_id
        WHERE o.status IN ('pending', 'paid') AND o.item_type != 'topup'
        ORDER BY o.created_at ASC
    """)


async def get_stats() -> dict:
    stats = {}
    for key, q in [
        ("total_users",      "SELECT COUNT(*) FROM users"),
        ("total_orders",     "SELECT COUNT(*) FROM orders WHERE item_type != 'topup'"),
        ("pending_orders",   "SELECT COUNT(*) FROM orders WHERE status IN ('pending','paid') AND item_type!='topup'"),
        ("delivered_orders", "SELECT COUNT(*) FROM orders WHERE status='delivered' AND item_type!='topup'"),
        ("total_referrals",  "SELECT COUNT(*) FROM referrals"),
    ]:
        stats[key] = await _fetchval(q) or 0
    stats["total_revenue"] = await _fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' AND item_type!='topup'"
    ) or 0.0
    # Revenue for last 7 days
    if _USE_PG:
        stats["week_revenue"] = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND created_at >= NOW() - INTERVAL '7 days'"
        ) or 0.0
        stats["today_revenue"] = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND created_at >= NOW() - INTERVAL '1 day'"
        ) or 0.0
    else:
        stats["week_revenue"] = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND created_at >= datetime('now','-7 days')"
        ) or 0.0
        stats["today_revenue"] = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND created_at >= datetime('now','-1 day')"
        ) or 0.0
    return stats


async def cancel_stale_pending_orders(older_than_minutes: int = 30) -> int:
    """
    Cancel pending orders older than `older_than_minutes` that have no monitor watching them
    (e.g., user opened Binance Pay step 1 then disappeared). Returns count cancelled.
    """
    if _USE_PG:
        rows = await _fetch("""
            UPDATE orders SET status='cancelled', admin_note='Auto-cancelled: stale pending'
            WHERE status='pending'
              AND item_type != 'topup'
              AND created_at < NOW() - ($1 * INTERVAL '1 minute')
            RETURNING order_id
        """, older_than_minutes)
    else:
        rows = await _fetch("""
            SELECT order_id FROM orders
            WHERE status='pending'
              AND item_type != 'topup'
              AND datetime(created_at) < datetime('now', $1)
        """, f"-{older_than_minutes} minutes")
        for r in rows:
            await _exec(
                "UPDATE orders SET status='cancelled', admin_note='Auto-cancelled: stale pending' "
                "WHERE order_id=$1", r["order_id"])
    return len(rows)


# ═════════════════════════════════════════════════════════════════════════════
# REFERRALS
# ═════════════════════════════════════════════════════════════════════════════

async def get_user_by_referral_code(code: str) -> dict | None:
    return await _fetchrow("SELECT * FROM users WHERE referral_code = $1", code)


async def record_referral(referrer_id: int, referred_id: int) -> None:
    if _USE_PG:
        await _exec("""
            INSERT INTO referrals (referrer_id, referred_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, referrer_id, referred_id)
    else:
        await _exec("""
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES ($1, $2)
        """, referrer_id, referred_id)


async def credit_referral(referrer_id: int, referred_id: int) -> bool:
    row = await _fetchrow(
        "SELECT credited FROM referrals WHERE referrer_id=$1 AND referred_id=$2",
        referrer_id, referred_id)
    if not row or row["credited"]:
        return False
    await _exec("UPDATE referrals SET credited=1 WHERE referrer_id=$1 AND referred_id=$2",
                referrer_id, referred_id)
    await _exec("UPDATE users SET credits = credits + 1.0 WHERE user_id=$1", referrer_id)
    return True


async def get_referral_count(user_id: int) -> int:
    return (await _fetchval(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id=$1", user_id)) or 0


async def get_referrer_id(buyer_id: int) -> int | None:
    """Return the user_id who referred this buyer (from users.referred_by)."""
    row = await _fetchrow("SELECT referred_by FROM users WHERE user_id=$1", buyer_id)
    return row["referred_by"] if row and row["referred_by"] else None


async def add_referral_credit(referrer_id: int, buyer_id: int) -> None:
    """
    Credit REFERRAL_REWARD to the referrer for a purchase by the referred user.
    Applies on every purchase (not just the first).
    Also ensures the referral row is marked credited=1 for stats.
    """
    from config import REFERRAL_REWARD
    await add_credits(referrer_id, REFERRAL_REWARD)
    # Mark the referral row as credited (idempotent for stats — just sets the flag)
    await _exec(
        "UPDATE referrals SET credited=1 WHERE referrer_id=$1 AND referred_id=$2",
        referrer_id, buyer_id
    )


# ═════════════════════════════════════════════════════════════════════════════
# STOCK
# ═════════════════════════════════════════════════════════════════════════════

async def add_stock_items(service_id: str, items: list[str],
                          label: str = None) -> int:
    count = 0
    for content in items:
        content = content.strip()
        if content:
            await _exec(
                "INSERT INTO stock (service_id, content, label) VALUES ($1, $2, $3)",
                service_id, content, label)
            count += 1
    return count


async def take_stock_items_multi(service_id: str, order_id: int,
                                  qty: int) -> list[dict]:
    """Atomically grab up to qty undelivered items."""
    if _USE_PG:
        async with (await _get_pool()).acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch("""
                    SELECT id, content, label FROM stock
                    WHERE service_id=$1 AND delivered=0
                    ORDER BY added_at ASC LIMIT $2
                    FOR UPDATE SKIP LOCKED
                """, service_id, qty)
                items = [dict(r) for r in rows]
                if items:
                    ids = [it["id"] for it in items]
                    await conn.execute("""
                        UPDATE stock SET delivered=1, order_id=$1,
                            delivered_at=NOW()
                        WHERE id = ANY($2::int[])
                    """, order_id, ids)
                return items
    else:
        import aiosqlite as _aio
        async with _aio.connect(DATABASE_PATH) as db:
            db.row_factory = _aio.Row
            async with db.execute("""
                SELECT id, content, label FROM stock
                WHERE service_id=? AND delivered=0
                ORDER BY added_at ASC LIMIT ?
            """, (service_id, qty)) as cur:
                rows = await cur.fetchall()
            items = [dict(r) for r in rows]
            for it in items:
                await db.execute("""
                    UPDATE stock SET delivered=1, order_id=?,
                        delivered_at=CURRENT_TIMESTAMP
                    WHERE id=? AND delivered=0
                """, (order_id, it["id"]))
            await db.commit()
            return items


async def get_stock_level(service_id: str) -> int:
    return (await _fetchval(
        "SELECT COUNT(*) FROM stock WHERE service_id=$1 AND delivered=0",
        service_id)) or 0


async def get_stock_levels_dict() -> dict:
    rows = await _fetch("""
        SELECT service_id, COUNT(*) AS cnt
        FROM stock WHERE delivered=0 GROUP BY service_id
    """)
    return {r["service_id"]: r["cnt"] for r in rows}


async def get_stock_items(service_id: str, limit: int = 50) -> list[dict]:
    return await _fetch("""
        SELECT id, content, label, added_at FROM stock
        WHERE service_id=$1 AND delivered=0
        ORDER BY added_at ASC LIMIT $2
    """, service_id, limit)


async def get_stock_delivered(service_id: str, limit: int = 10) -> list[dict]:
    return await _fetch("""
        SELECT id, content, order_id, delivered_at FROM stock
        WHERE service_id=$1 AND delivered=1
        ORDER BY delivered_at DESC LIMIT $2
    """, service_id, limit)


async def delete_stock_item(item_id: int) -> bool:
    row = await _fetchrow(
        "SELECT id FROM stock WHERE id=$1 AND delivered=0", item_id)
    if not row:
        return False
    await _exec("DELETE FROM stock WHERE id=$1", item_id)
    return True


async def get_all_stock_summary() -> list[dict]:
    return await _fetch("""
        SELECT service_id,
               SUM(CASE WHEN delivered=0 THEN 1 ELSE 0 END) AS available,
               SUM(CASE WHEN delivered=1 THEN 1 ELSE 0 END) AS delivered
        FROM stock GROUP BY service_id ORDER BY service_id
    """)


# ═════════════════════════════════════════════════════════════════════════════
# BOT CONFIG (key-value store for persistent bot settings)
# ═════════════════════════════════════════════════════════════════════════════

async def get_bot_config(key: str) -> str | None:
    """Read a persistent bot config value (e.g. welcome_photo_file_id)."""
    row = await _fetchrow("SELECT value FROM bot_config WHERE key=$1", key)
    return row["value"] if row else None


async def set_bot_config(key: str, value: str) -> None:
    """Write/update a persistent bot config value."""
    if _USE_PG:
        await _exec("""
            INSERT INTO bot_config (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = $2
        """, key, value)
    else:
        await _exec("""
            INSERT OR REPLACE INTO bot_config (key, value) VALUES ($1, $2)
        """, key, value)


# ═════════════════════════════════════════════════════════════════════════════
# FULL STATISTICS  (for /estadisticas command)
# ═════════════════════════════════════════════════════════════════════════════

async def get_full_stats() -> dict:
    """Comprehensive statistics for admin /estadisticas command."""
    s = {}

    # ── Users ─────────────────────────────────────────────────────────────────
    s["total_users"]  = await _fetchval("SELECT COUNT(*) FROM users") or 0
    s["banned_users"] = await _fetchval("SELECT COUNT(*) FROM users WHERE is_banned=1") or 0
    s["total_credits"] = await _fetchval("SELECT COALESCE(SUM(credits),0) FROM users") or 0.0

    if _USE_PG:
        s["new_today"] = await _fetchval(
            "SELECT COUNT(*) FROM users WHERE joined_at >= NOW() - INTERVAL '1 day'") or 0
        s["new_week"]  = await _fetchval(
            "SELECT COUNT(*) FROM users WHERE joined_at >= NOW() - INTERVAL '7 days'") or 0
        s["new_month"] = await _fetchval(
            "SELECT COUNT(*) FROM users WHERE joined_at >= NOW() - INTERVAL '30 days'") or 0
    else:
        s["new_today"] = await _fetchval(
            "SELECT COUNT(*) FROM users WHERE datetime(joined_at) >= datetime('now','-1 day')") or 0
        s["new_week"]  = await _fetchval(
            "SELECT COUNT(*) FROM users WHERE datetime(joined_at) >= datetime('now','-7 days')") or 0
        s["new_month"] = await _fetchval(
            "SELECT COUNT(*) FROM users WHERE datetime(joined_at) >= datetime('now','-30 days')") or 0

    lang_rows = await _fetch(
        "SELECT lang, COUNT(*) AS cnt FROM users GROUP BY lang ORDER BY cnt DESC")
    s["langs"] = [(r["lang"], r["cnt"]) for r in lang_rows]

    # ── Orders ────────────────────────────────────────────────────────────────
    s["total_orders"]     = await _fetchval(
        "SELECT COUNT(*) FROM orders WHERE item_type != 'topup'") or 0
    s["pending_orders"]   = await _fetchval(
        "SELECT COUNT(*) FROM orders WHERE status IN ('pending','paid') AND item_type!='topup'") or 0
    s["delivered_orders"] = await _fetchval(
        "SELECT COUNT(*) FROM orders WHERE status='delivered' AND item_type!='topup'") or 0
    s["cancelled_orders"] = await _fetchval(
        "SELECT COUNT(*) FROM orders WHERE status='cancelled' AND item_type!='topup'") or 0

    s["total_revenue"] = await _fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' AND item_type!='topup'") or 0.0

    if _USE_PG:
        s["today_revenue"] = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND created_at >= NOW() - INTERVAL '1 day'") or 0.0
        s["week_revenue"]  = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND created_at >= NOW() - INTERVAL '7 days'") or 0.0
        s["month_revenue"] = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND created_at >= NOW() - INTERVAL '30 days'") or 0.0
    else:
        s["today_revenue"] = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND datetime(created_at) >= datetime('now','-1 day')") or 0.0
        s["week_revenue"]  = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND datetime(created_at) >= datetime('now','-7 days')") or 0.0
        s["month_revenue"] = await _fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' "
            "AND item_type!='topup' AND datetime(created_at) >= datetime('now','-30 days')") or 0.0

    s["avg_order"] = (
        s["total_revenue"] / s["delivered_orders"]
        if s["delivered_orders"] > 0 else 0.0
    )

    # Payment method breakdown
    pm_rows = await _fetch(
        "SELECT payment_method, COUNT(*) AS cnt FROM orders "
        "WHERE status='delivered' AND item_type!='topup' "
        "GROUP BY payment_method ORDER BY cnt DESC")
    s["payment_methods"] = [(r["payment_method"], r["cnt"]) for r in pm_rows]

    # Top 5 best-selling products
    top_rows = await _fetch(
        "SELECT service_id, COUNT(*) AS cnt FROM orders "
        "WHERE status='delivered' AND item_type!='topup' "
        "GROUP BY service_id ORDER BY cnt DESC LIMIT 5")
    s["top_products"] = [(r["service_id"], r["cnt"]) for r in top_rows]

    # ── Top-ups ───────────────────────────────────────────────────────────────
    s["total_topups"]  = await _fetchval(
        "SELECT COUNT(*) FROM orders WHERE item_type='topup' AND status='delivered'") or 0
    s["topup_revenue"] = await _fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM orders "
        "WHERE item_type='topup' AND status='delivered'") or 0.0

    # ── Referrals ─────────────────────────────────────────────────────────────
    s["total_referrals"]    = await _fetchval("SELECT COUNT(*) FROM referrals") or 0
    s["credited_referrals"] = await _fetchval(
        "SELECT COUNT(*) FROM referrals WHERE credited=1") or 0
    s["referral_credits_given"] = await _fetchval(
        "SELECT COUNT(*) * 1.0 FROM referrals WHERE credited=1") or 0.0

    # ── Stock ─────────────────────────────────────────────────────────────────
    s["total_stock"]    = await _fetchval(
        "SELECT COUNT(*) FROM stock WHERE delivered=0") or 0
    s["stock_services"] = await _fetchval(
        "SELECT COUNT(DISTINCT service_id) FROM stock WHERE delivered=0") or 0

    return s
