from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.usuario import Usuario
from app.models.venda import Venda


def preparar_banco(db_session, monkeypatch):
    import app.database as database
    monkeypatch.setattr(database, 'Session', sessionmaker(bind=db_session.get_bind()))


def test_visitante_pode_entrar_e_ver_so_proprio_comprovante(db_session, monkeypatch):
    preparar_banco(db_session, monkeypatch)
    cliente = TestClient(app)
    entrada = cliente.get('/acesso/')
    assert entrada.status_code == 200
    assert 'Continuar como visitante' in entrada.text
    assert 'Sou usuário' in entrada.text
    assert 'Administrador ou funcionário' in entrada.text
    assert '/static/img/logo.webp' in entrada.text
    resposta = cliente.post('/acesso/visitante', follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers['location'] == '/cliente/'
    visitante = db_session.query(Usuario).filter_by(role='visitante').one()
    db_session.add_all([Venda(id=901, usuario_id=visitante.id, total_bruto=2, total_liquido=2, desconto_percentual=0),
                        Venda(id=902, usuario_id=None, total_bruto=2, total_liquido=2, desconto_percentual=0)])
    db_session.commit()
    assert cliente.get('/cliente/').status_code == 200
    assert cliente.get('/pdv/venda/901').status_code == 200
    assert cliente.get('/pdv/venda/902').status_code == 404
    assert cliente.post('/pdv/finalizar', data={}).status_code == 403
    assert cliente.post('/rfid/operacoes', json={'tipo': 'pagar', 'forma_pagamento': 'cortesia'}).status_code == 403


def test_cadastro_publico_cria_cliente_nao_admin(db_session, monkeypatch):
    preparar_banco(db_session, monkeypatch)
    cliente = TestClient(app)
    resposta = cliente.post('/acesso/cadastro', data={'nome': 'Ana', 'email': 'ANA@example.test', 'senha': 'senha12345'}, follow_redirects=False)
    assert resposta.status_code == 303
    assert db_session.query(Usuario).filter_by(email='ana@example.test').one().role == 'cliente'
    assert cliente.get('/cliente/').status_code == 200
    assert cliente.post('/usuarios/novo', data={}).status_code == 403


def test_login_do_usuario_mantem_a_tela_em_caso_de_erro(db_session, monkeypatch):
    preparar_banco(db_session, monkeypatch)
    cliente = TestClient(app)
    pagina = cliente.get('/acesso/usuario')
    assert pagina.status_code == 200
    assert 'Cadastre-se' in pagina.text
    resposta = cliente.post('/auth/login', data={'email': 'inexistente@example.test', 'senha': 'senhaerrada', 'origem': 'cliente'})
    assert 'E-mail ou senha inválidos' in resposta.text
    assert 'Entre na sua conta' in resposta.text


def test_qr_usa_endereco_local_e_exige_equipe(db_session, monkeypatch):
    from app.auth import criar_token
    import app.controllers.acesso_controller as acesso
    preparar_banco(db_session, monkeypatch)
    monkeypatch.delenv('ACESSO_PUBLICO_URL', raising=False)
    monkeypatch.setattr(acesso.socket, 'gethostbyname_ex', lambda nome: ('pc', [], ['192.168.100.39']))
    cliente = TestClient(app)
    cliente.cookies.set('access_token', criar_token({'sub': 'equipe@example.test', 'role': 'admin', 'id': 1}))
    resposta = cliente.get('/acesso/qr')
    assert resposta.status_code == 200
    assert 'http://192.168.100.39/acesso/' in resposta.text
    assert 'data:image/svg+xml;base64,' in resposta.text


def test_visitante_pode_iniciar_pedido_sem_desconto(db_session, monkeypatch):
    import json
    import app.controllers.rfid_admin_controller as rfid
    from app.models.categoria import Categoria
    from app.models.produtos import Produto
    preparar_banco(db_session, monkeypatch)
    db_session.add(Categoria(id=601, nome='abre-alas'))
    db_session.add(Produto(id=601, nome='Bebida', preco=10.0, categoria_id=601, ativo=True, estoque_atual=0))
    db_session.commit()
    class LeitorFake:
        def iniciar(self, tipo, operador_id, cents, dados, usuario):
            assert tipo == 'pagar' and cents == 1000 and usuario['role'] == 'visitante'
            return {'id': 'a' * 32, 'status': 'aguardando_tag'}
    monkeypatch.setattr(rfid, 'obter_rfid', lambda: LeitorFake())
    cliente = TestClient(app)
    cliente.post('/acesso/visitante', follow_redirects=False)
    resposta = cliente.post('/rfid/operacoes', json={
        'tipo': 'pagar', 'centavos': 1000, 'carrinho_json': json.dumps([{'produto_id': 601, 'quantidade': 1}]),
        'filial': 'Pinheiros', 'forma_pagamento': 'debito', 'cortesia': 'false', 'confirmacao': 'cartao',
    })
    assert resposta.status_code == 201
    assert resposta.json()['status'] == 'aguardando_tag'
