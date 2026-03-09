from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.config import CATEGORIES, CURRENCIES


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Ingreso", callback_data="menu_income"),
            InlineKeyboardButton("💸 Gasto Personal", callback_data="menu_expense_personal"),
        ],
        [
            InlineKeyboardButton("🏠 Gasto Compartido", callback_data="menu_expense_shared"),
            InlineKeyboardButton("🏦 Ahorro", callback_data="menu_saving"),
        ],
        [
            InlineKeyboardButton("📊 Reportes", callback_data="menu_reports"),
            InlineKeyboardButton("🕐 Últimas cargas", callback_data="menu_recent"),
        ],
        [
            InlineKeyboardButton("🧾 Pendientes", callback_data="menu_pending"),
        ],
    ])


def category_keyboard(type_key: str) -> InlineKeyboardMarkup:
    cats = CATEGORIES[type_key]
    rows = []
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(cats[i][1], callback_data=f"cat_{cats[i][0]}")]
        if i + 1 < len(cats):
            row.append(InlineKeyboardButton(cats[i + 1][1], callback_data=f"cat_{cats[i + 1][0]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(c, callback_data=f"cur_{c}") for c in CURRENCIES],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ])


def date_keyboard() -> InlineKeyboardMarkup:
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📅 Hoy ({today})", callback_data="date_today"),
            InlineKeyboardButton("📆 Otra fecha", callback_data="date_other"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ])


def paid_by_keyboard(braian_id: int, constanza_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Braian pagó", callback_data=f"paid_{braian_id}"),
            InlineKeyboardButton("Constanza pagó", callback_data=f"paid_{constanza_id}"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ])


def for_user_keyboard(braian_id: int, constanza_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Para los dos", callback_data="for_both"),
            InlineKeyboardButton("Solo Braian", callback_data=f"for_{braian_id}"),
            InlineKeyboardButton("Solo Constanza", callback_data=f"for_{constanza_id}"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ])


def description_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Omitir descripción", callback_data="desc_skip")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ]
    ])


def reports_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Este mes", callback_data="report_current_month"),
            InlineKeyboardButton("📅 Mes anterior", callback_data="report_last_month"),
        ],
        [InlineKeyboardButton("📆 Rango personalizado", callback_data="report_range")],
        [InlineKeyboardButton("🔙 Menú principal", callback_data="back_main")],
    ])


def back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Menú principal", callback_data="back_main")]
    ])


def pending_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Crear pendiente", callback_data="pend_create"),
            InlineKeyboardButton("📋 Ver pendientes", callback_data="pend_list"),
        ],
        [
            InlineKeyboardButton("✅ Ver pagados", callback_data="pend_list_paid"),
        ],
        [InlineKeyboardButton("🔙 Menú principal", callback_data="back_main")],
    ])


def pending_scope_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Compartido", callback_data="pend_scope_shared"),
            InlineKeyboardButton("👤 Personal", callback_data="pend_scope_personal"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="pend_cancel")],
    ])


def pending_list_keyboard(expenses: list, show_paid: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for exp in expenses:
        paid = exp["paid_amount"]
        total = exp["total_amount"]
        currency = exp["currency"]
        status_icon = "✅" if exp["status"] == "paid" else ("🔶" if exp["status"] == "partial" else "🔴")
        label = f"{status_icon} {exp['description']} ({paid:,.0f}/{total:,.0f} {currency})"
        rows.append([InlineKeyboardButton(label, callback_data=f"pend_detail_{exp['id']}")])
    back_cb = "pend_list_paid" if show_paid else "pend_list"
    rows.append([InlineKeyboardButton("🔙 Volver", callback_data="pend_back_menu")])
    return InlineKeyboardMarkup(rows)


def pending_detail_keyboard(expense_id: int, is_paid: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if not is_paid:
        rows.append([InlineKeyboardButton("💳 Registrar pago", callback_data=f"pend_pay_{expense_id}")])
    rows.append([InlineKeyboardButton("🔙 Volver a lista", callback_data="pend_list")])
    rows.append([InlineKeyboardButton("🏠 Menú principal", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def pending_pay_who_keyboard(braian_id: int, constanza_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Braian pagó", callback_data=f"pend_who_{braian_id}"),
            InlineKeyboardButton("Constanza pagó", callback_data=f"pend_who_{constanza_id}"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="pend_cancel")],
    ])
