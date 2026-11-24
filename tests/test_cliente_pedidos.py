from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.auth import criar_token
from app.database import get_db
from app.main import app
from app.models.usuario import Usuario
from app.models.venda import Venda, ItemVenda


def test_cliente_acessa_apenas_proprio_comprovante(db_session, monkeypatch):
    import app.database as database
    sessions = sessionmaker(bind=db_session.get_bind(), autoflush=False)
    monkeypatch.setattr(database, 'Session', sessions)
    db_session.add_all([
        Usuario(id=301, nome='Cliente A', email='a@example.test', senha_hash='x', role='cliente', ativo=True),
        Usuario(id=302, nome='Cliente B', email='b@example.test', senha_hash='x', role='cliente', ativo=True),
        Venda(id=401, usuario_id=301, total_bruto=10, total_liquido=10, desconto_percentual=0),
        Venda(id=402, usuario_id=302, total_bruto=10, total_liquido=10, desconto_percentual=0),
    ])
    db_session.commit()
    cliente = TestClient(app)
    cliente.cookies.set('access_token', criar_token({'sub': 'a@example.test', 'role': 'cliente', 'id': 301}))
    assert cliente.get('/cliente/').status_code == 200
    assert cliente.get('/pdv/venda/401').status_code == 200
    assert cliente.get('/pdv/venda/402').status_code == 404
    assert cliente.post('/pdv/finalizar', data={}).status_code == 403
    assert cliente.get('/usuarios/', follow_redirects=False).headers['location'] == '/cliente/'
    assert cliente.post('/rfid/operacoes', json={'tipo': 'identificar'}).status_code == 403
    assert cliente.post('/rfid/operacoes', json={'tipo': 'pagar', 'forma_pagamento': 'cortesia'}).status_code == 403


def test_conta_cliente_desativada_nao_acessa_pedidos(db_session, monkeypatch):
    import app.database as database
    monkeypatch.setattr(database, 'Session', sessionmaker(bind=db_session.get_bind()))
    db_session.add(Usuario(id=303, nome='Cliente', email='c@example.test', senha_hash='x', role='cliente', ativo=False))
    db_session.commit()
    cliente = TestClient(app)
    cliente.cookies.set('access_token', criar_token({'sub': 'c@example.test', 'role': 'cliente', 'id': 303}))
    assert cliente.get('/cliente/').status_code == 403


def test_dashboard_cliente_separa_ranking_geral_e_proprio(db_session, monkeypatch):
    import app.database as database
    monkeypatch.setattr(database, 'Session', sessionmaker(bind=db_session.get_bind()))
    db_session.add_all([
        Usuario(id=501, nome='Ana', email='ana-dashboard@example.test', senha_hash='x', role='cliente', ativo=True),
        Usuario(id=502, nome='Bia', email='bia-dashboard@example.test', senha_hash='x', role='cliente', ativo=True),
        Venda(id=601, usuario_id=501, total_bruto=10, total_liquido=10, desconto_percentual=0),
        Venda(id=602, usuario_id=502, total_bruto=20, total_liquido=20, desconto_percentual=0),
    ])
    db_session.flush()
    db_session.add_all([
        ItemVenda(venda_id=601, produto_nome='Sabor Ana', quantidade=1, preco_unitario=10),
        ItemVenda(venda_id=602, produto_nome='Sabor Bia', quantidade=2, preco_unitario=10),
    ])
    db_session.commit()
    cliente = TestClient(app)
    cliente.cookies.set('access_token', criar_token({'sub': 'ana-dashboard@example.test', 'role': 'cliente', 'id': 501, 'nome': 'Ana'}))
    resposta = cliente.get('/cliente/')
    assert resposta.status_code == 200
    geral, pessoal = resposta.text.split('id="ranking-comprados"')
    assert 'Sabor Ana' in geral and 'Sabor Bia' in geral
    assert 'Sabor Ana' in pessoal and 'Sabor Bia' not in pessoal
    assert cliente.get('/cliente/pdv').status_code == 200


def test_raiz_publica_abre_escolha_de_perfil(db_session):
    cliente = TestClient(app)
    resposta = cliente.get('/', follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers['location'] == '/acesso/'
