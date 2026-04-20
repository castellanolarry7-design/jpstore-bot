"""
bot.py – ReseliBot entry point
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from config import BOT_TOKEN
from database import init_db

# Handlers
from handlers.start    import start, show_language_selector, set_language, support, check_membership_callback
from utils.membership  import check_membership_detail, build_gate_message
from handlers.catalog  import (show_catalog, show_catalog_page, show_service,
                                show_payment_methods, show_quantity_selector,
                                qty_control, select_quantity)
from handlers.methods  import (show_methods, show_method_detail,
                                show_method_payment, initiate_method_payment,
                                initiate_balance_method_payment)
from handlers.referrals import show_referrals
from handlers.orders   import (
    initiate_payment, request_proof, receive_proof,
    cancel_proof, my_orders, cancel_order,
    receive_payer_id, cancel_binance_id,
    initiate_balance_payment,
    WAITING_PROOF, WAITING_PAYER_ID,
)
from handlers.balance  import (
    show_balance, show_recargar, recargar_amount,
    initiate_topup_payment, initiate_topup_binance,
    receive_topup_payer_id, cancel_topup,
    ask_custom_topup, receive_custom_topup,
    WAITING_TOPUP_PAYER_ID, WAITING_CUSTOM_TOPUP,
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
    # Product management
    admin_products, admin_cleanup,
    admin_product_add_start,
    admin_product_name, admin_product_emoji, admin_product_price,
    admin_product_desc_en, admin_product_desc_es,
    admin_product_delivery_en, admin_product_delivery_es,
    admin_product_photo_received, admin_product_no_photo,
    admin_product_confirm, admin_product_cancel, admin_product_del,
    # Photo management
    admin_static_photos, admin_prod_photo_menu,
    admin_photo_upload_prompt, admin_photo_receive, admin_photo_delete,
    # Welcome photo command
    cmd_setphoto, receive_welcome_photo,
    # DB product editing
    admin_prod_edit_menu,
    admin_prod_edit_field_start, admin_prod_edit_receive,
    # Static product/method override editing
    admin_static_edit_list, admin_static_edit_menu,
    admin_static_edit_start, admin_static_edit_receive,
    # Method management
    admin_methods_menu,
    admin_method_add_start,
    admin_method_name, admin_method_emoji, admin_method_price,
    admin_method_desc_en, admin_method_desc_es,
    admin_method_delivery_en, admin_method_delivery_es,
    admin_method_confirm, admin_method_cancel, admin_method_del,
    admin_method_edit_price_start, admin_method_edit_price_receive,
    # Legacy /addstock /stock commands
    cmd_addstock, cmd_stock,
    # States
    WAITING_ADMIN_PASSWORD, WAITING_DELIVERY_INFO,
    WAITING_BROADCAST_MSG, WAITING_STOCK_ADD_CREDS,
    WAITING_PROD_NAME, WAITING_PROD_EMOJI, WAITING_PROD_PRICE,
    WAITING_PROD_DESC_EN, WAITING_PROD_DESC_ES,
    WAITING_PROD_DELIVERY_EN, WAITING_PROD_DELIVERY_ES,
    WAITING_PROD_PHOTO, WAITING_SET_PHOTO, WAITING_WELCOME_PHOTO,
    WAITING_PROD_EDIT_VALUE, WAITING_STATIC_EDIT_VALUE,
    WAITING_METHOD_NAME, WAITING_METHOD_EMOJI, WAITING_METHOD_PRICE,
    WAITING_METHOD_DESC_EN, WAITING_METHOD_DESC_ES,
    WAITING_METHOD_DELIVERY_EN, WAITING_METHOD_DELIVERY_ES,
    WAITING_METHOD_EDIT_PRICE,
)
from handlers.stats import cmd_estadisticas
from handlers.membership_middleware import membership_middleware

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    await init_db()
    logger.info("✅ Database initialized.")
    logger.info("🤖 ReseliBot started.")


def build_application() -> Application:
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ══════════════════════════════════════════════════════════════════════════
    # GLOBAL MIDDLEWARE — membership gate (group=-1, runs before everything)
    # ══════════════════════════════════════════════════════════════════════════
    app.add_handler(TypeHandler(Update, membership_middleware), group=-1)

    # ══════════════════════════════════════════════════════════════════════════
    # CONVERSATIONS
    # ══════════════════════════════════════════════════════════════════════════

    # ── Admin auth (/weboadmin with password gate) ────────────────────────────
    admin_auth_conv = ConversationHandler(
        entry_points=[CommandHandler("weboadmin", admin_entry)],
        states={
            WAITING_ADMIN_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_check_password),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
            CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
        ],
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
                # Allow pressing the stock/panel buttons to exit the conversation
                CallbackQueryHandler(admin_stock_add_cancel, pattern=r"^admin_stock$"),
                CallbackQueryHandler(admin_panel,            pattern=r"^admin_panel$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancelar", admin_stock_add_cancel),
            CommandHandler("cancel",   admin_stock_add_cancel),
            CallbackQueryHandler(admin_stock_add_cancel, pattern=r"^admin_stock$"),
            CallbackQueryHandler(admin_panel,            pattern=r"^admin_panel$"),
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
                CallbackQueryHandler(cancel_binance_id, pattern=r"^cancel_payer_id$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   cancel_binance_id),
            CommandHandler("cancelar", cancel_binance_id),
            CallbackQueryHandler(cancel_binance_id, pattern=r"^cancel_payer_id$"),
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
                CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
            CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(deliver_conv)

    # ── Top-Up Binance Pay payer ID flow ─────────────────────────────────────
    topup_binance_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(initiate_topup_binance, pattern=r"^topup_pay_binance_\d+(\.\d+)?$"),
        ],
        states={
            WAITING_TOPUP_PAYER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_topup_payer_id),
                CommandHandler("cancel",   cancel_topup),
                CommandHandler("cancelar", cancel_topup),
                CallbackQueryHandler(cancel_topup, pattern=r"^cancel_topup$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   cancel_topup),
            CommandHandler("cancelar", cancel_topup),
            CallbackQueryHandler(cancel_topup, pattern=r"^cancel_topup$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(topup_binance_conv)

    # ── Broadcast ─────────────────────────────────────────────────────────────
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start,
                                           pattern=r"^admin_broadcast$")],
        states={
            WAITING_BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send),
                CommandHandler("cancel",   admin_cancel_conv),
                CommandHandler("cancelar", admin_cancel_conv),
                CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
            CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(broadcast_conv)

    # ── Product creation (multi-step) ────────────────────────────────────────
    product_create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_product_add_start, pattern=r"^admin_prod_add$")],
        states={
            WAITING_PROD_NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_name),
                                       CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                       CallbackQueryHandler(admin_products, pattern=r"^admin_products$")],
            WAITING_PROD_EMOJI:       [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_emoji),
                                       CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                       CallbackQueryHandler(admin_products, pattern=r"^admin_products$")],
            WAITING_PROD_PRICE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_price),
                                       CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                       CallbackQueryHandler(admin_products, pattern=r"^admin_products$")],
            WAITING_PROD_DESC_EN:     [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_desc_en),
                                       CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                       CallbackQueryHandler(admin_products, pattern=r"^admin_products$")],
            WAITING_PROD_DESC_ES:     [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_desc_es),
                                       CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                       CallbackQueryHandler(admin_products, pattern=r"^admin_products$")],
            WAITING_PROD_DELIVERY_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_delivery_en),
                                       CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                       CallbackQueryHandler(admin_products, pattern=r"^admin_products$")],
            WAITING_PROD_DELIVERY_ES: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_delivery_es),
                                       CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                       CallbackQueryHandler(admin_products, pattern=r"^admin_products$")],
            WAITING_PROD_PHOTO:       [
                MessageHandler(filters.PHOTO, admin_product_photo_received),
                CallbackQueryHandler(admin_product_no_photo, pattern=r"^admin_prod_no_photo$"),
                CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                CallbackQueryHandler(admin_products, pattern=r"^admin_products$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
            CallbackQueryHandler(admin_product_cancel, pattern=r"^admin_prod_cancel$"),
            CallbackQueryHandler(admin_panel,          pattern=r"^admin_panel$"),
            CallbackQueryHandler(admin_products,       pattern=r"^admin_products$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(product_create_conv)

    # ── /setphoto — set the bot welcome image ────────────────────────────────
    setphoto_conv = ConversationHandler(
        entry_points=[CommandHandler("setphoto", cmd_setphoto)],
        states={
            WAITING_WELCOME_PHOTO: [
                MessageHandler(filters.PHOTO, receive_welcome_photo),
                CommandHandler("cancel",   admin_cancel_conv),
                CommandHandler("cancelar", admin_cancel_conv),
            ],
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
        ],
        allow_reentry=True,
    )
    app.add_handler(setphoto_conv)

    # ── Set photo for existing product (static or dynamic) ────────────────────
    # Entry point: clicking any "📷 Foto" product button → admin_prod_photo_menu
    # which stores photo_target_sid, shows current photo, and enters WAITING_SET_PHOTO.
    set_photo_conv = ConversationHandler(
        entry_points=[
            # Main entry: admin clicks photo button for any product
            CallbackQueryHandler(admin_prod_photo_menu,    pattern=r"^admin_prod_photo_.+$"),
            # Legacy re-entry: "Subir / cambiar" from any stale message
            CallbackQueryHandler(admin_photo_upload_prompt, pattern=r"^admin_photo_upload_prompt$"),
        ],
        states={
            WAITING_SET_PHOTO: [
                # Accept both compressed photos AND images sent as documents
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, admin_photo_receive),
                # Allow cancellation via button
                CallbackQueryHandler(admin_products, pattern=r"^admin_products$"),
                CallbackQueryHandler(admin_panel,    pattern=r"^admin_panel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
            CallbackQueryHandler(admin_products, pattern=r"^admin_products$"),
            CallbackQueryHandler(admin_panel,    pattern=r"^admin_panel$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(set_photo_conv)

    # ── DB product field edit ─────────────────────────────────────────────────
    # Entry: admin_pef_<db_id>_<field>  (e.g. admin_pef_7_description_en)
    prod_edit_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_prod_edit_field_start,
                                 pattern=r"^admin_pef_\d+_.+$"),
        ],
        states={
            WAITING_PROD_EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_prod_edit_receive),
                CommandHandler("cancel",   admin_cancel_conv),
                CommandHandler("cancelar", admin_cancel_conv),
                CallbackQueryHandler(admin_products, pattern=r"^admin_products$"),
                CallbackQueryHandler(admin_panel,    pattern=r"^admin_panel$"),
                # "Cancel" in the edit prompt goes back to the edit menu
                CallbackQueryHandler(admin_prod_edit_menu, pattern=r"^admin_prod_edit_\d+$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
            CallbackQueryHandler(admin_products, pattern=r"^admin_products$"),
            CallbackQueryHandler(admin_panel,    pattern=r"^admin_panel$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(prod_edit_conv)

    # ── Static product/method override edit ───────────────────────────────────
    # Entry: admin_sef_<service_id>_<field>  (e.g. admin_sef_gemini_pro_1m_price)
    static_edit_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_static_edit_start, pattern=r"^admin_sef_.+$"),
        ],
        states={
            WAITING_STATIC_EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_static_edit_receive),
                CommandHandler("cancel",   admin_cancel_conv),
                CommandHandler("cancelar", admin_cancel_conv),
                CallbackQueryHandler(admin_products,          pattern=r"^admin_products$"),
                CallbackQueryHandler(admin_panel,             pattern=r"^admin_panel$"),
                CallbackQueryHandler(admin_static_edit_menu,  pattern=r"^admin_sedit_.+$"),
                CallbackQueryHandler(admin_static_edit_list,  pattern=r"^admin_static_edit_list$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
            CallbackQueryHandler(admin_products,         pattern=r"^admin_products$"),
            CallbackQueryHandler(admin_panel,            pattern=r"^admin_panel$"),
            CallbackQueryHandler(admin_static_edit_list, pattern=r"^admin_static_edit_list$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(static_edit_conv)

    # ── Custom top-up amount ──────────────────────────────────────────────────
    custom_topup_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_custom_topup, pattern=r"^topup_custom$"),
        ],
        states={
            WAITING_CUSTOM_TOPUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_topup),
                CommandHandler("cancel",   cancel_topup),
                CommandHandler("cancelar", cancel_topup),
                CallbackQueryHandler(cancel_topup, pattern=r"^cancel_topup$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancel",   cancel_topup),
            CommandHandler("cancelar", cancel_topup),
            CallbackQueryHandler(cancel_topup, pattern=r"^cancel_topup$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(custom_topup_conv)

    # ── Method creation & price-edit (multi-step) ────────────────────────────
    method_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_method_add_start,       pattern=r"^admin_method_add$"),
            CallbackQueryHandler(admin_method_edit_price_start, pattern=r"^admin_method_edit_\w+$"),
        ],
        states={
            WAITING_METHOD_NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_method_name),
                                         CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                         CallbackQueryHandler(admin_methods_menu, pattern=r"^admin_methods$")],
            WAITING_METHOD_EMOJI:       [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_method_emoji),
                                         CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                         CallbackQueryHandler(admin_methods_menu, pattern=r"^admin_methods$")],
            WAITING_METHOD_PRICE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_method_price),
                                         CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                         CallbackQueryHandler(admin_methods_menu, pattern=r"^admin_methods$")],
            WAITING_METHOD_DESC_EN:     [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_method_desc_en),
                                         CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                         CallbackQueryHandler(admin_methods_menu, pattern=r"^admin_methods$")],
            WAITING_METHOD_DESC_ES:     [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_method_desc_es),
                                         CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                         CallbackQueryHandler(admin_methods_menu, pattern=r"^admin_methods$")],
            WAITING_METHOD_DELIVERY_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_method_delivery_en),
                                         CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                         CallbackQueryHandler(admin_methods_menu, pattern=r"^admin_methods$")],
            WAITING_METHOD_DELIVERY_ES: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_method_delivery_es),
                                         CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                         CallbackQueryHandler(admin_methods_menu, pattern=r"^admin_methods$")],
            WAITING_METHOD_EDIT_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_method_edit_price_receive),
                                         CallbackQueryHandler(admin_panel, pattern=r"^admin_panel$"),
                                         CallbackQueryHandler(admin_methods_menu, pattern=r"^admin_methods$")],
        },
        fallbacks=[
            CommandHandler("cancel",   admin_cancel_conv),
            CommandHandler("cancelar", admin_cancel_conv),
            CallbackQueryHandler(admin_method_cancel, pattern=r"^admin_method_cancel$"),
            CallbackQueryHandler(admin_panel,         pattern=r"^admin_panel$"),
            CallbackQueryHandler(admin_methods_menu,  pattern=r"^admin_methods$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(method_conv)

    # ══════════════════════════════════════════════════════════════════════════
    # PLAIN COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    app.add_handler(CommandHandler("start",         start))
    app.add_handler(CommandHandler("addstock",      cmd_addstock))
    app.add_handler(CommandHandler("stock",         cmd_stock))
    app.add_handler(CommandHandler("estadisticas",  cmd_estadisticas))  # hidden admin command

    # ══════════════════════════════════════════════════════════════════════════
    # CALLBACK QUERY HANDLERS
    # ══════════════════════════════════════════════════════════════════════════

    # ── Membership gate ───────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(check_membership_callback, pattern=r"^check_membership$"))

    # ── Navigation ────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(start,                  pattern=r"^home$"))
    app.add_handler(CallbackQueryHandler(support,                pattern=r"^support$"))
    app.add_handler(CallbackQueryHandler(show_language_selector, pattern=r"^language$"))
    app.add_handler(CallbackQueryHandler(set_language,           pattern=r"^setlang_(en|es|hi|id|ur|zh)$"))

    # ── Catalog ───────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_catalog,           pattern=r"^catalog$"))
    app.add_handler(CallbackQueryHandler(show_catalog_page,      pattern=r"^catalog_page_\d+$"))
    app.add_handler(CallbackQueryHandler(show_service,           pattern=r"^service_.+$"))
    app.add_handler(CallbackQueryHandler(show_quantity_selector, pattern=r"^qtysel_.+$"))
    app.add_handler(CallbackQueryHandler(qty_control,            pattern=r"^qtyctrl_.+_\d+$"))
    app.add_handler(CallbackQueryHandler(select_quantity,        pattern=r"^qty_.+_\d+$"))
    app.add_handler(CallbackQueryHandler(show_payment_methods,   pattern=r"^buy_.+$"))
    app.add_handler(CallbackQueryHandler(initiate_payment,       pattern=r"^pay_(trc20|bep20)_.+$"))
    app.add_handler(CallbackQueryHandler(initiate_balance_payment, pattern=r"^pay_balance_.+$"))

    # ── Methods ───────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_methods,            pattern=r"^methods$"))
    app.add_handler(CallbackQueryHandler(show_method_detail,      pattern=r"^method_.+$"))
    app.add_handler(CallbackQueryHandler(show_method_payment,            pattern=r"^mbuy_.+$"))
    app.add_handler(CallbackQueryHandler(initiate_method_payment,        pattern=r"^mpay_(trc20|bep20)_.+$"))
    app.add_handler(CallbackQueryHandler(initiate_balance_method_payment, pattern=r"^mpay_balance_.+$"))

    # ── Orders ────────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(my_orders,              pattern=r"^my_orders$"))
    app.add_handler(CallbackQueryHandler(cancel_order,           pattern=r"^cancel_\d+$"))
    # Standalone fallback for stale cancel_payer_id / cancel_topup buttons
    app.add_handler(CallbackQueryHandler(cancel_binance_id,      pattern=r"^cancel_payer_id$"))
    app.add_handler(CallbackQueryHandler(cancel_topup,           pattern=r"^cancel_topup$"))

    # ── Balance / Top-Up ─────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_balance,            pattern=r"^balance$"))
    app.add_handler(CallbackQueryHandler(show_recargar,           pattern=r"^recargar$"))
    app.add_handler(CallbackQueryHandler(recargar_amount,         pattern=r"^topup_\d+$"))
    app.add_handler(CallbackQueryHandler(initiate_topup_payment,  pattern=r"^topup_pay_(trc20|bep20)_\d+(\.\d+)?$"))
    # custom amount entry-point fallback (also handled inside custom_topup_conv)
    app.add_handler(CallbackQueryHandler(ask_custom_topup,        pattern=r"^topup_custom$"))

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

    # ── Product management ────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(admin_products,        pattern=r"^admin_products$"))
    app.add_handler(CallbackQueryHandler(admin_cleanup,         pattern=r"^admin_cleanup$"))
    app.add_handler(CallbackQueryHandler(admin_product_confirm, pattern=r"^admin_prod_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_product_cancel,  pattern=r"^admin_prod_cancel$"))
    app.add_handler(CallbackQueryHandler(admin_product_del,     pattern=r"^admin_prod_del_\d+$"))
    # DB product edit menu (non-conv — just shows field buttons)
    app.add_handler(CallbackQueryHandler(admin_prod_edit_menu,  pattern=r"^admin_prod_edit_\d+$"))
    # Photo management
    app.add_handler(CallbackQueryHandler(admin_static_photos,   pattern=r"^admin_static_photos$"))
    # admin_prod_photo_menu is the entry point of set_photo_conv (registered above)
    # admin_photo_delete now embeds service_id: admin_photo_delete_<sid>
    app.add_handler(CallbackQueryHandler(admin_photo_delete,    pattern=r"^admin_photo_delete_.+$"))
    # Static product/method override edit (non-conv menu screens)
    app.add_handler(CallbackQueryHandler(admin_static_edit_list, pattern=r"^admin_static_edit_list$"))
    app.add_handler(CallbackQueryHandler(admin_static_edit_menu, pattern=r"^admin_sedit_.+$"))

    # ── Method management ─────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(admin_methods_menu,         pattern=r"^admin_methods$"))
    app.add_handler(CallbackQueryHandler(admin_method_confirm,       pattern=r"^admin_method_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_method_cancel,        pattern=r"^admin_method_cancel$"))
    app.add_handler(CallbackQueryHandler(admin_method_del,           pattern=r"^admin_method_del_\w+$"))

    return app


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN not configured. Check your .env file.")
    app = build_application()
    logger.info("🚀 Starting ReseliBot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
