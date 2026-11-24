import base64
import json
from datetime import datetime
from io import BytesIO
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.auth import get_admin
from app.database import get_db
from app.models.pedido_cliente import PedidoCliente
from app.models.rfid import OperacaoRFID
from app.models.usuario import Usuario
from app.services.rfid_service import RFIDError, obter_rfid
from app.services.qr_pagamento import qr_pagamento

router = APIRouter(tags=["Pedidos de clientes"])
templates = Jinja2Templates(directory="app/templates")
FALHAS_PAGAMENTO = {"negado_saldo_insuficiente", "expirado", "erro_comunicacao", "cancelado", "erro"}

@router.get("/admin/pedidos-clientes")
def listar_pedidos(request: Request, db: Session = Depends(get_db), usuario=Depends(get_admin)):
    pedidos = db.query(PedidoCliente).order_by(
        (PedidoCliente.status == "aguardando").desc(), PedidoCliente.criado_em.desc()).limit(200).all()
    for pedido in pedidos:
        pedido.itens = json.loads(pedido.itens_json)
        pedido.pagamento = db.query(OperacaoRFID).filter_by(operacao_id=pedido.operacao_rfid_id).first() if pedido.operacao_rfid_id else None
    return templates.TemplateResponse(request, "pedidos_clientes.html",
        {"request": request, "usuario": usuario, "pedidos": pedidos})

@router.post("/admin/pedidos-clientes/{codigo}/chamar")
def chamar_cliente(codigo: str, db: Session = Depends(get_db), usuario=Depends(get_admin)):
    pedido = db.query(PedidoCliente).filter_by(codigo=codigo.upper()).first()
    if not pedido:
        raise HTTPException(404, "Pedido nao encontrado.")
    if pedido.status == "aguardando":
        pedido.status = "chamado"
        pedido.chamado_em = datetime.now()
        db.commit()
    return RedirectResponse("/admin/pedidos-clientes", status_code=303)

@router.post("/admin/pedidos-clientes/{codigo}/pagar")
def pagar_pedido_cliente(codigo: str, request: Request, forma_pagamento: str = Form(...),
                        db: Session = Depends(get_db), usuario=Depends(get_admin)):
    pedido = db.query(PedidoCliente).filter_by(codigo=codigo.upper()).with_for_update().first()
    if not pedido:
        raise HTTPException(404, "Pedido nao encontrado.")
    if pedido.status == "pagando" and pedido.operacao_rfid_id:
        anterior = db.query(OperacaoRFID).filter_by(operacao_id=pedido.operacao_rfid_id).first()
        if anterior and anterior.status in FALHAS_PAGAMENTO:
            pedido.status = "chamado"
            pedido.operacao_rfid_id = None
            pedido.qr_url = None
            db.commit()
    if pedido.status != "chamado":
        raise HTTPException(409, "Chame o cliente antes de iniciar o pagamento.")
    if forma_pagamento not in {"debito", "credito", "pix"}:
        raise HTTPException(422, "Forma de pagamento invalida.")
    cliente = db.query(Usuario).filter(Usuario.id == pedido.usuario_id,
        Usuario.role.in_(["cliente", "visitante"]), Usuario.ativo.is_(True)).first()
    if not cliente:
        raise HTTPException(409, "A conta do cliente nao esta mais ativa.")

    cliente_ctx = {"id": cliente.id, "nome": cliente.nome, "email": cliente.email, "role": cliente.role}
    itens = json.loads(pedido.itens_json)
    venda_dados = {"carrinho_json": json.dumps([{"produto_id": item["produto_id"], "quantidade": item["quantidade"]} for item in itens]),
        "observacao": "Pedido " + pedido.codigo, "funcionario_comprador_id": "",
        "desconto_manual_percentual": "", "cortesia": "false", "forma_pagamento": forma_pagamento,
        "forma_pagamento_2": "", "valor_pagamento_1": "", "valor_pagamento_2": "", "filial": pedido.filial}
    total_centavos = round(float(pedido.total) * 100)
    try:
        if forma_pagamento == "pix":
            from app.pix import gerar_pix
            resultado_pix = gerar_pix(pedido.total)
            pedido.qr_url = resultado_pix["copia_cola"]
            pedido.operacao_rfid_id = None
            pedido.status = "pagando"
            resultado = {"id": None, "status": "aguardando_recebimento_pix", **resultado_pix}
        else:
            resultado = obter_rfid().iniciar("pagar", cliente.id, total_centavos, venda_dados, cliente_ctx)
            pedido.operacao_rfid_id = resultado["id"]
        pedido.status = "pagando"
        db.commit()
    except RFIDError as exc:
        db.rollback()
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    return RedirectResponse("/admin/pedidos-clientes", status_code=303)

