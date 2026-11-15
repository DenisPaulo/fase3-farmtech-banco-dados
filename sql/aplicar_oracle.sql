-- Aplica o DDL e o PL/SQL e encerra o SQL*Plus.
-- Caminho pensado para o container (veja o README).
-- No SQL Developer da FIAP, execute schema_oracle.sql e depois plsql_farmtech.sql com F5.
WHENEVER SQLERROR EXIT SQL.SQLCODE
@@schema_oracle.sql
@@plsql_farmtech.sql
PROMPT DDL e pacote PKG_FARMTECH aplicados.
EXIT
