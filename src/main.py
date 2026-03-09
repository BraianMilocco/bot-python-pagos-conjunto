import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from src.config import BOT_TOKEN, ALLOWED_IDS, USER_NAMES
from src.database import init_db
from src import keyboards
from src.handlers.transaction import build_transaction_handler
from src.handlers.reports import build_reports_handler, show_reports_menu, show_recent
from src.handlers.pending import build_pending_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in ALLOWED_IDS:
        if update.message:
            await update.message.reply_text("No tenés acceso a este bot.")
        elif update.callback_query:
            await update.callback_query.answer("No tenés acceso.", show_alert=True)
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    name = USER_NAMES.get(update.effective_user.id, "")
    await update.message.reply_text(
        f"Hola {name}! Bienvenido al bot de finanzas 💵\n\n"
        "¿Qué querés cargar?",
        reply_markup=keyboards.main_menu(),
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el menú principal."""
    if not await auth_middleware(update, context):
        return
    name = USER_NAMES.get(update.effective_user.id, "")
    await update.message.reply_text(
        f"Hola {name}! ¿Qué querés hacer?",
        reply_markup=keyboards.main_menu(),
    )


async def cmd_pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acceso directo a la sección de pendientes."""
    if not await auth_middleware(update, context):
        return
    await update.message.reply_text(
        "🧾 *Gastos Pendientes*\n\n¿Qué querés hacer?",
        parse_mode="Markdown",
        reply_markup=keyboards.pending_menu(),
    )


async def cmd_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acceso directo al menú de reportes."""
    if not await auth_middleware(update, context):
        return
    await update.message.reply_text(
        "📊 *Reportes* — ¿qué período querés ver?",
        parse_mode="Markdown",
        reply_markup=keyboards.reports_keyboard(),
    )


async def cmd_recientes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra las últimas 5 transacciones."""
    if not await auth_middleware(update, context):
        return
    from src.models import get_last_transactions
    rows = get_last_transactions(5)
    if not rows:
        await update.message.reply_text(
            "No hay transacciones cargadas aún.",
            reply_markup=keyboards.back_to_main(),
        )
        return
    lines = ["🕐 *Últimas 5 cargas:*\n"]
    type_icon = {"income": "💰", "expense": "💸", "saving": "🏦"}
    for row in rows:
        icon = type_icon.get(row["type"], "•")
        scope = " [compartido]" if row["scope"] == "shared" else ""
        desc = f" — {row['description']}" if row["description"] else ""
        lines.append(
            f"{icon} *{row['paid_by_name'] or row['user_name']}*{scope}: "
            f"{row['amount']:,.2f} {row['currency']}{desc} "
            f"({row['date']})"
        )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboards.back_to_main(),
    )


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista de comandos disponibles."""
    if not await auth_middleware(update, context):
        return
    await update.message.reply_text(
        "📋 *Comandos disponibles:*\n\n"
        "/start o /menu — Menú principal\n"
        "/pendientes — Ver y gestionar gastos pendientes\n"
        "/reporte — Ver reportes de gastos\n"
        "/recientes — Últimas 5 transacciones\n"
        "/ayuda — Esta ayuda\n\n"
        "También podés usar los botones del menú 👇",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu(),
    )


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    name = USER_NAMES.get(query.from_user.id, "")
    await query.edit_message_text(
        f"Hola {name}! ¿Qué querés hacer?",
        reply_markup=keyboards.main_menu(),
    )


async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "¿Qué querés hacer?",
        reply_markup=keyboards.main_menu(),
    )


async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cualquier texto suelto fuera de un flujo activo muestra el menú."""
    if not await auth_middleware(update, context):
        return
    name = USER_NAMES.get(update.effective_user.id, "")
    await update.message.reply_text(
        f"Hola {name}! ¿Qué querés hacer?",
        reply_markup=keyboards.main_menu(),
    )


def main() -> None:
    init_db()
    logger.info("Base de datos inicializada")

    app = Application.builder().token(BOT_TOKEN).build()

    # Middleware de autorización para mensajes de texto
    async def authed_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await auth_middleware(update, context)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("pendientes", cmd_pendientes))
    app.add_handler(CommandHandler("reporte", cmd_reporte))
    app.add_handler(CommandHandler("recientes", cmd_recientes))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(build_transaction_handler())
    app.add_handler(build_reports_handler())
    app.add_handler(build_pending_handler())
    app.add_handler(CallbackQueryHandler(show_reports_menu, pattern="^menu_reports$"))
    app.add_handler(CallbackQueryHandler(show_recent, pattern="^menu_recent$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(unknown_callback))
    # Cualquier mensaje de texto fuera de un flujo activo → menú principal
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))

    logger.info("Bot iniciado")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
