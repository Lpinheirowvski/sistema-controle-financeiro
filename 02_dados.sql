-- Legacy examples only. Re-running this script preserves existing rows without adding copies.
USE controle_financeiro;
INSERT INTO transacoes (descricao, tipo, valor, data_transacao)
SELECT seed.descricao, seed.tipo, seed.valor, seed.data_transacao
FROM (
    SELECT 'venda notebook' AS descricao, 'receita' AS tipo, 2500.00 AS valor,
           CAST('2026-10-20' AS DATE) AS data_transacao
    UNION ALL SELECT 'conta de luz', 'despesa', 350.00, '2026-10-21'
    UNION ALL SELECT 'manutencao de computador', 'receita', 800.00, '2026-10-22'
    UNION ALL SELECT 'aluguel', 'despesa', 1200.00, '2026-10-23'
    UNION ALL SELECT 'venda de monitor', 'receita', 950.00, '2026-10-24'
) seed
WHERE NOT EXISTS (
    SELECT 1 FROM transacoes t
    WHERE t.descricao = seed.descricao AND t.tipo = seed.tipo
      AND t.valor = seed.valor AND t.data_transacao = seed.data_transacao
);
