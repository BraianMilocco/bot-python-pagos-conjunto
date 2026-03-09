"""
Flujo para gestionar gastos pendientes de pago.
Permite crear un gasto pendiente y luego registrar pagos parciales o totales.
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
from src.models import (
    get_user_by_telegram_id,
    insert_pending_expense,
    get_pending_expenses,
    get_pending_expense_by_id,
    get_pending_payments,
    insert_pending_payment,
)

# Estados de la conversación
(
    PEND_MENU,
    PEND_SCOPE,
    PEND_CATEGORY,
    PEND_AMOUNT,
    PEND_CURRENCY,
    PEND_DESCRIPTION,
    PEND_CONFIRM,
    PEND_LIST,
    PEND_DETAIL,
    PEND_PAY_WHO,
    PEND_PAY_AMOUNT,
    PEND_PAY_CONFIRM,
) = range(12)

CAT_LABEL = {
    code: label
    for cats in CATEGORIES.values()
    for code, label in cats
}

STATUS_LABEL = {
    "pending": "🔴 Pendiente",
    "partial": "🔶 Pago parcial",
    "paid": "✅ Pagado",
}


# ─── Menú principal de pendientes ──────────────────────────────────────────────

async def show_pending_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🧾 *Gastos Pendientes*\n\n"
        "Aquí podés cargar gastos que aún no fueron pagados y registrar pagos a medida que se van haciendo.\n\n"
        "¿Qué querés hacer?",
        parse_mode="Markdown",
        reply_markup=keyboards.pending_menu(),
    )
    return PEND_MENU


# ─── Crear pendiente ────────────────────────────────────────────────────────────

async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data["flow"] = "create"
    await query.edit_message_text(
        "➕ *Nuevo gasto pendiente*\n\n¿Es un gasto compartido o personal?",
        parse_mode="Markdown",
        reply_markup=keyboards.pending_scope_keyboard(),
    )
    return PEND_SCOPE


async def handle_scope(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    scope = query.data.replace("pend_scope_", "")  # shared / personal
    context.user_data["scope"] = scope

    type_key = "expense_shared" if scope == "shared" else "expense_personal"
    context.user_data["type_key"] = type_key

    scope_label = "🏠 Compartido" if scope == "shared" else "👤 Personal"
    await query.edit_message_text(
        f"{scope_label}\n\nElegí la categoría:",
        reply_markup=keyboards.category_keyboard(type_key),
    )
    return PEND_CATEGORY


async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    category = query.data.replace("cat_", "")
    context.user_data["category"] = category

    await query.edit_message_text(
        f"Categoría: *{CAT_LABEL.get(category, category)}*\n\n"
        "Ingresá el monto total del gasto (ej: 120000 o 1500.50):",
        parse_mode="Markdown",
    )
    return PEND_AMOUNT


async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Monto inválido. Ingresá un número positivo (ej: 120000 o 99.99):")
        return PEND_AMOUNT

    context.user_data["amount"] = amount
    await update.message.reply_text(
        f"Monto: *{amount:,.2f}*\n\nElegí la moneda:",
        parse_mode="Markdown",
        reply_markup=keyboards.currency_keyboard(),
    )
    return PEND_CURRENCY


async def handle_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    currency = query.data.replace("cur_", "")
    context.user_data["currency"] = currency

    await query.edit_message_text(
        f"Moneda: *{currency}*\n\n"
        "Escribí un nombre o descripción para este gasto (ej: _Expensas Marzo_, _Internet_, _Gas_):",
        parse_mode="Markdown",
    )
    return PEND_DESCRIPTION


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Escribí un nombre para identificar este gasto:")
        return PEND_DESCRIPTION

    context.user_data["description"] = text
    await update.message.reply_text(
        _build_create_summary(context),
        parse_mode="Markdown",
        reply_markup=_confirm_create_keyboard(),
    )
    return PEND_CONFIRM


async def handle_confirm_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    creator = get_user_by_telegram_id(query.from_user.id)
    ud = context.user_data

    expense_id = insert_pending_expense(
        description=ud["description"],
        category=ud["category"],
        scope=ud["scope"],
        total_amount=ud["amount"],
        currency=ud["currency"],
        created_by=creator["id"],
    )

    await query.edit_message_text(
        f"✅ *Gasto pendiente creado!*\n\n{_build_create_summary(context)}",
        parse_mode="Markdown",
        reply_markup=keyboards.back_to_main(),
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─── Ver pendientes ─────────────────────────────────────────────────────────────

async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    show_paid = query.data == "pend_list_paid"
    context.user_data["show_paid"] = show_paid

    if show_paid:
        expenses = get_pending_expenses(status_filter="paid")
        title = "✅ *Gastos pagados*"
        empty_msg = "No hay gastos pagados aún."
    else:
        expenses = get_pending_expenses()
        title = "📋 *Gastos pendientes*"
        empty_msg = "No hay gastos pendientes. ¡Todo al día! ✅"

    if not expenses:
        await query.edit_message_text(
            f"{title}\n\n{empty_msg}",
            parse_mode="Markdown",
            reply_markup=keyboards.pending_menu(),
        )
        return PEND_MENU

    await query.edit_message_text(
        f"{title}\n\nTocá uno para ver el detalle:",
        parse_mode="Markdown",
        reply_markup=keyboards.pending_list_keyboard(expenses, show_paid=show_paid),
    )
    return PEND_LIST


async def show_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    expense_id = int(query.data.replace("pend_detail_", ""))
    context.user_data["expense_id"] = expense_id

    expense = get_pending_expense_by_id(expense_id)
    if not expense:
        await query.answer("Gasto no encontrado.", show_alert=True)
        return PEND_LIST

    payments = get_pending_payments(expense_id)
    text = _build_detail_text(expense, payments)

    is_paid = expense["status"] == "paid"
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboards.pending_detail_keyboard(expense_id, is_paid=is_paid),
    )
    return PEND_DETAIL


# ─── Registrar pago ─────────────────────────────────────────────────────────────

async def start_pay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    expense_id = int(query.data.replace("pend_pay_", ""))
    context.user_data["expense_id"] = expense_id

    expense = get_pending_expense_by_id(expense_id)
    remaining = expense["total_amount"] - expense["paid_amount"]

    await query.edit_message_text(
        f"💳 *Registrar pago*\n\n"
        f"*{expense['description']}*\n"
        f"Restante: {remaining:,.2f} {expense['currency']}\n\n"
        "¿Quién pagó?",
        parse_mode="Markdown",
        reply_markup=keyboards.pending_pay_who_keyboard(BRAIAN_TELEGRAM_ID, CONSTANZA_TELEGRAM_ID),
    )
    return PEND_PAY_WHO


async def handle_pay_who(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    payer_telegram_id = int(query.data.replace("pend_who_", ""))
    payer = get_user_by_telegram_id(payer_telegram_id)
    context.user_data["payer_id"] = payer["id"]
    context.user_data["payer_name"] = payer["name"]

    expense = get_pending_expense_by_id(context.user_data["expense_id"])
    remaining = expense["total_amount"] - expense["paid_amount"]

    await query.edit_message_text(
        f"Pagó: *{payer['name']}*\n\n"
        f"Restante a pagar: *{remaining:,.2f} {expense['currency']}*\n\n"
        "¿Cuánto pagó? (ingresá el monto):",
        parse_mode="Markdown",
    )
    return PEND_PAY_AMOUNT


async def handle_pay_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Monto inválido. Ingresá un número positivo:")
        return PEND_PAY_AMOUNT

    expense = get_pending_expense_by_id(context.user_data["expense_id"])
    remaining = expense["total_amount"] - expense["paid_amount"]

    if amount > remaining + 0.01:  # tolerancia por float
        await update.message.reply_text(
            f"El monto supera lo que resta pagar ({remaining:,.2f} {expense['currency']}).\n"
            "Ingresá un monto menor o igual al restante:"
        )
        return PEND_PAY_AMOUNT

    context.user_data["pay_amount"] = amount

    await update.message.reply_text(
        f"*Confirmar pago:*\n\n"
        f"Gasto: {expense['description']}\n"
        f"Pagó: {context.user_data['payer_name']}\n"
        f"Monto: {amount:,.2f} {expense['currency']}\n"
        f"Fecha: {date.today().strftime('%d/%m/%Y')}",
        parse_mode="Markdown",
        reply_markup=_confirm_pay_keyboard(),
    )
    return PEND_PAY_CONFIRM


async def handle_confirm_pay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    expense_id = ud["expense_id"]

    insert_pending_payment(
        pending_expense_id=expense_id,
        paid_by=ud["payer_id"],
        amount=ud["pay_amount"],
        date_=date.today(),
    )

    # Leer estado actualizado
    expense = get_pending_expense_by_id(expense_id)
    payments = get_pending_payments(expense_id)

    status_text = STATUS_LABEL.get(expense["status"], expense["status"])
    remaining = expense["total_amount"] - expense["paid_amount"]

    msg = (
        f"✅ *Pago registrado!*\n\n"
        f"*{expense['description']}*\n"
        f"Estado: {status_text}\n"
        f"Total: {expense['total_amount']:,.2f} {expense['currency']}\n"
        f"Pagado: {expense['paid_amount']:,.2f} {expense['currency']}\n"
    )
    if expense["status"] != "paid":
        msg += f"Restante: {remaining:,.2f} {expense['currency']}\n"
    else:
        msg += "¡Gasto completamente saldado! 🎉\n"

    context.user_data.clear()
    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=keyboards.back_to_main(),
    )
    return ConversationHandler.END


# ─── Cancelar / volver ──────────────────────────────────────────────────────────

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


async def back_to_pend_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🧾 *Gastos Pendientes*\n\n¿Qué querés hacer?",
        parse_mode="Markdown",
        reply_markup=keyboards.pending_menu(),
    )
    return PEND_MENU


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _build_create_summary(context: ContextTypes.DEFAULT_TYPE) -> str:
    ud = context.user_data
    scope_label = "🏠 Compartido" if ud.get("scope") == "shared" else "👤 Personal"
    category = CAT_LABEL.get(ud.get("category", ""), ud.get("category", ""))
    return (
        f"*Resumen del gasto pendiente:*\n"
        f"Nombre: {ud.get('description', '')}\n"
        f"Categoría: {category}\n"
        f"Tipo: {scope_label}\n"
        f"Total: {ud.get('amount', 0):,.2f} {ud.get('currency', '')}"
    )


def _build_detail_text(expense, payments: list) -> str:
    status = STATUS_LABEL.get(expense["status"], expense["status"])
    paid = expense["paid_amount"]
    total = expense["total_amount"]
    remaining = total - paid
    currency = expense["currency"]
    category = CAT_LABEL.get(expense["category"], expense["category"])

    lines = [
        f"*{expense['description']}*",
        f"Estado: {status}",
        f"Categoría: {category}",
        f"Total: {total:,.2f} {currency}",
        f"Pagado: {paid:,.2f} {currency}",
    ]
    if expense["status"] != "paid":
        lines.append(f"Restante: {remaining:,.2f} {currency}")

    if payments:
        lines.append("\n*Pagos registrados:*")
        for p in payments:
            date_str = p["date"] if isinstance(p["date"], str) else p["date"]
            lines.append(f"  • {p['paid_by_name']}: {p['amount']:,.2f} {currency} ({date_str})")

    return "\n".join(lines)


def _confirm_create_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="pend_confirm_yes"),
            InlineKeyboardButton("❌ Cancelar", callback_data="pend_cancel"),
        ]
    ])


def _confirm_pay_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar pago", callback_data="pend_pay_confirm"),
            InlineKeyboardButton("❌ Cancelar", callback_data="pend_cancel"),
        ]
    ])


# ─── Builder ────────────────────────────────────────────────────────────────────

def build_pending_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_pending_menu, pattern="^menu_pending$"),
        ],
        states={
            PEND_MENU: [
                CallbackQueryHandler(start_create, pattern="^pend_create$"),
                CallbackQueryHandler(show_list, pattern="^pend_list$"),
                CallbackQueryHandler(show_list, pattern="^pend_list_paid$"),
            ],
            PEND_SCOPE: [
                CallbackQueryHandler(handle_scope, pattern="^pend_scope_"),
            ],
            PEND_CATEGORY: [
                CallbackQueryHandler(handle_category, pattern="^cat_"),
            ],
            PEND_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount),
            ],
            PEND_CURRENCY: [
                CallbackQueryHandler(handle_currency, pattern="^cur_"),
            ],
            PEND_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description),
            ],
            PEND_CONFIRM: [
                CallbackQueryHandler(handle_confirm_create, pattern="^pend_confirm_yes$"),
            ],
            PEND_LIST: [
                CallbackQueryHandler(show_detail, pattern="^pend_detail_"),
                CallbackQueryHandler(back_to_pend_menu, pattern="^pend_back_menu$"),
                CallbackQueryHandler(show_list, pattern="^pend_list$"),
                CallbackQueryHandler(show_list, pattern="^pend_list_paid$"),
            ],
            PEND_DETAIL: [
                CallbackQueryHandler(start_pay, pattern="^pend_pay_\\d+$"),
                CallbackQueryHandler(show_list, pattern="^pend_list$"),
                CallbackQueryHandler(back_to_pend_menu, pattern="^pend_back_menu$"),
            ],
            PEND_PAY_WHO: [
                CallbackQueryHandler(handle_pay_who, pattern="^pend_who_"),
            ],
            PEND_PAY_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pay_amount),
            ],
            PEND_PAY_CONFIRM: [
                CallbackQueryHandler(handle_confirm_pay, pattern="^pend_pay_confirm$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^pend_cancel$"),
            CallbackQueryHandler(show_pending_menu, pattern="^menu_pending$"),
        ],
        per_message=False,
    )
