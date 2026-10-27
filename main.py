"""CLI principal da Fase 3 — Banco de Dados Estruturado e CRUD de Sensores."""

from __future__ import annotations

import argparse
import pandas as pd

from src.crud_sensores import executar_demo


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 3 — Banco de Dados Oracle/SQL FarmTech Solutions")
    parser.add_argument("--demo", action="store_true", help="Executa a demonstração completa não-interativa")
    parser.parse_args()

    res = executar_demo()
    print(f"=== FASE 3 — BANCO DE DADOS FARMTECH ({res['motor_banco']}) ===")
    print(f"Leituras importadas da Fase 2 (ESP32): {res['leituras_importadas']}")
    print("\nRelatório SQL por Talhão:")
    print(pd.DataFrame(res["relatorio"]).to_string(index=False))
    print(f"\nArquivos gerados:\n  - {res['der_png']}\n  - {res['relatorio_png']}")


if __name__ == "__main__":
    main()
