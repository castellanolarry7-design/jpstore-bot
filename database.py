"""
database.py – Async SQLite database management
"""
import aiosqlite
from config import DATABASE_PATH


async def _migrate(db) -> None:
    """Add missing columns to existing tables (safe to run multiple times)."""
    # ── users columns ────────────────────────────────────────────────────────
    async with db.execute("PRAGMA table_info(users)") as cur:
        cols = {row[1] for row in await cur.fetchall()}

    for col, sql in {
        "lang":           "ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'en'",
        "credits":        "ALTER TABLE users ADD COLUMN credits REAL DEFAULT 0.0",
        "referral_code":  "ALTER TABLE users ADD COLUMN referral_code TEXT",
        "referred_by":    "ALTER TABLE users ADD COLUMN referred_by INTEGER",
        "first_purchase": "ALTER TABLE users ADD COLUMN first_purchase INTEGER DEFAULT 0",
        "is_banned":      "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
    }.items():
        if col not in cols:
            await db.execute(sql)

    # ── orders columns (only if table exists) ────────────────────────────────
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
    ) as cur:
        orders_exists = await cur.fetchone()

    if orders_exists:
        async with db.execute("PRAGMA table_info(orders)") as cur:
            order_cols = {row[1] for row in await cur.fetchall()}
        for col, sql in {
            "item_type":         "ALTER TABLE orders ADD COLUMN item_type TEXT DEFAULT 'service'",
            "credits_used":      "ALTER TABLE orders ADD COLUMN credits_used REAL DEFAULT 0.0",
            "expected_amount":   "ALTER TABLE orders ADD COLUMN expected_amount REAL",
            "payer_binance_id":  "ALTER TABLE orders ADD COLUMN payer_binance_id TEXT",
        }.items():
            if col not in order_cols:
                await db.execute(sql)

    # ── stock columns (only if table exists) ─────────────────────────────────
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='stock'"
    ) as cur:
        stock_exists = await cur.fetchone()

    if stock_exists:
        async with db.execute("PRAGMA table_info(stock)") as cur:
            stock_cols = {row[1] for row in await cur.fetchall()}
        for col, sql in {
            "label": "ALTER TABLE stock ADD COLUMN label TEXT",
        }.items():
            if col not in stock_cols:
                await db.execute(sql)

    await db.commit()


async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Users table — now with lang, credits, referral_code, referred_by
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
        # Orders table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                service_id       TEXT    NOT NULL,
                item_type        TEXT    DEFAULT 'service',
                amount           REAL    NOT NULL,
                expected_amount  REAL,
                credits_used     REAL    DEFAULT 0.0,
                payment_method   TEXT    NOT NULL,
                payment_proof    TEXT,
                payer_binance_id TEXT,
                status           TEXT    DEFAULT 'pending',
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivery_info    TEXT,
                admin_note       TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        # Stock table — one row per deliverable item
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
        # Referrals table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id     INTEGER NOT NULL,
                referred_id     INTEGER NOT NULL,
                credited        INTEGER DEFAULT 0,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(referrer_id) REFERENCES users(user_id),
                FOREIGN KEY(referred_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()
        # Run migrations AFTER all tables exist (adds missing columns to old DBs)
        await _migrate(db)


# ── Users ─────────────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: str | None, first_name: str,
                      referred_by: int | None = None) -> None:
    import hashlib
    code = hashlib.md5(str(user_id).encode()).hexdigest()[:8].upper()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, referral_code, referred_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username, first_name, code, referred_by))
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_lang(user_id: int) -> str:
    user = await get_user(user_id)
    return user["lang"] if user else "en"


