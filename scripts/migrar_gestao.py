"""Valida a migração numa cópia e, com --aplicar, atualiza o SQLite local."""
import argparse
import os
from pathlib import Path
import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text
from app.database import engine

CAMPOS = {"produtos":["preco"],"estoques_variacoes":["preco"],"movimentacoes":["preco_unitario"],
          "vendas":["total_bruto","total_liquido"],"itens_venda":["preco_unitario"],"fechamentos_diarios":["total_vendido"]}
REVISAO = "fb1c2d3e4f5a"

def retrato(caminho):
    with sqlite3.connect(caminho) as banco:
        return {(t,c): banco.execute(f'SELECT id, "{c}" FROM "{t}" ORDER BY id').fetchall()
                for t,campos in CAMPOS.items() for c in campos}

def migrar(caminho):
    os.environ["DATABASE_URL"] = "sqlite:///" + caminho.as_posix()
    command.upgrade(Config("alembic.ini"), "head")

def main():
    args=argparse.ArgumentParser()
    args.add_argument("--aplicar",action="store_true")
    aplicar=args.parse_args().aplicar
    if engine.dialect.name != "sqlite":
        raise SystemExit("Este utilitário é exclusivo do SQLite local. Use alembic upgrade head para PostgreSQL.")
    origem=Path(engine.url.database).resolve()
    raiz=Path.cwd().resolve()
    if not origem.is_relative_to(raiz):
        raise SystemExit("O banco precisa estar dentro deste projeto.")
    with engine.connect() as conexao:
        versao=conexao.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    if versao == REVISAO:
        print("Banco já está na revisão " + REVISAO)
        return
    if versao != "fa0b1c2d3e4f":
        raise SystemExit("Revisão inesperada; confira as migrações antes de continuar.")
    destino=raiz/"backups"
    destino.mkdir(exist_ok=True)
    instante=datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup=destino/f"antes-gestao-{instante}.db"
    ensaio=destino/f"ensaio-gestao-{instante}.db"
    with sqlite3.connect(origem) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    with sqlite3.connect(backup) as src, sqlite3.connect(ensaio) as dst:
        src.backup(dst)
    antes=retrato(backup)
    migrar(ensaio)
    depois=retrato(ensaio)
    for chave, linhas in antes.items():
        esperado=[(id, int((Decimal(str(v))*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP)) if v is not None else None) for id,v in linhas]
        if depois[chave] != esperado:
            raise RuntimeError("Valores não preservados em " + str(chave))
    with sqlite3.connect(ensaio) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    print("Ensaio validado: contagens e valores monetários preservados.")
    print("Backup: " + str(backup))
    if aplicar:
        migrar(origem)
        with sqlite3.connect(origem) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        print("Banco local atualizado para " + REVISAO)
    else:
        print("Banco original não alterado. Use --aplicar após revisar o ensaio.")

if __name__ == "__main__":
    main()
