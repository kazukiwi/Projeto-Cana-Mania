from app.auth import get_usuario_logado
from app.main import app
from app.models.filial import EstoqueFilial, FILIAIS
from app.models.produtos import Produto
from app.models.transferencia_estoque import TransferenciaEstoque
from app.models.usuario import Usuario


def cadastrar_usuario(db, usuario_id, role):
    db.add(Usuario(
        id=usuario_id,
        nome="Pessoa de teste",
        email=f"pessoa{usuario_id}@teste.local",
        senha_hash="teste",
        role=role,
        ativo=True,
    ))
    db.commit()


def test_admin_transfere_estoque_e_registra_historico(usuario_fake, db_session):
    cadastrar_usuario(db_session, 1, "admin")
    produto = Produto(nome="Produto para transferência", preco=10, estoque_atual=12, ativo=True)
    db_session.add(produto)
    db_session.flush()
    db_session.add_all([
        EstoqueFilial(produto_id=produto.id, filial=FILIAIS[0], quantidade=10),
        EstoqueFilial(produto_id=produto.id, filial=FILIAIS[1], quantidade=2),
    ])
    db_session.commit()

    resposta = usuario_fake.post("/estoque/transferencias", data={
        "produto_id": produto.id,
        "filial_origem": FILIAIS[0],
        "filial_destino": FILIAIS[1],
        "quantidade": 4,
    }, follow_redirects=False)

    assert resposta.status_code == 303
    saldos = {item.filial: item.quantidade for item in db_session.query(EstoqueFilial).filter_by(produto_id=produto.id)}
    assert saldos[FILIAIS[0]] == 6
    assert saldos[FILIAIS[1]] == 6
    registro = db_session.query(TransferenciaEstoque).one()
    assert registro.quantidade == 4
    assert registro.saldo_origem_anterior == 10
    assert registro.saldo_origem_atualizado == 6


def test_funcionario_nao_ve_nem_executa_transferencia(usuario_fake, db_session):
    cadastrar_usuario(db_session, 2, "funcionario")
    produto = Produto(nome="Produto restrito", preco=10, estoque_atual=5, ativo=True)
    db_session.add(produto)
    db_session.flush()
    db_session.add(EstoqueFilial(produto_id=produto.id, filial=FILIAIS[0], quantidade=5))
    db_session.commit()
    app.dependency_overrides[get_usuario_logado] = lambda: {"id": 2, "nome": "Pessoa de teste", "role": "funcionario"}

    tela = usuario_fake.get("/estoque/")
    resposta = usuario_fake.post("/estoque/transferencias", data={
        "produto_id": produto.id,
        "filial_origem": FILIAIS[0],
        "filial_destino": FILIAIS[1],
        "quantidade": 1,
    }, follow_redirects=False)

    assert tela.status_code == 200
    assert "Enviar estoque para outra filial" not in tela.text
    assert resposta.status_code == 403
    assert db_session.query(TransferenciaEstoque).count() == 0
    assert db_session.query(EstoqueFilial).filter_by(produto_id=produto.id, filial=FILIAIS[0]).one().quantidade == 5