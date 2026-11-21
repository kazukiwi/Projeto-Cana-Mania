"""Cadastro, consulta, recarga e compra demonstrativa por RFID."""
import json
import base64
from io import BytesIO
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_admin, get_usuario_logado
from app.database import get_db
from app.models.categoria import Categoria
from app.models.produtos import Produto, CATEGORIAS_PDV
from app.models.rfid import CartaoRFID, OperacaoRFID
from app.models.usuario import Usuario
from app.services.rfid_service import RFIDError, obter_rfid
from app.services.qr_pagamento import qr_pagamento

router = APIRouter(tags=["RFID saldo ficticio"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _uid(uid: str) -> str:
    value = (uid or "").strip().upper()
    if not 8 <= len(value) <= 32 or any(char not in "0123456789ABCDEF" for char in value):
        raise HTTPException(422, "UID RFID invalido.")
    return value


def _centavos(data, field="centavos", minimum=1, maximum=2147483647):
    value = data.get(field) if isinstance(data, dict) else None
    if type(value) is not int or not minimum <= value <= maximum:
        raise HTTPException(422, "Valor em centavos invalido.")
    return value


@router.get("/admin/cartoes-rfid")
def pagina_cartoes(request: Request, admin=Depends(get_admin), db: Session = Depends(get_db)):
    cartoes = db.query(CartaoRFID).order_by(CartaoRFID.nome).all()
    return templates.TemplateResponse(request, "rfid/cartoes.html", {"request": request, "usuario": admin, "cartoes": cartoes})


@router.post("/rfid/operacoes")
async def iniciar(request: Request, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    try:
        data = await request.json()
    except ValueError:
        raise HTTPException(400, "JSON invalido.") from None
    tipo = data.get("tipo") if isinstance(data, dict) else None
    if usuario.get("role") in {"cliente", "visitante"}:
        if tipo != "pagar" or data.get("forma_pagamento") not in {"debito", "credito", "pix"}:
            raise HTTPException(403, "Operação não permitida para clientes.")
        if data.get("cortesia", "false") != "false" or data.get("desconto_manual_percentual") or data.get("funcionario_comprador_id"):
            raise HTTPException(403, "Descontos e cortesias são definidos pela equipe.")
    if tipo == "identificar" and usuario.get("role") != "admin":
        raise HTTPException(403, "Somente administradores podem identificar cartoes para cadastro ou recarga.")
    if tipo not in {"identificar", "pagar"}:
        raise HTTPException(422, "Tipo de operacao RFID invalido.")
    cents = _centavos(data, minimum=0, maximum=99999999) if tipo == "pagar" else 0
    if tipo == "pagar":
        try:
            items = json.loads(data.get("carrinho_json", "[]"))
        except (TypeError, ValueError):
            raise HTTPException(422, "Carrinho invalido.") from None
        if not isinstance(items, list) or not items:
            raise HTTPException(422, "Carrinho vazio.")
        total = Decimal("0.00")
        for item in items:
            if not isinstance(item, dict):
                raise HTTPException(422, "Item do carrinho invalido.")
            try:
                product_id, quantity = int(item.get("produto_id")), int(item.get("quantidade"))
            except (ValueError, TypeError):
                raise HTTPException(422, "Produto ou quantidade invalida.") from None
            product = db.query(Produto).join(Categoria, Produto.categoria_id == Categoria.id).filter(
                Produto.id == product_id, Produto.ativo.is_(True), func.lower(Categoria.nome).in_(CATEGORIAS_PDV)
            ).first()
            if not product or not 1 <= quantity <= 10000:
                raise HTTPException(422, "Produto ou quantidade invalida.")
            total += Decimal(str(product.preco)) * quantity
        try:
            discount = Decimal("100") if data.get("cortesia") == "true" else Decimal(str(data.get("desconto_manual_percentual") or "0"))
            employee_id = data.get("funcionario_comprador_id")
            if employee_id and data.get("cortesia") != "true":
                employee = db.query(Usuario).filter_by(id=int(employee_id), role="funcionario", ativo=True).first()
                if not employee:
                    raise HTTPException(422, "Funcionario invalido.")
                discount = min(Decimal("100"), discount + Decimal("15"))
        except (InvalidOperation, TypeError, ValueError):
            raise HTTPException(422, "Desconto invalido.") from None
        if not discount.is_finite() or not Decimal("0") <= discount <= Decimal("100"):
            raise HTTPException(422, "Desconto invalido.")
        expected_cents = int((total * (Decimal("100") - discount) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)
        if not 0 <= expected_cents <= 99999999 or cents != expected_cents:
            raise HTTPException(409, "O total calculado pelo servidor difere do carrinho. Atualize e tente novamente.")
        cents = expected_cents
    try:
        venda_dados = None
        if tipo == "pagar":
            keys = ("carrinho_json", "observacao", "funcionario_comprador_id", "desconto_manual_percentual", "cortesia", "forma_pagamento", "forma_pagamento_2", "valor_pagamento_1", "valor_pagamento_2", "filial")
            venda_dados = {key: str(data.get(key, "")) for key in keys}
            if any(venda_dados[key] for key in ("forma_pagamento_2", "valor_pagamento_1", "valor_pagamento_2")):
                raise HTTPException(422, "Pagamento dividido não disponível para RFID.")
        modo = data.get("confirmacao", "cartao")
        if tipo == "pagar" and modo == "qr":
            if venda_dados["forma_pagamento"] not in {"pix", "cortesia"}:
                raise HTTPException(422, "O QR Code está disponível para Pix e cortesia.")
            import qrcode
            from qrcode.image.svg import SvgPathImage
            result = qr_pagamento.iniciar(int(usuario["id"]), cents, venda_dados, usuario)
            url = str(request.base_url).rstrip("/") + "/confirmar-qr/" + result["id"]
            result["qr_url"] = url
            image = BytesIO()
            qrcode.make(url, image_factory=SvgPathImage).save(image)
            result["qr_code"] = "data:image/svg+xml;base64," + base64.b64encode(image.getvalue()).decode("ascii")
        elif modo == "cartao" or tipo == "identificar":
            result = obter_rfid().iniciar(tipo, int(usuario["id"]), cents, venda_dados, usuario)
        else:
            raise HTTPException(422, "Modo de confirmação inválido.")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except RFIDError as exc:
        raise HTTPException(503, str(exc)) from None
    return JSONResponse(result, status_code=201, headers={"Cache-Control": "no-store"})


@router.get("/rfid/operacoes/{op_id}")
def status_operacao(op_id: str, usuario=Depends(get_usuario_logado)):
    qr_pagamento.expirar(op_id)
    result = obter_rfid().consultar(op_id, int(usuario["id"]))
    if not result:
        raise HTTPException(404, "Operacao RFID nao encontrada.")
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.get("/confirmar-qr/{op_id}", response_class=HTMLResponse)
def abrir_confirmacao_qr(op_id: str):
    if len(op_id) != 32 or any(c not in "0123456789abcdef" for c in op_id):
        raise HTTPException(404, "Código inválido.")
    return HTMLResponse('''<!doctype html><html lang="pt-br"><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>Confirmação Cana Mania</title><body style="font-family:sans-serif;text-align:center;padding:2rem"><h1>Cana Mania</h1><p id="mensagem">Confirmando...</p><script>fetch(location.pathname,{method:'POST'}).then(r=>r.json()).then(d=>{document.getElementById('mensagem').textContent=d.mensagem}).catch(()=>{document.getElementById('mensagem').textContent='Não foi possível confirmar. Peça ajuda ao atendente.'});</script></body></html>''', headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.post("/confirmar-qr/{op_id}")
def confirmar_qr(op_id: str):
    resultado = qr_pagamento.confirmar(op_id)
    mensagens = {"brinde": "Parabéns! Você ganhou um brinde!", "aprovado": "Pagamento simulado confirmado!", "expirado": "Este QR Code expirou. Peça outro ao atendente.", "invalido": "Este QR Code é inválido ou já foi utilizado.", "erro": "Não foi possível concluir a venda. Peça ajuda ao atendente."}
    return JSONResponse({"status": resultado, "mensagem": mensagens[resultado]}, headers={"Cache-Control": "no-store"})


@router.post("/rfid/operacoes/{op_id}/cancelar")
def cancelar(op_id: str, usuario=Depends(get_usuario_logado)):
    try:
        return obter_rfid().cancelar(op_id, int(usuario["id"]))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except RFIDError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("/admin/cartoes-rfid/operacoes/{op_id}/concluir")
async def concluir_identificacao(op_id: str, request: Request, admin=Depends(get_admin), db: Session = Depends(get_db)):
    op = db.query(OperacaoRFID).filter_by(operacao_id=op_id, operador_id=int(admin["id"])).first()
    if not op or op.tipo not in {"identificar", "cadastro", "recarga"}:
        raise HTTPException(404, "Leitura RFID nao encontrada.")
    try:
        data = await request.json()
    except ValueError:
        raise HTTPException(400, "JSON invalido.") from None
    action = data.get("acao") if isinstance(data, dict) else None
    name = data.get("nome", "") if isinstance(data, dict) else ""
    cents = _centavos(data) if action in {"cadastro", "recarga"} else 0
    if action == "cadastro" and db.query(CartaoRFID).filter_by(uid=op.uid).first():
        raise HTTPException(409, "Este cartao ja esta cadastrado.")
    if action == "recarga" and not db.query(CartaoRFID).filter_by(uid=op.uid, ativo=True).first():
        raise HTTPException(404, "Cartao nao cadastrado ou inativo.")
    try:
        result = obter_rfid().completar_identificacao(op_id, int(admin["id"]), action, name, cents)
    except IntegrityError:
        raise HTTPException(409, "Este cartão já foi cadastrado por outra operação.") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except RFIDError as exc:
        raise HTTPException(503, str(exc)) from None
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.get("/admin/cartoes-rfid/{uid}/historico")
def historico(uid: str, admin=Depends(get_admin), db: Session = Depends(get_db)):
    uid = _uid(uid)
    card = db.query(CartaoRFID).filter_by(uid=uid).first()
    if not card:
        raise HTTPException(404, "Cartao nao cadastrado.")
    rows = db.query(OperacaoRFID).filter_by(cartao_id=card.id).order_by(OperacaoRFID.id.desc()).limit(100).all()
    return [{"id": row.operacao_id, "tipo": row.tipo, "status": row.status,
             "valor_centavos": row.valor_centavos, "saldo_antes": row.saldo_antes,
             "saldo_depois": row.saldo_depois, "criado_em": row.criado_em.isoformat() if row.criado_em else None}
            for row in rows]


@router.post("/admin/cartoes-rfid/ping")
def ping(admin=Depends(get_admin)):
    try:
        if not obter_rfid().ping():
            raise HTTPException(504, "Arduino nao respondeu PONG.")
    except RFIDError as exc:
        raise HTTPException(503, str(exc)) from None
    return {"status": "PONG"}


@router.get("/pdv/rfid/recibo/{op_id}")
def recibo_compra(op_id: str, request: Request, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    op = db.query(OperacaoRFID).filter_by(operacao_id=op_id, operador_id=int(usuario["id"]), tipo="pagar").first()
    if not op:
        raise HTTPException(404, "Operacao de compra nao encontrada.")
    return templates.TemplateResponse(request, "pdv/rfid_recibo.html", {"request": request, "usuario": usuario, "operacao": op})
