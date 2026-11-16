-- MySQL 8.0.46. DDL is additive; legacy transacoes is never altered or dropped.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(80) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    kind VARCHAR(7) NOT NULL,
    CONSTRAINT uq_category UNIQUE (name, kind),
    CONSTRAINT ck_category_kind CHECK (kind IN ('income', 'expense')),
    CONSTRAINT ck_category_name CHECK (CHAR_LENGTH(TRIM(name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    account_type VARCHAR(8) NOT NULL,
    CONSTRAINT ck_account_type CHECK (account_type IN ('checking', 'savings', 'cash')),
    CONSTRAINT ck_account_name CHECK (CHAR_LENGTH(TRIM(name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    description VARCHAR(200) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    transaction_date DATE NOT NULL,
    category_id INT NOT NULL,
    account_id INT NOT NULL,
    legacy_id INT UNIQUE,
    demo_key VARCHAR(50) UNIQUE,
    revision INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_transaction_category FOREIGN KEY (category_id) REFERENCES categories(id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_transaction_account FOREIGN KEY (account_id) REFERENCES accounts(id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_transaction_amount CHECK (amount > 0),
    CONSTRAINT ck_transaction_description CHECK (CHAR_LENGTH(TRIM(description)) > 0),
    CONSTRAINT ck_transaction_revision CHECK (revision > 0),
    INDEX idx_transaction_date (transaction_date, id),
    INDEX idx_transaction_category_date (category_id, transaction_date),
    INDEX idx_transaction_account_date (account_id, transaction_date)
) ENGINE=InnoDB;

CREATE OR REPLACE SQL SECURITY INVOKER VIEW v_transaction_details AS
SELECT t.*, c.name AS category, c.kind, a.name AS account,
       CASE WHEN c.kind = 'income' THEN t.amount ELSE -t.amount END AS signed_amount
FROM transactions t
JOIN categories c ON c.id = t.category_id
JOIN accounts a ON a.id = t.account_id;

-- A calendar fills missing months, so LAG means previous calendar month.
CREATE OR REPLACE SQL SECURITY INVOKER VIEW v_monthly_summary AS
WITH RECURSIVE calendar AS (
    SELECT CAST(DATE_FORMAT(MIN(transaction_date), '%Y-%m-01') AS DATE) AS month,
           CAST(DATE_FORMAT(MAX(transaction_date), '%Y-%m-01') AS DATE) AS last_month
    FROM transactions HAVING MIN(transaction_date) IS NOT NULL
    UNION ALL
    SELECT DATE_ADD(month, INTERVAL 1 MONTH), last_month
    FROM calendar WHERE month < last_month
), totals AS (
    SELECT cal.month,
           COALESCE(SUM(CASE WHEN d.kind = 'income' THEN d.amount ELSE 0 END), 0) AS income,
           COALESCE(SUM(CASE WHEN d.kind = 'expense' THEN d.amount ELSE 0 END), 0) AS expenses,
           COALESCE(SUM(d.signed_amount), 0) AS net,
           COUNT(d.id) AS transaction_count
    FROM calendar cal
    LEFT JOIN v_transaction_details d
        ON d.transaction_date >= cal.month
        AND d.transaction_date < DATE_ADD(cal.month, INTERVAL 1 MONTH)
    GROUP BY cal.month
)
SELECT totals.*,
       SUM(net) OVER (ORDER BY month ROWS UNBOUNDED PRECEDING) AS cumulative_net,
       LAG(net) OVER (ORDER BY month) AS previous_net,
       net - LAG(net) OVER (ORDER BY month) AS net_change
FROM totals;
