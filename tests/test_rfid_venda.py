import json
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base
import app.models
from app.models.categoria import Categoria
from app.models.produtos import Produto
from app.models.rfid import CartaoRFID, OperacaoRFID
from app.models.venda import Venda
from app.services.rfid_service import RFIDSerialService
from app.services.qr_pagamento import ConfirmacaoQR

class RFIDVendaTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)
        db = self.sessions()
        db.add(Categoria(id=1, nome='abre-alas'))
        db.add(Produto(id=1, nome='Bebida', preco=10.0, categoria_id=1, ativo=True, estoque_atual=0))
        db.add(CartaoRFID(id=1, uid='AABBCCDD', nome='Teste', saldo_centavos=1500, ativo=True))
        db.commit(); db.close()
        self.service = RFIDSerialService(session_factory=self.sessions)
        self.commands = []
        self.service._send = self.commands.append

    def executar(self, cents, cortesia='false'):
        db = self.sessions()
        db.add(OperacaoRFID(operacao_id='op', tipo='pagar', status='aguardando_tag', valor_centavos=cents, operador_id=1))
        db.commit(); db.close()
        dados = {'carrinho_json': json.dumps([{'produto_id': 1, 'quantidade': 1}]), 'observacao': '',
                 'funcionario_comprador_id': '', 'desconto_manual_percentual': '', 'cortesia': cortesia,
                 'forma_pagamento': 'cortesia' if cortesia == 'true' else 'rfid', 'forma_pagamento_2': '',
                 'valor_pagamento_1': '', 'valor_pagamento_2': '', 'filial': 'Pinheiros'}
        self.service._active = {'id': 'op', 'tipo': 'pagar', 'valor': cents, 'status': 'aguardando_tag',
                                'venda_dados': dados, 'usuario': {'id': 1}}
        self.service._handle_tag('AABBCCDD')
        db = self.sessions()
        op = db.query(OperacaoRFID).filter_by(operacao_id='op').one()
        result = (op.status, op.venda_id, db.query(CartaoRFID).one().saldo_centavos, db.query(Venda).count(), op.erro)
        db.close()
        return result

    def test_pagamento_cria_venda_e_debita_uma_vez(self):
        status, venda, saldo, count, erro = self.executar(1000)
        self.assertEqual((status, saldo, count), ('aprovado', 500, 1), erro)
        self.assertIsNotNone(venda)
        self.service._handle_tag('AABBCCDD')
        db = self.sessions(); self.assertEqual(db.query(Venda).count(), 1); db.close()

    def test_cortesia_exige_cartao_sem_debitar(self):
        status, venda, saldo, count, erro = self.executar(0, 'true')
        self.assertEqual((status, saldo, count), ('aprovado', 1500, 1), erro)
        self.assertIsNotNone(venda)

    def test_total_divergente_nao_debita_nem_cria_venda(self):
        status, venda, saldo, count, erro = self.executar(900)
        self.assertEqual((status, venda, saldo, count), ('erro_comunicacao', None, 1500, 0), erro)

    def test_finalizacao_direta_e_bloqueada(self):
        from app.controllers.pdv_controller import finalizar_venda
        db = self.sessions()
        resposta = finalizar_venda(request=None, carrinho_json='[]', observacao='',
            funcionario_comprador_id='', desconto_manual_percentual='', cortesia='false',
            forma_pagamento='rfid', forma_pagamento_2='', valor_pagamento_1='',
            valor_pagamento_2='', filial='Pinheiros', db=db, usuario={'id': 1})
        self.assertEqual(resposta.headers['location'], '/pdv?erro=rfid')
        self.assertEqual(db.query(Venda).count(), 0)
        db.close()

    def test_qr_pix_cria_venda_uma_vez_sem_debitar_cartao(self):
        qr = ConfirmacaoQR(self.sessions)
        dados = {'carrinho_json': '[{"produto_id":1,"quantidade":1}]', 'observacao': '',
                 'funcionario_comprador_id': '', 'desconto_manual_percentual': '', 'cortesia': 'false',
                 'forma_pagamento': 'pix', 'forma_pagamento_2': '', 'valor_pagamento_1': '',
                 'valor_pagamento_2': '', 'filial': 'Pinheiros'}
        operation = qr.iniciar(1, 1000, dados, {'id': 1})
        self.assertEqual(qr.confirmar(operation['id']), 'aprovado')
        self.assertEqual(qr.confirmar(operation['id']), 'invalido')
        db = self.sessions()
        self.assertEqual(db.query(Venda).one().forma_pagamento, 'pix')
        self.assertEqual(db.query(CartaoRFID).one().saldo_centavos, 1500)
        db.close()

    def test_qr_cortesia_exibe_brinde(self):
        qr = ConfirmacaoQR(self.sessions)
        dados = {'carrinho_json': '[{"produto_id":1,"quantidade":1}]', 'observacao': '',
                 'funcionario_comprador_id': '', 'desconto_manual_percentual': '', 'cortesia': 'true',
                 'forma_pagamento': 'cortesia', 'forma_pagamento_2': '', 'valor_pagamento_1': '',
                 'valor_pagamento_2': '', 'filial': 'Pinheiros'}
        operation = qr.iniciar(1, 0, dados, {'id': 1})
        self.assertEqual(qr.confirmar(operation['id']), 'brinde')
        db = self.sessions()
        self.assertEqual(db.query(Venda).one().total_liquido, 0)
        db.close()

    def test_qr_expirado_nao_conclui_venda(self):
        qr = ConfirmacaoQR(self.sessions)
        operation = qr.iniciar(1, 1000, {}, {'id': 1})
        deadline, dados, usuario, cents = qr.pending[operation['id']]
        qr.pending[operation['id']] = (0, dados, usuario, cents)
        self.assertEqual(qr.confirmar(operation['id']), 'expirado')
        db = self.sessions()
        self.assertEqual(db.query(Venda).count(), 0)
        db.close()

    def test_saldo_insuficiente_nao_cria_venda(self):
        db = self.sessions(); db.query(CartaoRFID).one().saldo_centavos = 100; db.commit(); db.close()
        status, venda, saldo, count, erro = self.executar(1000)
        self.assertEqual((status, venda, saldo, count), ('negado_saldo_insuficiente', None, 100, 0), erro)

    def test_apos_saldo_insuficiente_permite_nova_tentativa(self):
        db = self.sessions(); db.query(CartaoRFID).one().saldo_centavos = 100; db.commit(); db.close()
        self.executar(1000)
        dados = self.service._active['venda_dados'].copy()
        self.service._connect = lambda: None
        db = self.sessions(); db.add(CartaoRFID(uid='11223344', nome='Outro cartão', saldo_centavos=1500, ativo=True)); db.commit(); db.close()
        operation = self.service.iniciar('pagar', 1, 1000, dados, {'id': 1})
        self.service._handle_tag('11223344')
        db = self.sessions()
        self.assertEqual(db.query(OperacaoRFID).filter_by(operacao_id=operation['id']).one().status, 'aprovado')
        self.assertEqual(db.query(Venda).count(), 1)
        self.assertEqual(db.query(CartaoRFID).filter_by(uid='AABBCCDD').one().saldo_centavos, 100)
        self.assertEqual(db.query(CartaoRFID).filter_by(uid='11223344').one().saldo_centavos, 500)
        db.close()

    def test_fila_atende_cada_venda_na_ordem(self):
        dados = {'carrinho_json': '[{"produto_id":1,"quantidade":1}]', 'observacao': '',
                 'funcionario_comprador_id': '', 'desconto_manual_percentual': '', 'cortesia': 'false',
                 'forma_pagamento': 'debito', 'forma_pagamento_2': '', 'valor_pagamento_1': '',
                 'valor_pagamento_2': '', 'filial': 'Pinheiros'}
        self.service._connect = lambda: None
        db = self.sessions(); db.add(CartaoRFID(uid='11223344', nome='Segundo', saldo_centavos=1500, ativo=True)); db.commit(); db.close()
        primeira = self.service.iniciar('pagar', 1, 1000, dados, {'id': 1})
        segunda = self.service.iniciar('pagar', 2, 1000, dados, {'id': 2})
        self.assertEqual(segunda['status'], 'na_fila')
        self.assertEqual(self.service.consultar(segunda['id'], 2)['posicao'], 1)
        self.assertIsNone(self.service.consultar(segunda['id'], 1))
        self.service._handle_tag('AABBCCDD')
        self.assertEqual(self.service.consultar(primeira['id'], 1)['status'], 'aprovado')
        self.assertEqual(self.service.consultar(segunda['id'], 2)['status'], 'aguardando_tag')
        self.service._handle_tag('11223344')
        db = self.sessions()
        self.assertEqual(db.query(Venda).count(), 2)
        self.assertEqual({v.usuario_id for v in db.query(Venda)}, {1, 2})
        db.close()

if __name__ == '__main__': unittest.main()
