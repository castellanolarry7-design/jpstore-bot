"""
stats.py – /estadisticas hidden command for admins
Shows comprehensive bot metrics: users, revenue, orders, referrals, stock.
"""
from telegram import Update
from telegram.ext import ContextTypes
from handlers.admin import is_admin
import database as db
from config import SERVICES, METHODS

# ── Display helpers ────────────────────────────────────────────────────────────

_LANG_FLAGS = {
    "en": "🇺🇸 EN", "es": "🇪🇸 ES", "hi": "🇮🇳 HI",
    "id": "🇮🇩 ID", "ur": "🇵🇰 UR", "zh": "🇨🇳 ZH",
}

_PM_LABELS = {
    "trc20":       "USDT TRC20",
    "bep20":       "USDT BEP20",
    "binance_pay": "Binance Pay (API)",
    "binance_id":  "Binance ID (manual)",
    "balance":     "Saldo interno",
}


def _svc_label(service_id: str) -> str:
    """Human-readable name for a service_id."""
    all_s = {**SERVICES, **METHODS, **db.get_cached_db_products()}
    svc = all_s.get(service_id, {})
    return f"{svc.get('emoji', '📦')} {svc.get('name', service_id)}"


def _bar(value: int, total: int, width: int = 10) -> str:
    """Simple ASCII progress bar."""
    if total == 0:
        return "░" * width
    filled = round(value / total * width)
    return "█" * filled + "░" * (width - filled)


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Hidden command /estadisticas — full stats panel, admin-only.
    Not listed anywhere in the bot UI; only known to admins.
    """
    user = update.effective_user
    if not is_admin(user.id):
        return  # Silent ignore for non-admins

    # Acknowledge immediately — queries can take a moment
    sent = await update.message.reply_text("📊 <i>Generando estadísticas…</i>",
                                           parse_mode="HTML")

    s = await db.get_full_stats()

    # ── Section: Users ─────────────────────────────────────────────────────────
    lang_str = "  ".join(
        f"{_LANG_FLAGS.get(lang, lang.upper())}: {cnt}"
        for lang, cnt in s.get("langs", [])
    ) or "—"

    users_block = (
        "👥 <b>USUARIOS</b>\n"
        f"  Total registrados : <b>{s['total_users']:,}</b>\n"
        f"  🆕 Hoy            : <b>{s['new_today']}</b>\n"
        f"  📅 Esta semana    : <b>{s['new_week']}</b>\n"
        f"  🗓️ Este mes        : <b>{s['new_month']}</b>\n"
        f"  🚫 Baneados       : <b>{s['banned_users']}</b>\n"
        f"  💎 Créditos total : <b>${s['total_credits']:.2f}</b>\n"
        f"  🌐 Idiomas        : {lang_str}"
    )

    # ── Section: Revenue ───────────────────────────────────────────────────────
    total_rev = s["total_revenue"] + s["topup_revenue"]
    revenue_block = (
        "💰 <b>INGRESOS</b>\n"
        f"  All time (ventas) : <b>${s['total_revenue']:.2f}</b>\n"
        f"  Recargas saldo    : <b>${s['topup_revenue']:.2f}</b>\n"
        f"  ─────────────────────\n"
        f"  TOTAL acumulado   : <b>${total_rev:.2f}</b>\n"
        f"  📆 Hoy            : <b>${s['today_revenue']:.2f}</b>\n"
        f"  📅 Esta semana    : <b>${s['week_revenue']:.2f}</b>\n"
        f"  🗓️ Este mes        : <b>${s['month_revenue']:.2f}</b>\n"
        f"  🎯 Ticket promedio: <b>${s['avg_order']:.2f}</b>"
    )

    # ── Section: Orders ────────────────────────────────────────────────────────
    total_ord = s["total_orders"] or 1  # avoid div-by-zero in bars
    orders_block = (
        "🛒 <b>PEDIDOS</b>\n"
        f"  Total             : <b>{s['total_orders']:,}</b>\n"
        f"  ✅ Entregados     : <b>{s['delivered_orders']}</b>  "
        f"{_bar(s['delivered_orders'], total_ord)}\n"
        f"  ⏳ Pendientes     : <b>{s['pending_orders']}</b>  "
        f"{_bar(s['pending_orders'], total_ord)}\n"
        f"  ❌ Cancelados     : <b>{s['cancelled_orders']}</b>  "
        f"{_bar(s['cancelled_orders'], total_ord)}\n"
        f"  💵 Recargas OK    : <b>{s['total_topups']}</b>"
    )

    # ── Section: Payment methods ───────────────────────────────────────────────
    if s.get("payment_methods"):
        pm_lines = "\n".join(
            f"  • {_PM_LABELS.get(pm, pm)}: <b>{cnt}</b>"
            for pm, cnt in s["payment_methods"]
        )
        pm_block = "💳 <b>MÉTODOS DE PAGO</b>\n" + pm_lines
    else:
        pm_block = "💳 <b>MÉTODOS DE PAGO</b>\n  — Sin datos aún"

    # ── Section: Top products ──────────────────────────────────────────────────
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    if s.get("top_products"):
        top_lines = "\n".join(
            f"  {medals[i] if i < len(medals) else '•'} {_svc_label(sid)}: <b>{cnt} venta{'s' if cnt != 1 else ''}</b>"
            for i, (sid, cnt) in enumerate(s["top_products"])
        )
        top_block = "🏆 <b>TOP 5 PRODUCTOS</b>\n" + top_lines
    else:
        top_block = "🏆 <b>TOP 5 PRODUCTOS</b>\n  — Sin ventas aún"

    # ── Section: Referrals ─────────────────────────────────────────────────────
    ref_block = (
        "🤝 <b>REFERIDOS</b>\n"
        f"  Total registrados : <b>{s['total_referrals']}</b>\n"
        f"  ✅ Convertidos    : <b>{s['credited_referrals']}</b>\n"
        f"  💰 Créditos dados : <b>${s['credited_referrals'] * 1.0:.2f}</b>"
    )

    # ── Section: Stock ─────────────────────────────────────────────────────────
    stock_block = (
        "📦 <b>STOCK</b>\n"
        f"  Items disponibles : <b>{s['total_stock']:,}</b>\n"
        f"  Servicios con stock: <b>{s['stock_services']}</b>"
    )

    # ── Assemble full message ──────────────────────────────────────────────────
    sep = "\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
    report = (
        "📊 <b>ESTADÍSTICAS — RESELIBOT</b>\n"
        "═══════════════════════════\n"
        + sep.join([
            users_block,
            revenue_block,
            orders_block,
            pm_block,
            top_block,
            ref_block,
            stock_block,
        ])
        + "\n═══════════════════════════"
    )

    # Edit the "generating…" message with the full report
    try:
        await sent.edit_text(report, parse_mode="HTML")
    except Exception:
        # Message too long — split into two
        half = len(report) // 2
        split_at = report.rfind("\n", 0, half)
        await sent.edit_text(report[:split_at], parse_mode="HTML")
        await update.message.reply_text(report[split_at:], parse_mode="HTML")
