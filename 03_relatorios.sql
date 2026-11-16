USE controle_financeiro;

-- Run `python -m financial_analytics.cli init` before these v2 reports.
-- Monthly cash flow, zero-filled calendar, cumulative balance and period comparison.
SELECT * FROM v_monthly_summary ORDER BY month;

-- JOIN, GROUP BY, HAVING: categories with meaningful expense totals.
SELECT c.name AS category, COUNT(*) AS transaction_count, SUM(t.amount) AS expenses
FROM transactions t
JOIN categories c ON c.id = t.category_id
WHERE c.kind = 'expense'
GROUP BY c.id, c.name
HAVING SUM(t.amount) > 500
ORDER BY expenses DESC;

-- Deterministic running cash balance (date ties broken by primary key).
SELECT id, transaction_date, description, category, account, signed_amount,
       SUM(signed_amount) OVER (
           ORDER BY transaction_date, id ROWS UNBOUNDED PRECEDING
       ) AS cumulative_balance
FROM v_transaction_details ORDER BY transaction_date, id;

-- CTE and window ranking: expense share by category.
WITH expense_totals AS (
    SELECT category, SUM(amount) AS expenses
    FROM v_transaction_details WHERE kind = 'expense' GROUP BY category
)
SELECT category, expenses,
       DENSE_RANK() OVER (ORDER BY expenses DESC) AS expense_rank,
       ROUND(100 * expenses / NULLIF(SUM(expenses) OVER (), 0), 2) AS share_percent
FROM expense_totals ORDER BY expense_rank, category;

-- Conditional aggregation: account cash movements, all amounts in BRL.
SELECT account,
       SUM(CASE WHEN kind = 'income' THEN amount ELSE 0 END) AS income,
       SUM(CASE WHEN kind = 'expense' THEN amount ELSE 0 END) AS expenses,
       SUM(signed_amount) AS net
FROM v_transaction_details GROUP BY account ORDER BY account;
