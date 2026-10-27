"""Camada de conexão com Oracle Database e fallback automático em SQLite.

Seguindo o padrão de segurança dos projetos anteriores da FarmTech / CanaTech,
as credenciais do Oracle são lidas exclusivamente de variáveis de ambiente
(`.env.example`). Quando as variáveis `ORACLE_USER`/`ORACLE_PASSWORD` não estão
definidas ou o servidor Oracle não está acessível localmente, o módulo ativa
automaticamente um banco relacional SQLite com o mesmo modelo de 5 tabelas
(`CULTURAS`, `TALHOES`, `SENSORES`, `LEITURAS_SENSORES` e `APLICACOES_INSUMOS`).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "farmtech_fase3.db"

SQLITE_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS CULTURAS (
    id_cultura          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_cultura        TEXT NOT NULL,
    variedade           TEXT NOT NULL,
    umidade_ideal_min   REAL NOT NULL,
    umidade_ideal_max   REAL NOT NULL,
    ph_ideal_min        REAL NOT NULL,
    ph_ideal_max        REAL NOT NULL,
    n_min_mg_dm3        REAL NOT NULL,
    p_min_mg_dm3        REAL NOT NULL,
    k_min_mg_dm3        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS TALHOES (
    id_talhao           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cultura          INTEGER NOT NULL,
    codigo_talhao       TEXT NOT NULL UNIQUE,
    nome_talhao         TEXT NOT NULL,
    area_ha             REAL NOT NULL,
    altitude_m          REAL NOT NULL,
    FOREIGN KEY (id_cultura) REFERENCES CULTURAS (id_cultura)
);

CREATE TABLE IF NOT EXISTS SENSORES (
    id_sensor           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_talhao           INTEGER NOT NULL,
    codigo_sensor       TEXT NOT NULL UNIQUE,
    tipo_sensor         TEXT NOT NULL,
    modelo_hw           TEXT NOT NULL DEFAULT 'ESP32 + DHT22 + LDR + NPK',
    status_operacional  TEXT NOT NULL DEFAULT 'ATIVO',
    FOREIGN KEY (id_talhao) REFERENCES TALHOES (id_talhao)
);

CREATE TABLE IF NOT EXISTS LEITURAS_SENSORES (
    id_leitura          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_sensor           INTEGER NOT NULL,
    data_hora           TEXT NOT NULL,
    umidade_solo_pct    REAL NOT NULL,
    ph_solo             REAL NOT NULL,
    nitrogenio_mg_dm3   REAL NOT NULL,
    fosforo_mg_dm3      REAL NOT NULL,
    potassio_mg_dm3     REAL NOT NULL,
    temperatura_c       REAL NOT NULL,
    bomba_ligada        INTEGER NOT NULL DEFAULT 0 CHECK (bomba_ligada IN (0, 1)),
    FOREIGN KEY (id_sensor) REFERENCES SENSORES (id_sensor)
);

CREATE TABLE IF NOT EXISTS APLICACOES_INSUMOS (
    id_aplicacao        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_talhao           INTEGER NOT NULL,
    id_leitura_origem   INTEGER,
    data_aplicacao      TEXT NOT NULL,
    tipo_aplicacao      TEXT NOT NULL,
    volume_agua_mm      REAL NOT NULL DEFAULT 0,
    dose_npk_kg_ha      REAL NOT NULL DEFAULT 0,
    motivo_tecnico      TEXT NOT NULL,
    FOREIGN KEY (id_talhao) REFERENCES TALHOES (id_talhao),
    FOREIGN KEY (id_leitura_origem) REFERENCES LEITURAS_SENSORES (id_leitura)
);
"""


def tentar_conectar_oracle():
    """Tenta conectar ao Oracle caso ORACLE_USER e ORACLE_PASSWORD estejam configurados."""
    usuario = os.getenv("ORACLE_USER")
    senha = os.getenv("ORACLE_PASSWORD")
    if not usuario or not senha or usuario == "seu_usuario":
        return None
    host = os.getenv("ORACLE_HOST", "oracle.fiap.com.br")
    porta = os.getenv("ORACLE_PORT", "1521")
    servico = os.getenv("ORACLE_SERVICE", "ORCL")
    dsn = f"{host}:{porta}/{servico}"
    try:
        import oracledb
        return oracledb.connect(user=usuario, password=senha, dsn=dsn)
    except Exception:
        return None


def get_connection(sqlite_path: Path | str = DEFAULT_SQLITE_PATH) -> tuple[sqlite3.Connection, str]:
    """Retorna `(conexao, motor)` garantindo que o schema relacional exista."""
    ora_conn = tentar_conectar_oracle()
    if ora_conn is not None:
        return ora_conn, "Oracle Database"

    db_path = Path(sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SQLITE_DDL)
    conn.commit()
    return conn, "SQLite (fallback compatível com schema Oracle)"
