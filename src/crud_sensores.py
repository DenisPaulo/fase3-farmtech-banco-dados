"""Operações CRUD, importação da Fase 2, relatórios SQL e figuras da Fase 3."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

from src.db import DEFAULT_SQLITE_PATH, PROJECT_ROOT, get_connection

ASSETS_DIR = PROJECT_ROOT / "assets"
FASE2_JSON = PROJECT_ROOT / "data" / "leituras_fase2_esp32.json"


def seed_cadastros_iniciais(conn: sqlite3.Connection) -> None:
    """Popula CULTURAS, TALHOES e SENSORES se o banco estiver vazio."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM CULTURAS")
    if cur.fetchone()[0] > 0:
        return

    cur.executemany(
        """
        INSERT INTO CULTURAS (
            nome_cultura, variedade, umidade_ideal_min, umidade_ideal_max,
            ph_ideal_min, ph_ideal_max, n_min_mg_dm3, p_min_mg_dm3, k_min_mg_dm3
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("Café Arábica", "Catuaí Vermelho IAC 144", 45.0, 65.0, 5.5, 6.5, 30.0, 12.0, 90.0),
            ("Milho Safrinha", "Híbrido Simples", 50.0, 70.0, 5.8, 6.8, 35.0, 15.0, 100.0),
        ],
    )

    cur.executemany(
        """
        INSERT INTO TALHOES (id_cultura, codigo_talhao, nome_talhao, area_ha, altitude_m)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, "TL-01", "Talhão Norte — Café Catuaí", 42.5, 980.0),
            (1, "TL-02", "Talhão Sul — Café Bourbon", 38.0, 1025.0),
            (1, "TL-03", "Talhão Leste — Café Mundo Novo", 51.0, 945.0),
            (2, "TL-04", "Talhão Oeste — Pivô Central", 64.0, 890.0),
        ],
    )

    cur.executemany(
        """
        INSERT INTO SENSORES (id_talhao, codigo_sensor, tipo_sensor, modelo_hw, status_operacional)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, "ESP32-TL01", "Multissensor Solo/Clima", "ESP32 + DHT22 + LDR + NPK", "ATIVO"),
            (2, "ESP32-TL02", "Multissensor Solo/Clima", "ESP32 + DHT22 + LDR + NPK", "ATIVO"),
            (3, "ESP32-TL03", "Multissensor Solo/Clima", "ESP32 + DHT22 + LDR + NPK", "ATIVO"),
            (4, "ESP32-TL04", "Multissensor Solo/Clima", "ESP32 + DHT22 + LDR + NPK", "ATIVO"),
        ],
    )
    conn.commit()


def criar_leitura(
    conn: sqlite3.Connection,
    codigo_sensor: str,
    data_hora: str,
    umidade_solo_pct: float,
    ph_solo: float,
    nitrogenio_mg_dm3: float,
    fosforo_mg_dm3: float,
    potassio_mg_dm3: float,
    temperatura_c: float,
    bomba_ligada: int | None = None,
) -> int:
    """CREATE: insere uma leitura de sensor e registra aplicação automática se necessário."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id_sensor, s.id_talhao, c.umidade_ideal_min, c.n_min_mg_dm3, c.p_min_mg_dm3, c.k_min_mg_dm3
        FROM SENSORES s
        JOIN TALHOES t ON t.id_talhao = s.id_talhao
        JOIN CULTURAS c ON c.id_cultura = t.id_cultura
        WHERE s.codigo_sensor = ?
        """,
        (codigo_sensor,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"Sensor não cadastrado: {codigo_sensor}")

    id_sensor, id_talhao, umid_min, n_min, p_min, k_min = (
        row[0], row[1], float(row[2]), float(row[3]), float(row[4]), float(row[5])
    )
    deficit_hidrico = float(umidade_solo_pct) < umid_min
    deficit_npk = (
        float(nitrogenio_mg_dm3) < n_min
        or float(fosforo_mg_dm3) < p_min
        or float(potassio_mg_dm3) < k_min
    )
    if bomba_ligada is None:
        bomba_ligada = 1 if deficit_hidrico else 0

    cur.execute(
        """
        INSERT INTO LEITURAS_SENSORES (
            id_sensor, data_hora, umidade_solo_pct, ph_solo,
            nitrogenio_mg_dm3, fosforo_mg_dm3, potassio_mg_dm3,
            temperatura_c, bomba_ligada
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            id_sensor, data_hora, float(umidade_solo_pct), float(ph_solo),
            float(nitrogenio_mg_dm3), float(fosforo_mg_dm3), float(potassio_mg_dm3),
            float(temperatura_c), int(bomba_ligada),
        ),
    )
    id_leitura = int(cur.lastrowid)

    if deficit_hidrico or deficit_npk:
        agua_mm = round(max(0.0, (umid_min + 8.0 - float(umidade_solo_pct)) * 0.85), 2) if deficit_hidrico else 0.0
        dose_npk = round(max(0.0, (n_min - float(nitrogenio_mg_dm3)) * 1.8 + 15.0), 2) if deficit_npk else 0.0
        tipo = "FERTIRRIGACAO" if (deficit_hidrico and deficit_npk) else ("IRRIGACAO" if deficit_hidrico else "ADUBACAO_NPK")
        motivo = f"Acionamento automático via leitura #{id_leitura} (umidade={umidade_solo_pct:.1f}%, pH={ph_solo:.2f})"
        cur.execute(
            """
            INSERT INTO APLICACOES_INSUMOS (
                id_talhao, id_leitura_origem, data_aplicacao, tipo_aplicacao,
                volume_agua_mm, dose_npk_kg_ha, motivo_tecnico
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (id_talhao, id_leitura, data_hora, tipo, agua_mm, dose_npk, motivo),
        )

    conn.commit()
    return id_leitura


def listar_leituras(conn: sqlite3.Connection, codigo_talhao: str | None = None) -> pd.DataFrame:
    """READ: consulta leituras com JOIN completo entre sensores, talhões e culturas."""
    filtro = "WHERE t.codigo_talhao = ?" if codigo_talhao else ""
    params = (codigo_talhao,) if codigo_talhao else ()
    query = f"""
        SELECT l.id_leitura, t.codigo_talhao, t.nome_talhao, c.nome_cultura,
               s.codigo_sensor, l.data_hora, l.umidade_solo_pct, l.ph_solo,
               l.nitrogenio_mg_dm3, l.fosforo_mg_dm3, l.potassio_mg_dm3,
               l.temperatura_c, l.bomba_ligada
        FROM LEITURAS_SENSORES l
        JOIN SENSORES s ON s.id_sensor = l.id_sensor
        JOIN TALHOES t ON t.id_talhao = s.id_talhao
        JOIN CULTURAS c ON c.id_cultura = t.id_cultura
        {filtro}
        ORDER BY l.id_leitura
    """
    return pd.read_sql_query(query, conn, params=params)


def atualizar_leitura(
    conn: sqlite3.Connection,
    id_leitura: int,
    umidade_solo_pct: float | None = None,
    ph_solo: float | None = None,
    bomba_ligada: int | None = None,
) -> bool:
    """UPDATE: atualiza campos calibrados de uma leitura existente."""
    campos = []
    valores = []
    if umidade_solo_pct is not None:
        campos.append("umidade_solo_pct = ?")
        valores.append(float(umidade_solo_pct))
    if ph_solo is not None:
        campos.append("ph_solo = ?")
        valores.append(float(ph_solo))
    if bomba_ligada is not None:
        campos.append("bomba_ligada = ?")
        valores.append(int(bomba_ligada))
    if not campos:
        return False
    valores.append(int(id_leitura))
    cur = conn.cursor()
    cur.execute(f"UPDATE LEITURAS_SENSORES SET {', '.join(campos)} WHERE id_leitura = ?", valores)
    conn.commit()
    return cur.rowcount > 0


def deletar_leitura(conn: sqlite3.Connection, id_leitura: int) -> bool:
    """DELETE: remove aplicações dependentes e exclui a leitura pelo ID."""
    cur = conn.cursor()
    cur.execute("DELETE FROM APLICACOES_INSUMOS WHERE id_leitura_origem = ?", (int(id_leitura),))
    cur.execute("DELETE FROM LEITURAS_SENSORES WHERE id_leitura = ?", (int(id_leitura),))
    conn.commit()
    return cur.rowcount > 0


def importar_leituras_fase2(conn: sqlite3.Connection, json_path: Path = FASE2_JSON) -> int:
    """Importa o lote de leituras do ESP32 (Fase 2) para o banco estruturado."""
    seed_cadastros_iniciais(conn)
    registros = json.loads(Path(json_path).read_text(encoding="utf-8"))
    inseridos = 0
    for r in registros:
        criar_leitura(
            conn,
            codigo_sensor=r["codigo_sensor"],
            data_hora=r["data_hora"],
            umidade_solo_pct=r["umidade_solo_pct"],
            ph_solo=r["ph_solo"],
            nitrogenio_mg_dm3=r["nitrogenio_mg_dm3"],
            fosforo_mg_dm3=r["fosforo_mg_dm3"],
            potassio_mg_dm3=r["potassio_mg_dm3"],
            temperatura_c=r["temperatura_c"],
            bomba_ligada=r.get("bomba_ligada"),
        )
        inseridos += 1
    return inseridos


def relatorio_deficit_por_talhao(conn: sqlite3.Connection) -> pd.DataFrame:
    """Consulta analítica SQL agregando déficit hídrico/nutricional e insumos por talhão."""
    query = """
        SELECT t.codigo_talhao,
               t.nome_talhao,
               t.area_ha,
               COUNT(l.id_leitura) AS total_leituras,
               ROUND(AVG(l.umidade_solo_pct), 2) AS umidade_media_pct,
               ROUND(MIN(l.umidade_solo_pct), 2) AS umidade_min_pct,
               ROUND(AVG(l.ph_solo), 2) AS ph_medio,
               ROUND(AVG(l.nitrogenio_mg_dm3), 1) AS n_medio,
               ROUND(AVG(l.fosforo_mg_dm3), 1) AS p_medio,
               ROUND(AVG(l.potassio_mg_dm3), 1) AS k_medio,
               SUM(l.bomba_ligada) AS acionamentos_bomba,
               COALESCE((SELECT ROUND(SUM(a.volume_agua_mm), 2)
                         FROM APLICACOES_INSUMOS a
                         WHERE a.id_talhao = t.id_talhao), 0.0) AS agua_aplicada_mm,
               COALESCE((SELECT ROUND(SUM(a.dose_npk_kg_ha), 2)
                         FROM APLICACOES_INSUMOS a
                         WHERE a.id_talhao = t.id_talhao), 0.0) AS npk_aplicado_kg_ha
        FROM TALHOES t
        LEFT JOIN SENSORES s ON s.id_talhao = t.id_talhao
        LEFT JOIN LEITURAS_SENSORES l ON l.id_sensor = s.id_sensor
        GROUP BY t.id_talhao, t.codigo_talhao, t.nome_talhao, t.area_ha
        ORDER BY t.codigo_talhao
    """
    return pd.read_sql_query(query, conn)


def gerar_diagrama_der(out_path: Path | None = None) -> Path:
    """Gera o diagrama visual do Modelo Entidade-Relacionamento (MER/DER) da Fase 3."""
    if out_path is None:
        out_path = ASSETS_DIR / "der_farmtech.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title(
        "DER — Modelo Relacional FarmTech Solutions (Oracle Database / Fase 3)",
        fontsize=13, fontweight="bold", pad=12, color="#1B365D",
    )

    tabelas = [
        (0.6, 4.1, 3.1, 2.3, "CULTURAS", [
            "PK id_cultura (NUMBER)",
            "   nome_cultura (VARCHAR2)",
            "   variedade (VARCHAR2)",
            "   umidade_ideal_min/max",
            "   ph_ideal_min/max",
            "   n/p/k_min_mg_dm3",
        ], "#E8F1F5"),
        (4.4, 4.1, 3.1, 2.3, "TALHOES", [
            "PK id_talhao (NUMBER)",
            "FK id_cultura -> CULTURAS",
            "UQ codigo_talhao (TL-01..04)",
            "   nome_talhao (VARCHAR2)",
            "   area_ha (NUMBER)",
            "   altitude_m (NUMBER)",
        ], "#E8F5E9"),
        (8.3, 4.1, 3.2, 2.3, "SENSORES", [
            "PK id_sensor (NUMBER)",
            "FK id_talhao -> TALHOES",
            "UQ codigo_sensor (ESP32-TLxx)",
            "   tipo_sensor (VARCHAR2)",
            "   modelo_hw (ESP32+DHT22+NPK)",
            "   status_operacional",
        ], "#FFF8E1"),
        (6.4, 0.6, 4.6, 2.5, "LEITURAS_SENSORES", [
            "PK id_leitura (NUMBER)",
            "FK id_sensor -> SENSORES",
            "   data_hora (TIMESTAMP)",
            "   umidade_solo_pct, ph_solo",
            "   nitrogenio, fosforo, potassio",
            "   temperatura_c, bomba_ligada (0/1)",
        ], "#FDECEA"),
        (1.0, 0.6, 4.4, 2.5, "APLICACOES_INSUMOS", [
            "PK id_aplicacao (NUMBER)",
            "FK id_talhao -> TALHOES",
            "FK id_leitura_origem -> LEITURAS",
            "   data_aplicacao, tipo_aplicacao",
            "   volume_agua_mm, dose_npk_kg_ha",
            "   motivo_tecnico (VARCHAR2)",
        ], "#F3E5F5"),
    ]

    for x, y, w, h, titulo, cols, cor in tabelas:
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.08", facecolor=cor, edgecolor="#1B365D", linewidth=1.6
        )
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h - 0.28, titulo, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#1B365D")
        ax.plot([x + 0.1, x + w - 0.1], [y + h - 0.48, y + h - 0.48], color="#1B365D", lw=1.0)
        for i, c in enumerate(cols):
            ax.text(x + 0.18, y + h - 0.75 - i * 0.28, c, ha="left", va="center", fontsize=8.5, family="monospace")

    # Setas de relacionamento 1:N
    setas = [
        ((3.7, 5.25), (4.4, 5.25), "1 : N"),
        ((7.5, 5.25), (8.3, 5.25), "1 : N"),
        ((9.8, 4.1), (9.2, 3.1), "1 : N"),
        ((5.5, 4.1), (3.6, 3.1), "1 : N"),
        ((6.4, 1.8), (5.4, 1.8), "1 : 0..N"),
    ]
    for (x0, y0), (x1, y1), txt in setas:
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="->", lw=1.6, color="#0D47A1"))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.14, txt, ha="center", fontsize=8.5, fontweight="bold", color="#0D47A1")

    fig.tight_layout()
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_path


def gerar_grafico_relatorio(df_rel: pd.DataFrame, out_path: Path | None = None) -> Path:
    """Gera o gráfico consolidado de leituras, umidade e insumos por talhão."""
    if out_path is None:
        out_path = ASSETS_DIR / "relatorio_sensores_fase3.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))

    ax = axes[0]
    x = range(len(df_rel))
    ax.bar([i - 0.18 for i in x], df_rel["umidade_media_pct"], width=0.35, color="#2E7D32", label="Umidade média [%]")
    ax.bar([i + 0.18 for i in x], df_rel["umidade_min_pct"], width=0.35, color="#C62828", label="Umidade mínima [%]")
    ax.axhline(45.0, color="#1565C0", ls="--", lw=1.3, label="Limite mínimo ideal Café (45%)")
    ax.set_xticks(list(x), df_rel["codigo_talhao"])
    ax.set_ylabel("Umidade do solo [%]")
    ax.set_title("Umidade média e crítica por talhão (SQL Fase 3)")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8.5)

    ax2 = axes[1]
    ax2.bar([i - 0.18 for i in x], df_rel["agua_aplicada_mm"], width=0.35, color="#0277BD", label="Água aplicada [mm]")
    ax2.bar([i + 0.18 for i in x], df_rel["npk_aplicado_kg_ha"], width=0.35, color="#EF6C00", label="Dose NPK [kg/ha]")
    ax2.set_xticks(list(x), df_rel["codigo_talhao"])
    ax2.set_ylabel("Volume / Dose acumulada")
    ax2.set_title("Recomendações gravadas em APLICACOES_INSUMOS")
    ax2.grid(alpha=0.3, axis="y")
    ax2.legend(fontsize=8.5)

    fig.tight_layout()
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_path


def executar_demo(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> dict:
    """Executa o fluxo completo não-interativo (seed, importação Fase 2, CRUD e gráficos)."""
    if Path(sqlite_path).exists():
        Path(sqlite_path).unlink()
    conn, motor = get_connection(sqlite_path)
    try:
        inseridos = importar_leituras_fase2(conn)
        # Demonstra CREATE + UPDATE + DELETE em registro de calibração
        id_temp = criar_leitura(conn, "ESP32-TL01", "2026-05-11 09:00:00", 39.0, 5.6, 31.0, 13.0, 95.0, 24.5)
        atualizar_leitura(conn, id_temp, umidade_solo_pct=41.5, ph_solo=5.8)
        deletar_leitura(conn, id_temp)

        df_rel = relatorio_deficit_por_talhao(conn)
        der_path = gerar_diagrama_der()
        rel_path = gerar_grafico_relatorio(df_rel)
        return {
            "motor_banco": motor,
            "leituras_importadas": inseridos,
            "relatorio": df_rel.to_dict(orient="records"),
            "der_png": str(der_path),
            "relatorio_png": str(rel_path),
        }
    finally:
        conn.close()
