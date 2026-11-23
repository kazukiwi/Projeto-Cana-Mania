"""Cardápio, compras e comprovantes do Canamaniaco."""
from fastapi import APIRouter, Depends, HTTPException, Request
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
    return templates.TemplateResponse(request, "cliente/cardapio.html", {
        "request": request, "usuario": usuario, "produtos": produtos_do_cardapio(db),
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