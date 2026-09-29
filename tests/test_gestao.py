import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.auth import get_usuario_logado, get_admin
from app.models import comercial
from app.models.usuario import Usuario
from app.models.categoria import Categoria
from app.models.produtos import Produto
from app.models.filial import EstoqueFilial
from app.models.venda import Venda, ItemVenda
from app.models.comercial import MovimentoCaixa, ConferenciaCaixa, AlteracaoEstoquePreco
from app.money import dinheiro, ZERO
from app.services.vendas import registrar_venda
from app.controllers.comercial_controller import resumo_caixa, FUSO
with patch.object(Base.metadata, "create_all"):
    from app.main import app

class GestaoTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread":False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add_all([
            Usuario(id=1, nome="Operador", email="op@example.com", senha_hash="teste", role="funcionario"),
            Usuario(id=2, nome="Administrador", email="admin@example.com", senha_hash="teste", role="admin"),
            Categoria(id=1, nome="abre-alas", ativo=True),
            Categoria(id=2, nome="enredo", ativo=True),
            Categoria(id=3, nome="maniacos por drink", ativo=True),
            Categoria(id=4, nome="cookies", ativo=True),
            Categoria(id=5, nome="outra", ativo=True),
        ])
        self.db.flush()
        self.db.add_all([
            Produto(id=1, nome="Drink A", preco=Decimal("0.10"), ativo=True, categoria_id=1, estoque_atual=0),
            Produto(id=2, nome="Drink B", preco=Decimal("0.20"), ativo=True, categoria_id=2, estoque_atual=0),
            Produto(id=3, nome="Drink C", preco=Decimal("3.30"), ativo=True, categoria_id=3, estoque_atual=0),
            Produto(id=4, nome="Cookie", preco=Decimal("7.25"), ativo=True, categoria_id=4, estoque_atual=10),
            Produto(id=5, nome="Nao mostrar", preco=Decimal("9"), ativo=True, categoria_id=5, estoque_atual=0),
            Produto(id=6, nome="Inativo", preco=Decimal("1"), ativo=False, categoria_id=1, estoque_atual=0),
        ])
        self.db.flush()
        self.db.add(EstoqueFilial(produto_id=4, filial="Pinheiros", quantidade=10))
        self.db.commit()
        self.usuario = {"id":1,"nome":"Operador","role":"funcionario"}
        self.overrides = app.dependency_overrides.copy()
        def db_request():
            with self.Session() as db:
                db.info.update(usuario_id=self.usuario["id"], origem="teste")
                yield db
        app.dependency_overrides[get_db] = db_request
        app.dependency_overrides[get_usuario_logado] = lambda: self.usuario
        self.client = TestClient(app, raise_server_exceptions=True)

    def tearDown(self):
        self.client.close()
        self.db.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.overrides)
        self.engine.dispose()

    def vender(self, token=None, itens=None, pagamento="dinheiro"):
        return registrar_venda(self.db, 1, token or str(uuid4()), json.dumps(itens or [{"produto_id":4,"quantidade":2}]), "Pinheiros", pagamento)

    def test_reenvio_nao_duplica_estoque_ou_venda(self):
        token = str(uuid4())
        primeira = self.vender(token)
        segunda = self.vender(token)
        self.assertEqual(primeira.id, segunda.id)
        self.assertEqual(self.db.query(Venda).count(),1)
        self.assertEqual(self.db.query(ItemVenda).count(),1)
        self.assertEqual(self.db.query(EstoqueFilial).first().quantidade,8)

    def test_token_com_outros_dados_rejeitado(self):
        token = str(uuid4())
        self.vender(token)
        with self.assertRaises(HTTPException) as erro:
            self.vender(token, pagamento="pix")
        self.assertEqual(erro.exception.status_code,409)

    def test_falha_desfaz_toda_venda(self):
        with self.assertRaises(HTTPException):
            self.vender(itens=[{"produto_id":4,"quantidade":2},{"produto_id":999,"quantidade":1}])
        self.assertEqual(self.db.query(Venda).count(),0)
        self.assertEqual(self.db.query(EstoqueFilial).first().quantidade,10)

    def test_decimal_e_centavos_no_banco(self):
        venda = self.vender(itens=[{"produto_id":1,"quantidade":1},{"produto_id":2,"quantidade":1}])
        self.assertEqual(venda.total_liquido, Decimal("0.30"))
        bruto = self.db.execute(text("select total_liquido from vendas")).scalar()
        self.assertEqual(bruto,30)
        self.assertEqual(dinheiro("1.005"),Decimal("1.01"))

    def test_caixa_considera_somente_dinheiro(self):
        self.vender(pagamento="dinheiro")
        self.vender(pagamento="pix")
        hoje = datetime.now(FUSO).date()
        for tipo,valor in (("abertura","100"),("reforco","20"),("retirada","10")):
            self.db.add(MovimentoCaixa(token=str(uuid4()),data=hoje,filial="Pinheiros",usuario_id=1,tipo=tipo,valor=Decimal(valor),motivo="teste"))
        self.db.commit()
        resumo = resumo_caixa(self.db,hoje,"Pinheiros",1)
        self.assertEqual(resumo["esperado"], Decimal("124.50"))
        self.assertEqual(resumo["total"], Decimal("29.00"))

    def test_conferencia_idempotente_preserva_diferenca(self):
        self.vender()
        dados = {"data":datetime.now(FUSO).date().isoformat(),"filial":"Pinheiros","informado":"15","token":str(uuid4()),"observacao":"Teste"}
        for _ in range(2):
            self.assertEqual(self.client.post("/caixa/fechar",data=dados,follow_redirects=False).status_code,303)
        with self.Session() as db:
            self.assertEqual(db.query(ConferenciaCaixa).count(),1)
            c = db.query(ConferenciaCaixa).first()
            self.assertEqual(c.diferenca,Decimal("0.50"))
            self.assertEqual(json.loads(c.resumo_json)["pagamentos"]["dinheiro"],"14.50")

    def test_movimento_repetido_e_valor_invalido(self):
        dados={"filial":"Pinheiros","tipo":"reforco","valor":"10.25","motivo":"troco","token":str(uuid4())}
        for _ in range(2):
            self.assertEqual(self.client.post("/caixa/movimento",data=dados,follow_redirects=False).status_code,303)
        with self.Session() as db:
            self.assertEqual(db.query(MovimentoCaixa).count(),1)
        dados["valor"]="NaN"
        self.assertEqual(self.client.post("/caixa/movimento",data=dados).status_code,400)

    def test_cardapio_publico_apenas_tres_categorias(self):
        app.dependency_overrides.pop(get_usuario_logado)
        resposta=self.client.get("/cardapio")
        self.assertEqual(resposta.status_code,200)
        for nome in ("Drink A","Drink B","Drink C"):
            self.assertIn(nome,resposta.text)
        for nome in ("Cookie","Nao mostrar","Inativo"):
            self.assertNotIn(nome,resposta.text)

    def test_categoria_inativa_fora_cardapio(self):
        self.db.get(Categoria,1).ativo=False
        self.db.commit()
        self.assertNotIn("Drink A",self.client.get("/cardapio").text)

    def test_relatorio_filtros_e_exportacao(self):
        self.vender(pagamento="pix")
        self.vender(pagamento="dinheiro")
        resposta=self.client.get("/relatorios?pagamento=pix")
        self.assertEqual(resposta.status_code,200)
        csv=self.client.get("/relatorios/exportar.csv?pagamento=pix")
        self.assertEqual(csv.status_code,200)
        self.assertIn("14,50",csv.text)
        self.assertEqual(len(csv.text.strip().splitlines()),2)
        self.assertIn("attachment",csv.headers["content-disposition"])
        self.assertEqual(self.client.get("/relatorios?inicio=2026-12-10&fim=2026-01-01").status_code,400)

    def test_operador_nao_consulta_outro(self):
        self.vender()
        self.usuario={"id":2,"nome":"Outro","role":"funcionario"}
        csv=self.client.get("/relatorios/exportar.csv?operador=1")
        self.assertEqual(len(csv.text.strip().splitlines()),1)
        self.assertEqual(self.client.get("/caixa?operador=1").status_code,200)

    def test_auditoria_preco_e_estoque(self):
        self.db.info.update(usuario_id=1, origem="teste")
        self.db.get(Produto,4).preco = Decimal("8.00")
        self.db.commit()
        self.vender()
        logs = self.db.query(AlteracaoEstoquePreco).filter_by(usuario_id=1).all()
        self.assertTrue(any(a.campo=="preco" and a.anterior=="7.25" and a.novo=="8.00" for a in logs))
        self.assertTrue(any(a.entidade=="estoques_filiais" and a.anterior=="10" and a.novo=="8" for a in logs))

    def test_paginas_e_finalizacao_http(self):
        for url in ("/pdv/","/pdv/historico","/caixa","/relatorios"):
            self.assertEqual(self.client.get(url).status_code,200,url)
        dados={"carrinho_json":'[{"produto_id":1,"quantidade":3}]',"pedido_token":str(uuid4()),"filial":"Pinheiros","forma_pagamento":"dinheiro"}
        resposta=self.client.post("/pdv/finalizar",data=dados,headers={"Accept":"application/json"})
        self.assertEqual(resposta.status_code,200)
        venda_id=resposta.json()["venda_id"]
        self.assertEqual(self.client.get("/pdv/venda/"+str(venda_id)).status_code,200)
        self.assertEqual(self.client.get("/mais_vendidos").status_code,200)
        self.assertEqual(self.client.get("/pdv/pedido/"+dados["pedido_token"]).json()["venda_id"],venda_id)

    def test_auditoria_restrita_admin(self):
        self.assertEqual(self.client.get("/auditoria").status_code,401)
        app.dependency_overrides[get_admin]=lambda: {"id":2,"role":"admin"}
        self.assertEqual(self.client.get("/auditoria").status_code,200)

