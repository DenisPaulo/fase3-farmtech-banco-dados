"""Testes automatizados da Fase 3 (MER/DER, CRUD SQL e relatórios de sensores)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.crud_sensores import (
    atualizar_leitura,
    criar_leitura,
    deletar_leitura,
    executar_demo,
    importar_leituras_fase2,
    listar_leituras,
    relatorio_deficit_por_talhao,
    seed_cadastros_iniciais,
)
from src.db import PROJECT_ROOT, get_connection


def test_crud_completo_e_integridade_relacional(tmp_path: Path):
    db_file = tmp_path / "test_farmtech.db"
    conn, motor = get_connection(db_file, engine="sqlite")
    assert motor.startswith("SQLite")
    seed_cadastros_iniciais(conn)

    # Create: umidade 30% abaixo do mínimo da cultura aciona bomba e gera aplicação.
    lid = criar_leitura(conn, "ESP32-TL01", "2026-05-12 10:00:00", 30.0, 5.4, 22.0, 9.0, 75.0, 26.5)
    df = listar_leituras(conn, "TL-01")
    assert len(df) == 1
    assert int(df.iloc[0]["bomba_ligada"]) == 1
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tipo_aplicacao
          FROM APLICACOES_INSUMOS
         WHERE id_leitura_origem = ?
        """,
        (lid,),
    )
    aplicacao = cur.fetchone()
    assert aplicacao is not None
    assert aplicacao[0] == "FERTIRRIGACAO"

    assert atualizar_leitura(conn, lid) is False

    # Update
    ok_up = atualizar_leitura(conn, lid, umidade_solo_pct=52.0, ph_solo=6.1, bomba_ligada=0)
    assert ok_up is True
    df_up = listar_leituras(conn, "TL-01")
    assert float(df_up.iloc[0]["umidade_solo_pct"]) == 52.0
    assert int(df_up.iloc[0]["bomba_ligada"]) == 0

    # Delete remove a leitura e a aplicação dependente.
    assert deletar_leitura(conn, 999999) is False
    ok_del = deletar_leitura(conn, lid)
    assert ok_del is True
    assert len(listar_leituras(conn, "TL-01")) == 0
    cur.execute("SELECT COUNT(*) FROM APLICACOES_INSUMOS WHERE id_leitura_origem = ?", (lid,))
    assert cur.fetchone()[0] == 0
    conn.close()


def test_criar_leitura_sensor_desconhecido(tmp_path: Path):
    conn, motor = get_connection(tmp_path / "sensor.db", engine="sqlite")
    assert motor.startswith("SQLite")
    seed_cadastros_iniciais(conn)
    with pytest.raises(ValueError, match="Sensor não cadastrado"):
        criar_leitura(conn, "ESP32-INEXISTENTE", "2026-05-12 10:00:00", 50.0, 6.0, 40.0, 20.0, 100.0, 24.0)
    conn.close()


def test_placeholder_oracle_abre_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORACLE_USER", "seu_usuario")
    monkeypatch.setenv("ORACLE_PASSWORD", "sua_senha")
    monkeypatch.delenv("FARMTECH_DB_ENGINE", raising=False)
    conn, motor = get_connection(tmp_path / "auto.db", engine="auto")
    assert motor.startswith("SQLite")
    conn.close()


def test_importacao_fase2_e_relatorio_sql(tmp_path: Path):
    db_file = tmp_path / "test_import.db"
    conn, motor = get_connection(db_file, engine="sqlite")
    assert motor.startswith("SQLite")
    n = importar_leituras_fase2(conn)
    assert n == 8
    rel = relatorio_deficit_por_talhao(conn)
    assert len(rel) == 4
    assert set(rel["codigo_talhao"]) == {"TL-01", "TL-02", "TL-03", "TL-04"}
    assert (rel["agua_aplicada_mm"] > 0).all()
    conn.close()


def test_executar_demo_gera_figuras(tmp_path: Path):
    res = executar_demo(tmp_path / "demo.db")
    assert res["motor_banco"].startswith("SQLite")
    assert res["leituras_importadas"] == 8
    assert Path(res["der_png"]).exists()
    assert Path(res["relatorio_png"]).exists()


def test_cli_main_py_demo():
    """Cobre `python main.py --demo` no modo SQLite."""
    env = os.environ.copy()
    env["FARMTECH_DB_ENGINE"] = "sqlite"
    env["ORACLE_USER"] = "seu_usuario"
    env["ORACLE_PASSWORD"] = "sua_senha"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "--demo"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "SQLite" in result.stdout
    assert "Leituras importadas da Fase 2 (ESP32): 8" in result.stdout
    assert "Relatório SQL por Talhão" in result.stdout


def test_plsql_objetos_do_schema():
    script = (PROJECT_ROOT / "sql" / "plsql_farmtech.sql").read_text(encoding="utf-8")
    schema = (PROJECT_ROOT / "sql" / "schema_oracle.sql").read_text(encoding="utf-8")
    for tabela in ("CULTURAS", "TALHOES", "SENSORES", "LEITURAS_SENSORES", "APLICACOES_INSUMOS"):
        assert f"CREATE TABLE {tabela}" in schema
    for trecho in (
        "CREATE TABLE AUDITORIA_LEITURAS",
        "PACKAGE PKG_FARMTECH",
        "PROCEDURE PRC_INSERIR_LEITURA",
        "FUNCTION FN_UMIDADE_MEDIA_TALHAO",
        "TRIGGER TRG_AUD_LEITURAS",
        "RAISE_APPLICATION_ERROR(-20001",
        "RAISE_APPLICATION_ERROR(-20010",
        "ROUND(AVG(l.umidade_solo_pct), 2)",
    ):
        assert trecho in script
    seed = (PROJECT_ROOT / "sql" / "seed_exemplo.sql").read_text(encoding="utf-8")
    assert "ESP32-TL01" in seed
    assert "TL-04" in seed
