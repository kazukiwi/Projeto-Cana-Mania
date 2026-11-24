"""Cardápio, compras e comprovantes do Canamaniaco."""
import json
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_usuario_logado
from app.database import get_db
from app.models.categoria import Categoria
from app.models.filial import FILIAIS
from app.models.produtos import Produto, CATEGORIAS_PDV
from app.models.venda import Venda
from app.models.pedido_cliente import PedidoCliente

router = APIRouter(prefix="/cliente", tags=["Canamaniaco"])
templates = Jinja2Templates(directory="app/templates")


def exigir_canamaniaco(usuario):
    if usuario.get("role") not in {"cliente", "visitante"}:
        raise HTTPException(403, "Área exclusiva para Canamaniacos.")


def produtos_do_cardapio(db: Session):
    return (db.query(Produto).join(Categoria).filter(
        Produto.ativo.is_(True),
        # Usa as mesmas categorias que o PDV da equipe oferece para venda.
        func.lower(Categoria.nome).in_(CATEGORIAS_PDV)
    ).order_by(Categoria.nome, Produto.nome).all())


@router.get("/")
def inicio(request: Request, usuario=Depends(get_usuario_logado)):
    exigir_canamaniaco(usuario)
    return RedirectResponse("/cliente/cardapio", status_code=303)


@router.get("/cardapio")
def cardapio(request: Request, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    exigir_canamaniaco(usuario)
    produtos = produtos_do_cardapio(db)
    grupos = {}
    for produto in produtos:
        categoria = produto.categoria.nome if produto.categoria else "Canamania"
        categoria_id = produto.categoria_id if produto.categoria else "sem-categoria"
        if categoria_id not in grupos:
            grupos[categoria_id] = {"id": categoria_id, "nome": categoria, "produtos": []}
        grupos[categoria_id]["produtos"].append(produto)
    return templates.TemplateResponse(request, "cliente/cardapio_organizado.html", {
        "request": request, "usuario": usuario, "categorias_cardapio": list(grupos.values()),
    })


@router.get("/pdv")
def ponto_de_compra(request: Request, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    exigir_canamaniaco(usuario)
    produtos = produtos_do_cardapio(db)
    vendas = db.query(Venda).filter_by(usuario_id=usuario["id"]).order_by(Venda.id.desc()).limit(20).all()
    return templates.TemplateResponse(request, "cliente/pedidos.html", {
        "request": request, "usuario": usuario, "produtos": produtos,
        "filiais": FILIAIS, "vendas": vendas,
    })

@router.post("/pedidos")
async def criar_pedido(request: Request, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    exigir_canamaniaco(usuario)
    try:
        dados = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(400, "Dados do pedido invalidos.")
    if not isinstance(dados, dict):
        raise HTTPException(400, "Dados do pedido invalidos.")
    filial = dados.get("filial")
    itens = dados.get("itens")
    if filial not in FILIAIS or not isinstance(itens, list) or not itens:
        raise HTTPException(400, "Selecione uma loja e ao menos um produto.")

    snapshot = []
    total_centavos = 0
    for item in itens:
        try:
            produto_id = int(item.get("produto_id"))
            quantidade = int(item.get("quantidade"))
        except (AttributeError, TypeError, ValueError):
            raise HTTPException(400, "Item do pedido invalido.")
        if not 1 <= quantidade <= 99:
            raise HTTPException(400, "A quantidade deve ser de 1 a 99.")
        produto = (db.query(Produto).join(Categoria).filter(
            Produto.id == produto_id, Produto.ativo.is_(True),
            func.lower(Categoria.nome).in_(CATEGORIAS_PDV)
        ).first())
        if not produto:
            raise HTTPException(400, "Um dos produtos nao esta mais dispon?vel.")
        sabores = []
        if produto.nome.strip().casefold() == "cana mix":
            sabores_recebidos = item.get("sabores", [])
            if not isinstance(sabores_recebidos, list) or len(sabores_recebidos) > 2:
                raise HTTPException(400, "O Cana Mix permite escolher no maximo dois sabores.")
            for sabor in sabores_recebidos:
                if not isinstance(sabor, str):
                    raise HTTPException(400, "Confira os sabores escolhidos para o Cana Mix.")
                sabor = sabor.strip()
                if not sabor or len(sabor) > 40 or any(s.casefold() == sabor.casefold() for s in sabores):
                    raise HTTPException(400, "Confira os sabores escolhidos para o Cana Mix.")
                sabores.append(sabor)
        preco_centavos = round(float(produto.preco or 0) * 100)
        subtotal = preco_centavos * quantidade
        total_centavos += subtotal
        nome_pedido = produto.nome + (f" ({', '.join(sabores)})" if sabores else "")
        snapshot.append({"produto_id": produto.id, "nome": nome_pedido, "sabores": sabores,
                         "quantidade": quantidade, "preco_unitario": preco_centavos / 100,
                         "subtotal": subtotal / 100})

    pedido = None
    for _ in range(5):
        codigo = "CM-" + secrets.token_hex(3).upper()
        if not db.query(PedidoCliente.id).filter_by(codigo=codigo).first():
            pedido = PedidoCliente(codigo=codigo, usuario_id=usuario["id"],
                nome_cliente=usuario.get("nome") or "Canamaniaco",
                itens_json=json.dumps(snapshot, ensure_ascii=False), filial=filial,
                total=total_centavos / 100, status="aguardando")
            break
    if pedido is None:
        raise HTTPException(503, "Nao foi possivel gerar o codigo do pedido. Tente novamente.")
    db.add(pedido)
    db.commit()
    return JSONResponse({"codigo": pedido.codigo, "status": pedido.status}, status_code=201)


@router.get("/pedidos/{codigo}")
def consultar_pedido(codigo: str, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    exigir_canamaniaco(usuario)
    pedido = db.query(PedidoCliente).filter_by(codigo=codigo.upper(), usuario_id=usuario["id"]).first()
    if not pedido:
        raise HTTPException(404, "Pedido nao encontrado.")
    resposta = {"codigo": pedido.codigo, "status": pedido.status, "qr_url": pedido.qr_url}
    if pedido.operacao_rfid_id:
        from app.services.qr_pagamento import qr_pagamento
        from app.models.rfid import OperacaoRFID
        qr_pagamento.expirar(pedido.operacao_rfid_id)
        operacao = db.query(OperacaoRFID).filter_by(operacao_id=pedido.operacao_rfid_id).first()
        if operacao:
            resposta["pagamento"] = {"id": operacao.operacao_id, "status": operacao.status,
                "erro": operacao.erro, "venda_id": operacao.venda_id}
    return resposta


@router.get("/pedidos/{codigo}/qr")
def qr_pedido_cliente(codigo: str, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    exigir_canamaniaco(usuario)
    pedido = db.query(PedidoCliente).filter_by(codigo=codigo.upper(), usuario_id=usuario["id"]).first()
    if not pedido or not pedido.qr_url:
        raise HTTPException(404, "QR Code nao encontrado.")
    import qrcode
    from io import BytesIO
    from qrcode.image.svg import SvgPathImage
    imagem = BytesIO()
    qrcode.make(pedido.qr_url, image_factory=SvgPathImage).save(imagem)
    return Response(imagem.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
