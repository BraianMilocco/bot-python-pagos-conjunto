import psycopg2.extras
from datetime import date
from typing import Optional
from src.database import get_connection


def get_user_by_telegram_id(telegram_id: int) -> Optional[psycopg2.extras.RealDictRow]:
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE telegram_id = %s", (telegram_id,)
    ).fetchone()
    conn.close()
    return user


def insert_transaction(
    user_id: int,
    type_: str,
    scope: str,
    category: str,
    amount: float,
    currency: str,
    description: str,
    paid_by: int,
    for_user: Optional[int],
    date_: date,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO transactions
           (user_id, type, scope, category, amount, currency, description, paid_by, for_user, date)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (user_id, type_, scope, category, amount, currency, description, paid_by, for_user, date_),
    )
    tx_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return tx_id


def get_report(date_from: date, date_to: date) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT t.*, u.name as user_name,
                  pb.name as paid_by_name,
                  fu.name as for_user_name
           FROM transactions t
           JOIN users u ON t.user_id = u.id
           LEFT JOIN users pb ON t.paid_by = pb.id
           LEFT JOIN users fu ON t.for_user = fu.id
           WHERE t.date BETWEEN %s AND %s
           ORDER BY t.date DESC""",
        (date_from, date_to),
    ).fetchall()
    conn.close()
    return rows


def get_report_summary(date_from: date, date_to: date) -> dict:
    conn = get_connection()

    incomes = conn.execute(
        """SELECT u.name, t.currency, SUM(t.amount) as total
           FROM transactions t JOIN users u ON t.user_id = u.id
           WHERE t.type = 'income' AND t.date BETWEEN %s AND %s
           GROUP BY u.name, t.currency""",
        (date_from, date_to),
    ).fetchall()

    shared = conn.execute(
        """SELECT pb.name as paid_by_name, t.currency, SUM(t.amount) as total
           FROM transactions t LEFT JOIN users pb ON t.paid_by = pb.id
           WHERE t.type = 'expense' AND t.scope = 'shared' AND t.date BETWEEN %s AND %s
           GROUP BY pb.name, t.currency""",
        (date_from, date_to),
    ).fetchall()

    shared_categories = conn.execute(
        """SELECT t.category, t.currency, SUM(t.amount) as total
           FROM transactions t
           WHERE t.type = 'expense' AND t.scope = 'shared' AND t.date BETWEEN %s AND %s
           GROUP BY t.category, t.currency
           ORDER BY total DESC""",
        (date_from, date_to),
    ).fetchall()

    personal = conn.execute(
        """SELECT u.name, t.currency, SUM(t.amount) as total
           FROM transactions t JOIN users u ON t.user_id = u.id
           WHERE t.type = 'expense' AND t.scope = 'personal' AND t.date BETWEEN %s AND %s
           GROUP BY u.name, t.currency""",
        (date_from, date_to),
    ).fetchall()

    personal_categories = conn.execute(
        """SELECT u.name, t.category, t.currency, SUM(t.amount) as total
           FROM transactions t JOIN users u ON t.user_id = u.id
           WHERE t.type = 'expense' AND t.scope = 'personal' AND t.date BETWEEN %s AND %s
           GROUP BY u.name, t.category, t.currency
           ORDER BY total DESC""",
        (date_from, date_to),
    ).fetchall()

    savings = conn.execute(
        """SELECT t.category, t.currency, SUM(t.amount) as total
           FROM transactions t
           WHERE t.type = 'saving' AND t.date BETWEEN %s AND %s
           GROUP BY t.category, t.currency""",
        (date_from, date_to),
    ).fetchall()

    conn.close()
    return {
        "incomes": incomes,
        "shared": shared,
        "shared_categories": shared_categories,
        "personal": personal,
        "personal_categories": personal_categories,
        "savings": savings,
    }


def insert_pending_expense(
    description: str,
    category: str,
    scope: str,
    total_amount: float,
    currency: str,
    created_by: int,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO pending_expenses
           (description, category, scope, total_amount, currency, created_by)
           VALUES (%s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (description, category, scope, total_amount, currency, created_by),
    )
    expense_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return expense_id


def get_pending_expenses(status_filter: Optional[str] = None) -> list:
    conn = get_connection()
    if status_filter:
        rows = conn.execute(
            """SELECT pe.*, u.name as created_by_name,
                      COALESCE(SUM(pp.amount), 0) as paid_amount
               FROM pending_expenses pe
               JOIN users u ON pe.created_by = u.id
               LEFT JOIN pending_payments pp ON pp.pending_expense_id = pe.id
               WHERE pe.status = %s
               GROUP BY pe.id, u.name
               ORDER BY pe.created_at DESC""",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT pe.*, u.name as created_by_name,
                      COALESCE(SUM(pp.amount), 0) as paid_amount
               FROM pending_expenses pe
               JOIN users u ON pe.created_by = u.id
               LEFT JOIN pending_payments pp ON pp.pending_expense_id = pe.id
               WHERE pe.status IN ('pending', 'partial')
               GROUP BY pe.id, u.name
               ORDER BY pe.created_at DESC""",
        ).fetchall()
    conn.close()
    return rows


