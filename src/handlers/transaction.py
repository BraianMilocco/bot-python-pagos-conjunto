"""
Flujo unificado para cargar transacciones:
income / expense_personal / expense_shared / saving
"""
from datetime import date
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from src import keyboards
from src.config import BRAIAN_TELEGRAM_ID, CONSTANZA_TELEGRAM_ID, CATEGORIES
from src.models import get_user_by_telegram_id, insert_transaction

# Estados de la conversación
(
    ST_CATEGORY,
    ST_AMOUNT,
    ST_CURRENCY,
    ST_DESCRIPTION,
    ST_DATE,
    ST_DATE_INPUT,
    ST_PAID_BY,
    ST_FOR_USER,
    ST_CONFIRM,
) = range(9)

LABEL = {
    "income": "💰 Ingreso",
    "expense_personal": "💸 Gasto Personal",
    "expense_shared": "🏠 Gasto Compartido",
    "saving": "🏦 Ahorro",
}

CAT_LABEL = {
    code: label
    for cats in CATEGORIES.values()
    for code, label in cats
}

CURRENCY_SYMBOL = {"ARS": "$", "USD": "u$d", "USDT": "USDT"}


async def start_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    tx_type = query.data.replace("menu_", "")  # income / expense_personal / expense_shared / saving
    context.user_data["tx_type"] = tx_type

    # Determinar scope y type para la DB
    if tx_type == "income":
        context.user_data["db_type"] = "income"
        context.user_data["db_scope"] = "personal"
    elif tx_type == "expense_personal":
        context.user_data["db_type"] = "expense"
        context.user_data["db_scope"] = "personal"
    elif tx_type == "expense_shared":
        context.user_data["db_type"] = "expense"
        context.user_data["db_scope"] = "shared"
    elif tx_type == "saving":
        context.user_data["db_type"] = "saving"
        context.user_data["db_scope"] = "personal"

    label = LABEL[tx_type]
    await query.edit_message_text(
        f"{label}\n\nElegí la categoría:",
        reply_markup=keyboards.category_keyboard(tx_type),
    )
    return ST_CATEGORY


async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    category = query.data.replace("cat_", "")
    context.user_data["category"] = category

    await query.edit_message_text(
        f"Categoría: *{CAT_LABEL.get(category, category)}*\n\nIngresá el monto (ej: 1500 o 1500.50):",
        parse_mode="Markdown",
    )
    return ST_AMOUNT


async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Monto inválido. Ingresá un número positivo (ej: 1500 o 99.99):")
        return ST_AMOUNT

    context.user_data["amount"] = amount
    await update.message.reply_text(
        f"Monto: *{amount:,.2f}*\n\nElegí la moneda:",
        parse_mode="Markdown",
        reply_markup=keyboards.currency_keyboard(),
    )
    return ST_CURRENCY


async def handle_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    currency = query.data.replace("cur_", "")
    context.user_data["currency"] = currency

    await query.edit_message_text(
        f"Moneda: *{currency}*\n\nAgregá una descripción o saltéala:",
        parse_mode="Markdown",
        reply_markup=keyboards.description_keyboard(),
    )
    return ST_DESCRIPTION


async def handle_description_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["description"] = None
    await query.edit_message_text(
        "¿Cuándo fue?",
        reply_markup=keyboards.date_keyboard(),
    )
    return ST_DATE


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["description"] = text

    await update.message.reply_text(
        "¿Cuándo fue?",
        reply_markup=keyboards.date_keyboard(),
    )
    return ST_DATE


async def handle_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "date_today":
        context.user_data["date"] = date.today()
        return await _next_after_date(query, context)
    else:
        await query.edit_message_text("Ingresá la fecha en formato DD/MM/YYYY:")
        return ST_DATE_INPUT


async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        from datetime import datetime
        parsed = datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        await update.message.reply_text("Formato inválido. Usá DD/MM/YYYY (ej: 15/02/2026):")
        return ST_DATE_INPUT

    context.user_data["date"] = parsed

    # Necesitamos enviar el siguiente mensaje - usamos send en vez de edit
    if context.user_data["db_scope"] == "shared":
        await update.message.reply_text(
            "¿Quién pagó este gasto?",
            reply_markup=keyboards.paid_by_keyboard(BRAIAN_TELEGRAM_ID, CONSTANZA_TELEGRAM_ID),
        )
        return ST_PAID_BY
    else:
        return await _go_to_confirm(update.message, context)


