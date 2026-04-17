-- Ampliar colunas que recebem dados maiores que o previsto
ALTER TABLE fracoes ALTER COLUMN turno TYPE VARCHAR(100);
ALTER TABLE fracoes ALTER COLUMN horario_inicio TYPE VARCHAR(50);
ALTER TABLE fracoes ALTER COLUMN horario_fim TYPE VARCHAR(50);
ALTER TABLE cabecalho ALTER COLUMN turno TYPE VARCHAR(100);
