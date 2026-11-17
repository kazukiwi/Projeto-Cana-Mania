"""Cadastro, consulta, recarga e compra demonstrativa por RFID."""
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
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
    if tipo == "identificar" and usuario.get("role") != "admin":
        raise HTTPException(403, "Somente administradores podem identificar cartoes para cadastro ou recarga.")
    if tipo not in {"identificar", "pagar"}:
        raise HTTPException(422, "Tipo de operacao RFID invalido.")
    cents = _centavos(data) if tipo == "pagar" else 0
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
            discount = Decimal(str(data.get("desconto_percentual") or "0"))
            employee_id = data.get("funcionario_comprador_id")
            if employee_id:
                employee = db.query(Usuario).filter_by(id=int(employee_id), role="funcionario", ativo=True).first()
                if not employee:
                    raise HTTPException(422, "Funcionario invalido.")
                discount = min(Decimal("100"), discount + Decimal("15"))
        except (InvalidOperation, TypeError, ValueError):
            raise HTTPException(422, "Desconto invalido.") from None
        if not discount.is_finite() or not Decimal("0") <= discount <= Decimal("100"):
            raise HTTPException(422, "Desconto invalido.")
        expected_cents = int((total * (Decimal("100") - discount) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)
        if not 1 <= expected_cents <= 99999999 or cents != expected_cents:
            raise HTTPException(409, "O total calculado pelo servidor difere do carrinho. Atualize e tente novamente.")
        cents = expected_cents
    try:
        result = obter_rfid().iniciar(tipo, int(usuario["id"]), cents)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except RFIDError as exc:
        raise HTTPException(503, str(exc)) from None
    return JSONResponse(result, status_code=201, headers={"Cache-Control": "no-store"})


@router.get("/rfid/operacoes/{op_id}")
def status_operacao(op_id: str, usuario=Depends(get_usuario_logado)):
    result = obter_rfid().consultar(op_id, int(usuario["id"]))
    if not result:
        raise HTTPException(404, "Operacao RFID nao encontrada.")
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


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