async def _next_after_date(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Después de elegir fecha, sigue paid_by (shared) o confirmación."""
    if context.user_data["db_scope"] == "shared":
        await message_or_query.edit_message_text(
            "¿Quién pagó este gasto?",
            reply_markup=keyboards.paid_by_keyboard(BRAIAN_TELEGRAM_ID, CONSTANZA_TELEGRAM_ID),
        )
        return ST_PAID_BY
    else:
        # Para income, expense_personal y saving, paid_by = quien carga
        user = get_user_by_telegram_id(message_or_query.from_user.id)
        context.user_data["paid_by"] = user["id"]
        context.user_data["for_user"] = None
        await message_or_query.edit_message_text(
            _build_summary(context),
            parse_mode="Markdown",
            reply_markup=keyboards.confirm_keyboard(),
        )
        return ST_CONFIRM


async def handle_paid_by(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    paid_by_telegram_id = int(query.data.replace("paid_", ""))
    user = get_user_by_telegram_id(paid_by_telegram_id)
    context.user_data["paid_by"] = user["id"]

    await query.edit_message_text(
        "¿Para quién aplica este gasto?",
        reply_markup=keyboards.for_user_keyboard(BRAIAN_TELEGRAM_ID, CONSTANZA_TELEGRAM_ID),
    )
    return ST_FOR_USER


async def handle_for_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "for_both":
        context.user_data["for_user"] = None
    else:
        for_telegram_id = int(query.data.replace("for_", ""))
        user = get_user_by_telegram_id(for_telegram_id)
        context.user_data["for_user"] = user["id"]

    await query.edit_message_text(
        _build_summary(context),
        parse_mode="Markdown",
        reply_markup=keyboards.confirm_keyboard(),
    )
    return ST_CONFIRM


async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    loader = get_user_by_telegram_id(query.from_user.id)
    ud = context.user_data

    insert_transaction(
        user_id=loader["id"],
        type_=ud["db_type"],
        scope=ud["db_scope"],
        category=ud["category"],
        amount=ud["amount"],
        currency=ud["currency"],
        description=ud.get("description"),
        paid_by=ud["paid_by"],
        for_user=ud.get("for_user"),
        date_=ud["date"],
    )

    await query.edit_message_text(
        "✅ *¡Cargado con éxito!*\n\n" + _build_summary(context),
        parse_mode="Markdown",
        reply_markup=keyboards.back_to_main(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "❌ Cancelado.",
            reply_markup=keyboards.back_to_main(),
        )
    context.user_data.clear()
    return ConversationHandler.END


def _build_summary(context: ContextTypes.DEFAULT_TYPE) -> str:
    ud = context.user_data
    tx_type = ud.get("tx_type", "")
    label = LABEL.get(tx_type, tx_type)
    category = CAT_LABEL.get(ud.get("category", ""), ud.get("category", ""))
    amount = ud.get("amount", 0)
    currency = ud.get("currency", "")
    desc = ud.get("description") or "_sin descripción_"
    date_str = ud.get("date", date.today()).strftime("%d/%m/%Y")

    lines = [
        f"*Resumen:*",
        f"Tipo: {label}",
        f"Categoría: {category}",
        f"Monto: {amount:,.2f} {currency}",
        f"Descripción: {desc}",
        f"Fecha: {date_str}",
    ]

    if ud.get("db_scope") == "shared":
        # Buscar nombre del paid_by
        from src.database import get_connection
        conn = get_connection()
        paid_row = conn.execute("SELECT name FROM users WHERE id = %s", (ud.get("paid_by"),)).fetchone()
        conn.close()
        paid_name = paid_row["name"] if paid_row else "?"
        lines.append(f"Pagó: {paid_name}")

        for_user = ud.get("for_user")
        if for_user is None:
            lines.append("Aplica: Para los dos")
        else:
            conn = get_connection()
            for_row = conn.execute("SELECT name FROM users WHERE id = %s", (for_user,)).fetchone()
            conn.close()
            for_name = for_row["name"] if for_row else "?"
            lines.append(f"Aplica: Solo {for_name}")

    return "\n".join(lines)


async def _go_to_confirm(message, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = get_user_by_telegram_id(message.from_user.id)
    context.user_data["paid_by"] = user["id"]
    context.user_data["for_user"] = None
    await message.reply_text(
        _build_summary(context),
        parse_mode="Markdown",
        reply_markup=keyboards.confirm_keyboard(),
    )
    return ST_CONFIRM


def build_transaction_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_transaction, pattern="^menu_(income|expense_personal|expense_shared|saving)$"),
        ],
        states={
            ST_CATEGORY: [CallbackQueryHandler(handle_category, pattern="^cat_")],
            ST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            ST_CURRENCY: [CallbackQueryHandler(handle_currency, pattern="^cur_")],
            ST_DESCRIPTION: [
                CallbackQueryHandler(handle_description_skip, pattern="^desc_skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description),
            ],
            ST_DATE: [CallbackQueryHandler(handle_date_choice, pattern="^date_")],
            ST_DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_input)],
            ST_PAID_BY: [CallbackQueryHandler(handle_paid_by, pattern="^paid_")],
            ST_FOR_USER: [CallbackQueryHandler(handle_for_user, pattern="^for_")],
            ST_CONFIRM: [CallbackQueryHandler(handle_confirm, pattern="^confirm_yes$")],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")],
        per_message=False,
    )
