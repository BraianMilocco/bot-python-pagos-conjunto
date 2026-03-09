CREATE TABLE IF NOT EXISTS pending_expenses (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'shared' CHECK(scope IN ('personal', 'shared')),
    total_amount NUMERIC NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ARS' CHECK(currency IN ('ARS', 'USD', 'USDT')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'partial', 'paid')),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pending_payments (
    id SERIAL PRIMARY KEY,
    pending_expense_id INTEGER NOT NULL REFERENCES pending_expenses(id),
    paid_by INTEGER NOT NULL REFERENCES users(id),
    amount NUMERIC NOT NULL,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_expenses(status);
CREATE INDEX IF NOT EXISTS idx_pending_payments_expense ON pending_payments(pending_expense_id);