@router.get("/admin/pedidos-clientes/{codigo}/qr")
def qr_pedido_admin(codigo: str, db: Session = Depends(get_db), usuario=Depends(get_admin)):
    pedido = db.query(PedidoCliente).filter_by(codigo=codigo.upper()).first()
    if not pedido or not pedido.qr_url:
        raise HTTPException(404, "QR Code nao encontrado.")
    import qrcode
    from qrcode.image.svg import SvgPathImage
    imagem = BytesIO()
    qrcode.make(pedido.qr_url, image_factory=SvgPathImage).save(imagem)
    return Response(imagem.getvalue(), media_type="image/svg+xml", headers={"Cache-Control":"no-store"})

@router.post("/admin/pedidos-clientes/{codigo}/confirmar-pix")
def confirmar_pix_pedido_cliente(codigo: str, db: Session = Depends(get_db), usuario=Depends(get_admin)):
    pedido = db.query(PedidoCliente).filter_by(codigo=codigo.upper()).with_for_update().first()
    if not pedido:
        raise HTTPException(404, "Pedido nao encontrado.")
    if pedido.status != "pagando" or not pedido.qr_url:
        raise HTTPException(409, "Este pedido nao aguarda confirmacao de Pix.")

    cliente = db.query(Usuario).filter(
        Usuario.id == pedido.usuario_id,
        Usuario.role.in_(["cliente", "visitante"]),
        Usuario.ativo.is_(True),
    ).first()
    if not cliente:
        raise HTTPException(409, "A conta do cliente nao esta mais ativa.")

    itens = json.loads(pedido.itens_json)
    venda_dados = {
        "carrinho_json": json.dumps([{"produto_id": item["produto_id"], "quantidade": item["quantidade"]} for item in itens]),
        "observacao": "Pedido " + pedido.codigo,
        "funcionario_comprador_id": "",
        "desconto_manual_percentual": "",
        "cortesia": "false",
        "forma_pagamento": "pix",
        "forma_pagamento_2": "",
        "valor_pagamento_1": "",
        "valor_pagamento_2": "",
        "filial": pedido.filial,
    }
    cliente_ctx = {"id": cliente.id, "nome": cliente.nome, "email": cliente.email, "role": cliente.role}
    try:
        from app.controllers.pdv_controller import finalizar_venda
        db.info["rfid_venda"] = True
        # O recebimento já foi conferido; registre a venda mesmo se o saldo
        # caiu desde a criação do pedido. O estoque poderá ficar negativo.
        db.info["pix_recebido_pedido_cliente"] = True
        resposta = finalizar_venda(request=None, db=db, usuario=cliente_ctx, **venda_dados)
        if not resposta.headers.get("location", "").startswith("/pdv/venda/"):
            raise ValueError("Nao foi possivel concluir a venda. Confira o estoque.")
        pedido.status = "pago"
        pedido.qr_url = None
        pedido.operacao_rfid_id = None
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    return RedirectResponse("/admin/pedidos-clientes", status_code=303)
