from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_admin, get_usuario_logado
from app.database import get_db
from app.models.filial import EstoqueFilial, FILIAIS
from app.models.produtos import Produto, CATEGORIAS_CONSUMO, LIMITE_ESTOQUE_BAIXO
from app.models.categoria import Categoria

router = APIRouter(prefix="/estoque", tags=["Estoque por filial"])
templates = Jinja2Templates(directory="app/templates")


def garantir_estoque_filiais(db: Session, produto: Produto | None = None) -> None:
    """Cria os saldos ausentes sem alterar o inventário já distribuído.

    Produtos legados iniciam na fábrica, de onde o administrador os envia para as lojas.
    """
    produtos = [produto] if produto else (
        db.query(Produto)
        .join(Categoria, Produto.categoria_id == Categoria.id, isouter=True)
        .filter(Produto.ativo == True, or_(Categoria.nome.is_(None), ~func.lower(Categoria.nome).in_(CATEGORIAS_CONSUMO)))
        .all()
    )
    alterou = False
    for item in produtos:
        existentes = {saldo.filial for saldo in item.estoques_filiais}
        for filial in FILIAIS:
            if filial not in existentes:
                quantidade = item.estoque_atual if filial == "Carrão (Fábrica)" and not existentes else 0
                db.add(EstoqueFilial(produto_id=item.id, filial=filial, quantidade=quantidade))
                alterou = True
    if alterou:
        db.commit()


@router.get("/")
def painel_estoque(request: Request, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    garantir_estoque_filiais(db)
    produtos = (
        db.query(Produto)
        .join(Categoria, Produto.categoria_id == Categoria.id, isouter=True)
        .filter(Produto.ativo == True, or_(Categoria.nome.is_(None), ~func.lower(Categoria.nome).in_(CATEGORIAS_CONSUMO)))
        .order_by(Produto.nome)
        .all()
    )
    saldos = (
        db.query(EstoqueFilial)
        .join(Produto, EstoqueFilial.produto_id == Produto.id)
        .join(Categoria, Produto.categoria_id == Categoria.id, isouter=True)
        .filter(Produto.ativo == True, or_(Categoria.nome.is_(None), ~func.lower(Categoria.nome).in_(CATEGORIAS_CONSUMO)))
        .all()
    )
    por_produto = {(saldo.produto_id, saldo.filial): saldo.quantidade for saldo in saldos}
    resumo = {filial: sum(por_produto.get((produto.id, filial), 0) for produto in produtos) for filial in FILIAIS}
    alertas = [
        {"produto": produto, "filial": filial, "quantidade": por_produto.get((produto.id, filial), 0)}
        for produto in produtos for filial in FILIAIS
        if 0 < por_produto.get((produto.id, filial), 0) <= LIMITE_ESTOQUE_BAIXO
    ]
    return templates.TemplateResponse(request, "estoque/index.html", {
        "request": request, "usuario": usuario, "produtos": produtos, "filiais": FILIAIS,
        "por_produto": por_produto, "resumo": resumo, "alertas": alertas,
    })


@router.post("/transferir")
def transferir_estoque(
    produto_id: int = Form(...), origem: str = Form(...), destino: str = Form(...), quantidade: int = Form(...),
    db: Session = Depends(get_db), admin=Depends(get_admin),
):
    if origem not in FILIAIS or destino not in FILIAIS or origem == destino or quantidade <= 0:
        return RedirectResponse("/estoque?erro=dados", status_code=303)
    produto = db.query(Produto).filter(Produto.id == produto_id, Produto.ativo == True).first()
    if not produto or produto.eh_consumo:
        return RedirectResponse("/estoque?erro=produto", status_code=303)
    garantir_estoque_filiais(db, produto)
    origem_saldo = db.query(EstoqueFilial).filter_by(produto_id=produto_id, filial=origem).with_for_update().first()
    destino_saldo = db.query(EstoqueFilial).filter_by(produto_id=produto_id, filial=destino).with_for_update().first()
    if not origem_saldo or origem_saldo.quantidade < quantidade:
        return RedirectResponse("/estoque?erro=saldo", status_code=303)
    origem_saldo.quantidade -= quantidade
    destino_saldo.quantidade += quantidade
    db.commit()
    return RedirectResponse("/estoque?transferido=ok", status_code=303)