async def set_user_lang(user_id: int, lang: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
        await db.commit()


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY joined_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def add_credits(user_id: int, amount: float) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def use_credits(user_id: int, amount: float) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET credits = MAX(0, credits - ?) WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def mark_first_purchase(user_id: int) -> int | None:
    """Marks first purchase and returns the referrer_id if one exists."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT first_purchase, referred_by FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row or row["first_purchase"]:
            return None  # already marked
        await db.execute(
            "UPDATE users SET first_purchase = 1 WHERE user_id = ?", (user_id,))
        await db.commit()
        return row["referred_by"]


# ── Orders ────────────────────────────────────────────────────────────────────

async def create_order(user_id: int, service_id: str, amount: float,
                       payment_method: str, item_type: str = "service",
                       credits_used: float = 0.0) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO orders (user_id, service_id, item_type, amount, payment_method, credits_used)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, service_id, item_type, amount, payment_method, credits_used))
        await db.commit()
        return cursor.lastrowid


async def set_order_payer(order_id: int, payer_binance_id: str, expected_amount: float) -> None:
    """Store the payer's Binance Pay ID and the unique expected amount."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE orders
            SET payer_binance_id = ?, expected_amount = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (payer_binance_id, expected_amount, order_id))
        await db.commit()


async def update_order_proof(order_id: int, proof: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE orders SET payment_proof = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (proof, order_id))
        await db.commit()


async def update_order_status(order_id: int, status: str,
                               admin_note: str = None, delivery_info: str = None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE orders
            SET status = ?,
                admin_note    = COALESCE(?, admin_note),
                delivery_info = COALESCE(?, delivery_info),
                updated_at    = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (status, admin_note, delivery_info, order_id))
        await db.commit()


async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_orders(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_pending_orders() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT o.*, u.username, u.first_name
            FROM orders o JOIN users u ON o.user_id = u.user_id
            WHERE o.status = 'pending' ORDER BY o.created_at ASC
        """) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_orders(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT o.*, u.username, u.first_name
            FROM orders o JOIN users u ON o.user_id = u.user_id
            ORDER BY o.created_at DESC LIMIT ?
        """, (limit,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_stats() -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        stats = {}
        for key, query in [
            ("total_users",      "SELECT COUNT(*) FROM users"),
            ("total_orders",     "SELECT COUNT(*) FROM orders"),
            ("pending_orders",   "SELECT COUNT(*) FROM orders WHERE status='pending'"),
            ("delivered_orders", "SELECT COUNT(*) FROM orders WHERE status='delivered'"),
            ("total_referrals",  "SELECT COUNT(*) FROM referrals"),
        ]:
            async with db.execute(query) as cur:
                stats[key] = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='delivered'"
        ) as cur:
            stats["total_revenue"] = (await cur.fetchone())[0]
        return stats


# ── Referrals ─────────────────────────────────────────────────────────────────

async def get_user_by_referral_code(code: str) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE referral_code = ?", (code,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def record_referral(referrer_id: int, referred_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id)
            VALUES (?, ?)
        """, (referrer_id, referred_id))
        await db.commit()


async def credit_referral(referrer_id: int, referred_id: int) -> bool:
    """Credit the referrer $1 — only once per referred user. Returns True if credited."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT credited FROM referrals WHERE referrer_id=? AND referred_id=?",
            (referrer_id, referred_id)
        ) as cur:
            row = await cur.fetchone()
        if not row or row[0]:
            return False
        await db.execute(
            "UPDATE referrals SET credited = 1 WHERE referrer_id=? AND referred_id=?",
            (referrer_id, referred_id)
        )
        await db.execute(
            "UPDATE users SET credits = credits + 1.0 WHERE user_id = ?", (referrer_id,))
        await db.commit()
        return True


async def get_referral_count(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)
        ) as cur:
            return (await cur.fetchone())[0]


# ── Stock ─────────────────────────────────────────────────────────────────────