class ConcorrenciaTests(unittest.TestCase):
    def test_duas_requisicoes_simultaneas(self):
        with TemporaryDirectory() as pasta:
            engine = create_engine("sqlite:///" + str(Path(pasta)/"teste.db"),connect_args={"timeout":15})
            Base.metadata.create_all(engine)
            Session=sessionmaker(bind=engine)
            with Session() as db:
                db.add(Usuario(id=1,nome="Teste",email="teste@example.com",senha_hash="teste"))
                db.add(Categoria(id=1,nome="cookies",ativo=True))
                db.flush()
                db.add(Produto(id=1,nome="Cookie",categoria_id=1,ativo=True,preco=Decimal("5"),estoque_atual=10))
                db.flush()
                db.add(EstoqueFilial(produto_id=1,filial="Pinheiros",quantidade=10))
                db.commit()
            token=str(uuid4())
            def enviar(_):
                with Session() as db:
                    return registrar_venda(db,1,token,'[{"produto_id":1,"quantidade":2}]',"Pinheiros","dinheiro").id
            with ThreadPoolExecutor(max_workers=2) as pool:
                ids=list(pool.map(enviar,range(2)))
            self.assertEqual(ids[0],ids[1])
            with Session() as db:
                self.assertEqual(db.query(Venda).count(),1)
                self.assertEqual(db.query(EstoqueFilial).first().quantidade,8)
            engine.dispose()
