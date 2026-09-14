from fastapi import APIRouter

router = APIRouter(
    prefix="/vendas",
    tags=["Vendas"]
)

@router.get("/")
def vendas():
    return {"msg": "Página de vendas"}

from fastapi import Depends, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.produtos import Produto
from app.models.venda import Venda

@router.post("/nova")
def nova_venda(
    produto_id: int = Form(...),
    quantidade: int = Form(...),
    db: Session = Depends(get_db)
):

    produto = db.query(Produto).filter(
        Produto.id == produto_id
    ).first()

    if not produto:
        return {"erro": "Produto não encontrado"}

    if produto.estoque_atual < quantidade:
        return {"erro": "Estoque insuficiente"}

    produto.estoque_atual -= quantidade

    venda = Venda(
        produto_id=produto.id,
        quantidade=quantidade,
        valor_unitario=produto.preco
    )

    db.add(venda)
    db.commit()

    return {"msg": "Venda registrada"}




@router.get("/historico")
def historico(
    pagina: int = 1,
    por_pagina: int = 10,
    db: Session = Depends(get_db)
):
    skip = (pagina - 1) * por_pagina

    vendas = (
        db.query(Venda)
        .offset(skip)
        .limit(por_pagina)
        .all()
    )

    return vendas