def get_pending_expense_by_id(expense_id: int) -> Optional[psycopg2.extras.RealDictRow]:
    conn = get_connection()
    row = conn.execute(
        """SELECT pe.*, u.name as created_by_name,
                  COALESCE(SUM(pp.amount), 0) as paid_amount
           FROM pending_expenses pe
           JOIN users u ON pe.created_by = u.id
           LEFT JOIN pending_payments pp ON pp.pending_expense_id = pe.id
           WHERE pe.id = %s
           GROUP BY pe.id, u.name""",
        (expense_id,),
    ).fetchone()
    conn.close()
    return row


def get_pending_payments(expense_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT pp.*, u.name as paid_by_name
           FROM pending_payments pp
           JOIN users u ON pp.paid_by = u.id
           WHERE pp.pending_expense_id = %s
           ORDER BY pp.date ASC, pp.created_at ASC""",
        (expense_id,),
    ).fetchall()
    conn.close()
    return rows


def insert_pending_payment(
    pending_expense_id: int,
    paid_by: int,
    amount: float,
    date_: date,
) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO pending_payments (pending_expense_id, paid_by, amount, date)
           VALUES (%s, %s, %s, %s)""",
        (pending_expense_id, paid_by, amount, date_),
    )
    row = conn.execute(
        """SELECT pe.total_amount, COALESCE(SUM(pp.amount), 0) as paid_amount
           FROM pending_expenses pe
           LEFT JOIN pending_payments pp ON pp.pending_expense_id = pe.id
           WHERE pe.id = %s
           GROUP BY pe.id""",
        (pending_expense_id,),
    ).fetchone()
    if row:
        paid = float(row["paid_amount"])
        total = float(row["total_amount"])
        if paid >= total:
            new_status = "paid"
        elif paid > 0:
            new_status = "partial"
        else:
            new_status = "pending"
        conn.execute(
            "UPDATE pending_expenses SET status = %s WHERE id = %s",
            (new_status, pending_expense_id),
        )
    conn.commit()
    conn.close()


def get_pending_summary() -> dict:
    conn = get_connection()

    shared_payments_by_payer = conn.execute(
        """SELECT u.name as paid_by_name, pe.currency, SUM(pp.amount) as total
           FROM pending_payments pp
           JOIN users u ON pp.paid_by = u.id
           JOIN pending_expenses pe ON pp.pending_expense_id = pe.id
           WHERE pe.scope = 'shared'
           GROUP BY u.name, pe.currency""",
    ).fetchall()

    shared_outstanding = conn.execute(
        """SELECT pe.currency,
                  SUM(pe.total_amount) as total_committed,
                  COALESCE(SUM(pp.amount), 0) as total_paid
           FROM pending_expenses pe
           LEFT JOIN pending_payments pp ON pp.pending_expense_id = pe.id
           WHERE pe.scope = 'shared' AND pe.status IN ('pending', 'partial')
           GROUP BY pe.currency""",
    ).fetchall()

    items = conn.execute(
        """SELECT pe.*, u.name as created_by_name,
                  COALESCE(SUM(pp.amount), 0) as paid_amount
           FROM pending_expenses pe
           JOIN users u ON pe.created_by = u.id
           LEFT JOIN pending_payments pp ON pp.pending_expense_id = pe.id
           WHERE pe.status IN ('pending', 'partial')
           GROUP BY pe.id, u.name
           ORDER BY pe.scope, pe.created_at DESC""",
    ).fetchall()

    conn.close()
    return {
        "shared_payments_by_payer": shared_payments_by_payer,
        "shared_outstanding": shared_outstanding,
        "items": items,
    }


def get_last_transactions(limit: int = 5) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT t.*, u.name as user_name, pb.name as paid_by_name
           FROM transactions t
           JOIN users u ON t.user_id = u.id
           LEFT JOIN users pb ON t.paid_by = pb.id
           ORDER BY t.created_at DESC LIMIT %s""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows
