create DATABASE if NOT EXISTS controle_financeiro;
use controle_financeiro;
create TABLE if NOT EXISTS transacoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    descricao VARCHAR(100) ,
    tipo VARCHAR(20),
    valor DECIMAL(10, 2),
    data_transacao DATE
);