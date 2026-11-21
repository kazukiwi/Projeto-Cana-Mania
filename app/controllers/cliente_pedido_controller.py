"""Catálogo e comprovantes do cliente autenticado."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_usuario_logado
from app.database import get_db
from app.models.categoria import Categoria
from app.models.filial import FILIAIS
from app.models.produtos import Produto, CATEGORIAS_PDV
from app.models.venda import Venda

router = APIRouter(prefix="/cliente", tags=["Pedidos"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def pedidos(request: Request, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    if usuario.get("role") != "cliente":
        raise HTTPException(403, "Área exclusiva para clientes.")
    produtos = (db.query(Produto).join(Categoria).filter(
        Produto.ativo.is_(True), func.lower(Categoria.nome).in_(CATEGORIAS_PDV)
    ).order_by(Produto.nome).all())
    vendas = db.query(Venda).filter_by(usuario_id=usuario["id"]).order_by(Venda.id.desc()).limit(20).all()
    return templates.TemplateResponse(request, "cliente/pedidos.html", {
        "request": request, "usuario": usuario, "produtos": produtos,
        "filiais": FILIAIS, "vendas": vendas,
    })
