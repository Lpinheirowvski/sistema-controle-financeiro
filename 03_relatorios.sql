use coontrole_financeiro;
select table_schema, TABLE_NAME from information_schema.tables where table_name = 'transacoes';
select * from transacoes;
select sum(valor) as total_receitas from transacoes where tipo ='receita';
select sum(valor) AS total_despesas from transacoes WHERE TIPO ='despesa';
select sum(CASE when tipo = 'receita' then valor else 0 end) -
       sum(case when tipo = 'despesa' then valor else 0 end) as saldo
from transacoes; 
select count(*) as total_transacoes from transacoes;
select * from transacoes where valor >500;
select * from transacoes where valor <1000;
select * from transacoes order by valor DESC;
select * from transacoes order by valor ASC;
select * from transacoes where tipo = 'despesa' order by valor DESC;
select * from transacoes where tipo = 'receita' order by valor ASC;
select * from transacoes;
select
    tipo,
    sum(valor) as total
from transacoes
group by tipo;
select * from transacoes where id = 3;
select
    tipo,
    count(*) as quantidade,
    sum(valor) as total
from transacoes
group by tipo;
select
    tipo,
    count(*) as quantidade,
    sum(valor) as total
from transacoes
where data_transacao BETWEEN '2026-10-01' AND '2026-10-31'
group by tipo;
select count(*) as quantidade from transacoes where tipo = 'receita';