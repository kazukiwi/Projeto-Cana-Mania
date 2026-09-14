from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.venda import ItemVenda

router = APIRouter(prefix="/api/v1/produtos", tags=["Mais Vendidos API"])


@router.get("/mais-vendidos")
def mais_vendidos(db: Session = Depends(get_db)):

    # 🔥 Agrupamento base
    resultados = (
        db.query(
            ItemVenda.produto_id,
            ItemVenda.produto_nome.label("nome"),
            func.sum(ItemVenda.quantidade).label("vendas"),
            func.sum(ItemVenda.quantidade * ItemVenda.preco_unitario).label("receita"),
        )
        .group_by(ItemVenda.produto_id, ItemVenda.produto_nome)
        .all()
    )

    # total geral para percentual
    total_geral = sum(r.vendas for r in resultados) if resultados else 0

    produtos = []

    for r in resultados:
        vendas = r.vendas or 0
        receita = r.receita or 0

        produtos.append({
            "id": r.produto_id,
            "nome": r.nome,
            "codigo": f"PROD-{r.produto_id}",
            "categoria": "Geral",  # se quiser, depois liga com tabela categoria
            "vendas": vendas,
            "receita": float(receita),
            "precoMedio": (receita / vendas) if vendas else 0,
            "percentual": round((vendas / total_geral) * 100, 2) if total_geral else 0
        })

    # ordena por vendas (igual seu JS espera)
    produtos.sort(key=lambda x: x["vendas"], reverse=True)

    return produtos