"""
bot.py – JPStore Bot entry point
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
from database import init_db

# Handlers
from handlers.start    import start, show_language_selector, set_language, support
from handlers.catalog  import (show_catalog, show_service, show_payment_methods,
                                show_quantity_selector, select_quantity)
from handlers.methods  import (show_methods, show_method_detail,
                                show_method_payment, initiate_method_payment)
from handlers.referrals import show_referrals
from handlers.orders   import (
    initiate_payment, request_proof, receive_proof,
    cancel_proof, my_orders, cancel_order,
    receive_payer_id, cancel_binance_id,
    WAITING_PROOF, WAITING_PAYER_ID,
)
from handlers.admin    import (
    # Auth
    admin_entry, admin_check_password,
    # Panel sections
    admin_panel, admin_stats, admin_users,
    admin_pending_orders, admin_mark_paid, admin_cancel_order,
    admin_deliver_start, admin_deliver_confirm,
    admin_broadcast_start, admin_broadcast_send,
    admin_cancel_conv, noop_callback,
    # Stock management
    admin_stock_menu,
    admin_stock_view_pick, admin_stock_view_items,
    admin_stock_add_pick, admin_stock_add_service,
    admin_stock_receive_creds, admin_stock_add_cancel,
    admin_stock_del_pick, admin_stock_del_view, admin_stock_del_item,
    # Legacy /addstock /stock commands
    cmd_addstock, cmd_stock,
    stock_receive_items, stock_cancel,
    # States
    WAITING_ADMIN_PASSWORD, WAITING_DELIVERY_INFO,
    WAITING_BROADCAST_MSG, WAITING_STOCK_ADD_CREDS,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    await init_db()
    logger.info("✅ Database initialized.")
    logger.info("🤖 JPStore Bot started.")


def build_application() -> Application:
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ══════════════════════════════════════════════════════════════════════════
    # CONVERSATIONS
    # ══════════════════════════════════════════════════════════════════════════

    # ── Admin auth (/admin with password gate) ────────────────────────────────
    admin_auth_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_entry)],
        states={
            WAITING_ADMIN_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_check_password),
            ]
        },
        fallbacks=[CommandHandler("cancel", admin_cancel_conv)],
        allow_reentry=True,
    )
    app.add_handler(admin_auth_conv)

    # ── Stock add (entry via panel button admin_stock_add_<service_id>) ───────
    stock_add_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_stock_add_service, pattern=r"^admin_stock_add_.+$"),
        ],
        states={
            WAITING_STOCK_ADD_CREDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_stock_receive_creds),
                CommandHandler("cancelar", admin_stock_add_cancel),
                CommandHandler("cancel",   admin_stock_add_cancel),
            ]
        },
        fallbacks=[
            CommandHandler("cancelar", admin_stock_add_cancel),
            CommandHandler("cancel",   admin_stock_add_cancel),
        ],
        allow_reentry=True,
    )
    app.add_handler(stock_add_conv)

    # ── Binance Pay payer ID flow ─────────────────────────────────────────────
    payer_id_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(initiate_payment,        pattern=r"^pay_binance_.+$"),
            CallbackQueryHandler(initiate_method_payment, pattern=r"^mpay_binance_.+$"),
        ],
        states={
            WAITING_PAYER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_payer_id),
                CommandHandler("cancel",   cancel_binance_id),
                CommandHandler("cancelar", cancel_binance_id),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   cancel_binance_id),
            CommandHandler("cancelar", cancel_binance_id),
        ],
        allow_reentry=True,
    )
    app.add_handler(payer_id_conv)

    # ── Payment proof submission ──────────────────────────────────────────────
    proof_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(request_proof, pattern=r"^proof_\d+$")],
        states={
            WAITING_PROOF: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_proof),
                CommandHandler("cancel",   cancel_proof),
                CommandHandler("cancelar", cancel_proof),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   cancel_proof),
            CommandHandler("cancelar", cancel_proof),
        ],
        allow_reentry=True,
    )
    app.add_handler(proof_conv)

    # ── Admin manual deliver ──────────────────────────────────────────────────
    deliver_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_deliver_start,
                                           pattern=r"^admin_deliver_\d+$")],
        states={
            WAITING_DELIVERY_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_deliver_confirm),
                CommandHandler("cancel",   admin_cancel_conv),
                CommandHandler("cancelar", admin_cancel_conv),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
        ],
        allow_reentry=True,
    )
    app.add_handler(deliver_conv)

    # ── Broadcast ─────────────────────────────────────────────────────────────
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start,
                                           pattern=r"^admin_broadcast$")],
        states={
            WAITING_BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send),
                CommandHandler("cancel",   admin_cancel_conv),
                CommandHandler("cancelar", admin_cancel_conv),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
        ],
        allow_reentry=True,
    )
    app.add_handler(broadcast_conv)

    # ══════════════════════════════════════════════════════════════════════════
    # PLAIN COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("addstock", cmd_addstock))
    app.add_handler(CommandHandler("stock",    cmd_stock))

    # ══════════════════════════════════════════════════════════════════════════
    # CALLBACK QUERY HANDLERS
    # ══════════════════════════════════════════════════════════════════════════

    # ── Navigation ────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(start,                  pattern=r"^home$"))
    app.add_handler(CallbackQueryHandler(support,                pattern=r"^support$"))
    app.add_handler(CallbackQueryHandler(show_language_selector, pattern=r"^language$"))
    app.add_handler(CallbackQueryHandler(set_language,           pattern=r"^setlang_(en|es)$"))

    # ── Catalog ───────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_catalog,           pattern=r"^catalog$"))
    app.add_handler(CallbackQueryHandler(show_service,           pattern=r"^service_.+$"))
    app.add_handler(CallbackQueryHandler(show_quantity_selector, pattern=r"^qtysel_.+$"))
    app.add_handler(CallbackQueryHandler(select_quantity,        pattern=r"^qty_.+_\d+$"))
    app.add_handler(CallbackQueryHandler(show_payment_methods,   pattern=r"^buy_.+$"))
    app.add_handler(CallbackQueryHandler(initiate_payment,       pattern=r"^pay_(trc20|bep20)_.+$"))

    # ── Methods ───────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_methods,            pattern=r"^methods$"))
    app.add_handler(CallbackQueryHandler(show_method_detail,      pattern=r"^method_.+$"))
    app.add_handler(CallbackQueryHandler(show_method_payment,     pattern=r"^mbuy_.+$"))
    app.add_handler(CallbackQueryHandler(initiate_method_payment, pattern=r"^mpay_(trc20|bep20)_.+$"))

    # ── Orders ────────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(my_orders,              pattern=r"^my_orders$"))
    app.add_handler(CallbackQueryHandler(cancel_order,           pattern=r"^cancel_\d+$"))

    # ── Referrals ─────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_referrals,         pattern=r"^referrals$"))

    # ── Admin panel ───────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(admin_panel,            pattern=r"^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_stats,            pattern=r"^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_pending_orders,   pattern=r"^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_mark_paid,        pattern=r"^admin_paid_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_order,     pattern=r"^admin_cancel_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_users,            pattern=r"^admin_users$"))
    app.add_handler(CallbackQueryHandler(noop_callback,          pattern=r"^noop$"))

    # ── Stock management ─────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(admin_stock_menu,       pattern=r"^admin_stock$"))
    app.add_handler(CallbackQueryHandler(admin_stock_view_pick,  pattern=r"^admin_stock_view$"))
    app.add_handler(CallbackQueryHandler(admin_stock_view_items, pattern=r"^admin_stock_items_.+$"))
    app.add_handler(CallbackQueryHandler(admin_stock_add_pick,   pattern=r"^admin_stock_add_pick$"))
    app.add_handler(CallbackQueryHandler(admin_stock_del_pick,   pattern=r"^admin_stock_del_pick$"))
    app.add_handler(CallbackQueryHandler(admin_stock_del_view,   pattern=r"^admin_stock_delview_.+$"))
    app.add_handler(CallbackQueryHandler(admin_stock_del_item,   pattern=r"^admin_stock_delitem_\d+$"))

    return app


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN not configured. Check your .env file.")
    app = build_application()
    logger.info("🚀 Starting JPStore Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
