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
    # Safe ALTER TABLE ADD COLUMN IF NOT EXISTS (PG 9.6+)
    for tbl, col, typedef in [
        ("users",  "credits",              "REAL DEFAULT 0.0"),
        ("users",  "referral_code",        "TEXT"),
        ("users",  "referred_by",          "BIGINT"),
        ("users",  "first_purchase",       "INTEGER DEFAULT 0"),
        ("users",  "is_banned",            "INTEGER DEFAULT 0"),
        ("orders", "item_type",            "TEXT DEFAULT 'service'"),
        ("orders", "credits_used",         "REAL DEFAULT 0.0"),
        ("orders", "expected_amount",      "REAL"),
        ("orders", "payer_binance_id",     "TEXT"),
        ("orders", "instruction_msg_id",   "BIGINT"),
        ("orders", "instruction_chat_id",  "BIGINT"),
        ("stock",  "label",                "TEXT"),
    ]:
        try:
            await conn.execute(
                f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {typedef}"
            )
        except Exception:
            pass


async def _create_tables_sqlite(db) -> None:
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
    return await _fetch("""
        SELECT o.*, u.username, u.first_name
        FROM orders o JOIN users u ON o.user_id = u.user_id
        WHERE o.status = 'pending' ORDER BY o.created_at ASC
    """)


async def get_stats() -> dict:
    stats = {}
    for key, q in [
        ("total_users",      "SELECT COUNT(*) FROM users"),
        ("total_orders",     "SELECT COUNT(*) FROM orders WHERE item_type != 'topup'"),
        ("pending_orders",   "SELECT COUNT(*) FROM orders WHERE status='pending' AND item_type!='topup'"),
        ("delivered_orders", "SELECT COUNT(*) FROM orders WHERE status='delivered'"),
        ("total_referrals",  "SELECT COUNT(*) FROM referrals"),
    ]:
        stats[key] = await _fetchval(q) or 0
    stats["total_revenue"] = await _fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered' AND item_type!='topup'"
    ) or 0.0
    return stats


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
