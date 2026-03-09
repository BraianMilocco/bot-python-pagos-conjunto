from datetime import date, timedelta
import calendar
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from src import keyboards
from src.models import get_report_summary, get_last_transactions, get_pending_summary

ST_REPORT_RANGE_FROM, ST_REPORT_RANGE_TO = range(10, 12)

CATEGORY_LABELS = {
    "sueldo": "Sueldo", "freelance": "Freelance", "otro_ingreso": "Otro",
    "gustos": "Gustos/Innec.", "salud": "Salud", "ropa": "Ropa",
    "educacion": "Educacion", "otro_personal": "Otro Personal",
    "comida": "Comida/Super", "impuestos": "Impuestos/Serv.",
    "streaming": "Streaming", "alquiler": "Alquiler/Viv.",
    "transporte": "Transporte", "otro_compartido": "Otro Compart.",
    "viaje": "Viaje", "casamiento": "Casamiento",
    "fondo_emergencia": "Fondo Emerg.", "otro_ahorro": "Otro Ahorro",
}


async def show_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📊 *Reportes* — ¿qué período querés ver?",
        parse_mode="Markdown",
        reply_markup=keyboards.reports_keyboard(),
    )


async def handle_report_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    today = date.today()

    if query.data == "report_current_month":
        date_from = today.replace(day=1)
        date_to = today
        title = f"Este mes ({today.strftime('%B %Y')})"
        await _send_report(query, date_from, date_to, title)
        return ConversationHandler.END

    elif query.data == "report_last_month":
        first_this = today.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        date_from = last_month_end.replace(day=1)
        date_to = last_month_end
        title = f"Mes anterior ({last_month_end.strftime('%B %Y')})"
        await _send_report(query, date_from, date_to, title)
        return ConversationHandler.END

    elif query.data == "report_range":
        await query.edit_message_text("Ingresá la fecha de inicio (DD/MM/YYYY):")
        return ST_REPORT_RANGE_FROM


async def handle_range_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        from datetime import datetime
        context.user_data["report_from"] = datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        await update.message.reply_text("Formato inválido. Usá DD/MM/YYYY:")
        return ST_REPORT_RANGE_FROM
    await update.message.reply_text("Ingresá la fecha de fin (DD/MM/YYYY):")
    return ST_REPORT_RANGE_TO


async def handle_range_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        from datetime import datetime
        date_to = datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        await update.message.reply_text("Formato inválido. Usá DD/MM/YYYY:")
        return ST_REPORT_RANGE_TO

    date_from = context.user_data.pop("report_from")
    title = f"{date_from.strftime('%d/%m/%Y')} al {date_to.strftime('%d/%m/%Y')}"
    await _send_report_message(update.message, date_from, date_to, title)
    return ConversationHandler.END


async def _send_report(query, date_from: date, date_to: date, title: str):
    text = _build_report_text(date_from, date_to, title)
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboards.back_to_main(),
    )


async def _send_report_message(message, date_from: date, date_to: date, title: str):
    text = _build_report_text(date_from, date_to, title)
    await message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboards.back_to_main(),
    )


