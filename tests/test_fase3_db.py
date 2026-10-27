"""Testes automatizados da Fase 3 (MER/DER, CRUD SQL e relatórios de sensores)."""

from pathlib import Path

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
from src.db import get_connection


def test_crud_completo_e_integridade_relacional(tmp_path: Path):
    db_file = tmp_path / "test_farmtech.db"
    conn, motor = get_connection(db_file)
    assert "SQLite" in motor or "Oracle" in motor
    seed_cadastros_iniciais(conn)

    # Create
    lid = criar_leitura(conn, "ESP32-TL01", "2026-05-12 10:00:00", 30.0, 5.4, 22.0, 9.0, 75.0, 26.5)
    df = listar_leituras(conn, "TL-01")
    assert len(df) == 1
    assert int(df.iloc[0]["bomba_ligada"]) == 1  # umidade 30% < 45% aciona bomba

    # Update
    ok_up = atualizar_leitura(conn, lid, umidade_solo_pct=52.0, ph_solo=6.1, bomba_ligada=0)
    assert ok_up is True
    df_up = listar_leituras(conn, "TL-01")
    assert float(df_up.iloc[0]["umidade_solo_pct"]) == 52.0
    assert int(df_up.iloc[0]["bomba_ligada"]) == 0

    # Delete
    ok_del = deletar_leitura(conn, lid)
    assert ok_del is True
    assert len(listar_leituras(conn, "TL-01")) == 0
    conn.close()


def test_importacao_fase2_e_relatorio_sql(tmp_path: Path):
    db_file = tmp_path / "test_import.db"
    conn, _ = get_connection(db_file)
    n = importar_leituras_fase2(conn)
    assert n == 8
    rel = relatorio_deficit_por_talhao(conn)
    assert len(rel) == 4
    assert set(rel["codigo_talhao"]) == {"TL-01", "TL-02", "TL-03", "TL-04"}
    assert (rel["agua_aplicada_mm"] > 0).all()
    conn.close()


def test_executar_demo_gera_figuras(tmp_path: Path):
    res = executar_demo(tmp_path / "demo.db")
    assert res["leituras_importadas"] == 8
    assert Path(res["der_png"]).exists()
    assert Path(res["relatorio_png"]).exists()