async def add_stock_items(service_id: str, items: list[str], label: str = None) -> int:
    """Insert multiple stock items. Returns count added."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        count = 0
        for content in items:
            content = content.strip()
            if content:
                await db.execute(
                    "INSERT INTO stock (service_id, content, label) VALUES (?, ?, ?)",
                    (service_id, content, label)
                )
                count += 1
        await db.commit()
        return count


async def take_stock_item(service_id: str, order_id: int) -> dict | None:
    """
    Atomically grab one undelivered item for the service and mark it delivered.
    Returns the item dict or None if stock is empty.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Pick the oldest available item
        async with db.execute("""
            SELECT id, content, label FROM stock
            WHERE service_id = ? AND delivered = 0
            ORDER BY added_at ASC LIMIT 1
        """, (service_id,)) as cur:
            row = await cur.fetchone()

        if not row:
            return None

        item = dict(row)
        await db.execute("""
            UPDATE stock
            SET delivered = 1, order_id = ?, delivered_at = CURRENT_TIMESTAMP
            WHERE id = ? AND delivered = 0
        """, (order_id, item["id"]))
        await db.commit()
        return item


async def get_stock_levels() -> list[dict]:
    """Returns available stock count per service_id."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT service_id,
                   COUNT(*) FILTER (WHERE delivered = 0) AS available,
                   COUNT(*) FILTER (WHERE delivered = 1) AS delivered
            FROM stock
            GROUP BY service_id
            ORDER BY service_id
        """) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_stock_level(service_id: str) -> int:
    """Returns available item count for one service."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM stock WHERE service_id = ? AND delivered = 0",
            (service_id,)
        ) as cur:
            return (await cur.fetchone())[0]


async def take_stock_items_multi(service_id: str, order_id: int, qty: int) -> list[dict]:
    """
    Atomically grab `qty` undelivered items for the service.
    Returns list of item dicts (may be shorter than qty if stock runs out).
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, content, label FROM stock
            WHERE service_id = ? AND delivered = 0
            ORDER BY added_at ASC LIMIT ?
        """, (service_id, qty)) as cur:
            rows = await cur.fetchall()

        items = [dict(r) for r in rows]
        for item in items:
            await db.execute("""
                UPDATE stock
                SET delivered = 1, order_id = ?, delivered_at = CURRENT_TIMESTAMP
                WHERE id = ? AND delivered = 0
            """, (order_id, item["id"]))
        await db.commit()
        return items


async def get_stock_levels_dict() -> dict:
    """Returns {service_id: available_count} for all services with stock."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT service_id, COUNT(*) as cnt
            FROM stock WHERE delivered = 0
            GROUP BY service_id
        """) as cur:
            rows = await cur.fetchall()
            return {row[0]: row[1] for row in rows}


async def get_stock_items(service_id: str, limit: int = 50) -> list[dict]:
    """Returns available (undelivered) stock items for a service."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, content, label, added_at
            FROM stock
            WHERE service_id = ? AND delivered = 0
            ORDER BY added_at ASC LIMIT ?
        """, (service_id, limit)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_stock_delivered(service_id: str, limit: int = 20) -> list[dict]:
    """Returns recently delivered stock items for a service."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, content, order_id, delivered_at
            FROM stock
            WHERE service_id = ? AND delivered = 1
            ORDER BY delivered_at DESC LIMIT ?
        """, (service_id, limit)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_stock_item(item_id: int) -> bool:
    """Hard-delete a stock item by ID. Returns True if found and deleted."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT id FROM stock WHERE id = ? AND delivered = 0", (item_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        await db.execute("DELETE FROM stock WHERE id = ?", (item_id,))
        await db.commit()
        return True


async def get_all_stock_summary() -> list[dict]:
    """Returns summary of all services: available + delivered counts."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT service_id,
                   SUM(CASE WHEN delivered=0 THEN 1 ELSE 0 END) AS available,
                   SUM(CASE WHEN delivered=1 THEN 1 ELSE 0 END) AS delivered
            FROM stock
            GROUP BY service_id
            ORDER BY service_id
        """) as cur:
            return [dict(r) for r in await cur.fetchall()]