def _fmt(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def _build_report_text(date_from: date, date_to: date, title: str) -> str:
    data = get_report_summary(date_from, date_to)
    pending = get_pending_summary()
    lines = [f"📊 *Reporte: {title}*\n"]

    # ── INGRESOS ──────────────────────────────────────────
    lines.append("💰 *INGRESOS*")
    if data["incomes"]:
        totals: dict[str, float] = {}
        by_user: dict[str, dict[str, float]] = {}
        for row in data["incomes"]:
            name, cur, total = row["name"], row["currency"], row["total"]
            by_user.setdefault(name, {})[cur] = total
            totals[cur] = totals.get(cur, 0) + total
        for name, currencies in by_user.items():
            for cur, total in currencies.items():
                lines.append(f"  {name}: {_fmt(total, cur)}")
        lines.append("  ─────────────")
        for cur, total in totals.items():
            lines.append(f"  *Total: {_fmt(total, cur)}*")
    else:
        lines.append("  Sin ingresos registrados")

    lines.append("")

    # ── GASTOS COMPARTIDOS ────────────────────────────────
    lines.append("🏠 *GASTOS COMPARTIDOS*")

    # Combinar pagos de transacciones + pagos sobre pendientes compartidos
    combined_paid: dict[str, dict[str, float]] = {}
    for row in data["shared"]:
        name = row["paid_by_name"] or "Desconocido"
        combined_paid.setdefault(name, {})[row["currency"]] = (
            combined_paid.get(name, {}).get(row["currency"], 0) + row["total"]
        )
    for row in pending["shared_payments_by_payer"]:
        name = row["paid_by_name"]
        cur = row["currency"]
        combined_paid.setdefault(name, {})[cur] = (
            combined_paid.get(name, {}).get(cur, 0) + row["total"]
        )

    if combined_paid:
        for name, currencies in combined_paid.items():
            for cur, total in currencies.items():
                lines.append(f"  {name} pagó: {_fmt(total, cur)}")

        # Balance por moneda sobre totales combinados
        all_currencies = {cur for currencies in combined_paid.values() for cur in currencies}
        for cur in all_currencies:
            amounts = {name: currencies.get(cur, 0) for name, currencies in combined_paid.items() if cur in currencies}
            names = list(amounts.keys())
            if len(names) == 2:
                diff = amounts[names[0]] - amounts[names[1]]
                if abs(diff) > 0.01:
                    debtor = names[1] if diff > 0 else names[0]
                    creditor = names[0] if diff > 0 else names[1]
                    lines.append(f"  ⚖️ {debtor} le debe {_fmt(abs(diff), cur)} a {creditor}")

        # Top categorías (solo transacciones)
        if data["shared_categories"]:
            lines.append("  *Por categoría:*")
            for row in data["shared_categories"][:5]:
                cat = CATEGORY_LABELS.get(row["category"], row["category"])
                lines.append(f"    • {cat}: {_fmt(row['total'], row['currency'])}")
    else:
        lines.append("  Sin gastos compartidos")

    # Deuda compartida pendiente de pago
    if pending["shared_outstanding"]:
        lines.append("  *Comprometido sin saldar:*")
        for row in pending["shared_outstanding"]:
            remaining = row["total_committed"] - row["total_paid"]
            lines.append(f"    ⏳ Resta pagar: {_fmt(remaining, row['currency'])}")

    lines.append("")

    # ── GASTOS PERSONALES ─────────────────────────────────
    lines.append("💸 *GASTOS PERSONALES*")
    if data["personal"]:
        for row in data["personal"]:
            lines.append(f"  {row['name']}: {_fmt(row['total'], row['currency'])}")

        lines.append("  *Top categorías por persona:*")
        shown: dict[str, int] = {}
        for row in data["personal_categories"]:
            name = row["name"]
            shown[name] = shown.get(name, 0) + 1
            if shown[name] <= 3:
                cat = CATEGORY_LABELS.get(row["category"], row["category"])
                lines.append(f"    {name} - {cat}: {_fmt(row['total'], row['currency'])}")
    else:
        lines.append("  Sin gastos personales")

    lines.append("")

    # ── AHORROS ───────────────────────────────────────────
    lines.append("🏦 *AHORROS*")
    if data["savings"]:
        totals: dict[str, float] = {}
        for row in data["savings"]:
            cat = CATEGORY_LABELS.get(row["category"], row["category"])
            lines.append(f"  {cat}: {_fmt(row['total'], row['currency'])}")
            totals[row["currency"]] = totals.get(row["currency"], 0) + row["total"]
        lines.append("  ─────────────")
        for cur, total in totals.items():
            lines.append(f"  *Total ahorrado: {_fmt(total, cur)}*")
    else:
        lines.append("  Sin ahorros registrados")

    # ── PENDIENTES ────────────────────────────────────────
    if pending["items"]:
        lines.append("")
        lines.append("🧾 *PENDIENTES DE PAGO*")
        status_icon = {"pending": "🔴", "partial": "🔶"}
        for item in pending["items"]:
            icon = status_icon.get(item["status"], "•")
            remaining = item["total_amount"] - item["paid_amount"]
            scope_tag = "[compartido]" if item["scope"] == "shared" else "[personal]"
            cat = CATEGORY_LABELS.get(item["category"], item["category"])
            lines.append(
                f"  {icon} *{item['description']}* {scope_tag}\n"
                f"     {cat} · Total: {_fmt(item['total_amount'], item['currency'])}\n"
                f"     Pagado: {_fmt(item['paid_amount'], item['currency'])} · "
                f"*Resta: {_fmt(remaining, item['currency'])}*"
            )

    return "\n".join(lines)


async def show_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    rows = get_last_transactions(5)
    if not rows:
        await query.edit_message_text(
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

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboards.back_to_main(),
    )


def build_reports_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_report_choice, pattern="^report_(current_month|last_month|range)$"),
        ],
        states={
            ST_REPORT_RANGE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_range_from)],
            ST_REPORT_RANGE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_range_to)],
        },
        fallbacks=[CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern="^cancel$")],
        per_message=False,
    )
