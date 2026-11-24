from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_usuario_logado
from app.database import get_db
from app.models.cliente import Cliente
from app.models.filial import EstoqueFilial
from app.models.produtos import Produto, EstoqueVariacao
from app.models.venda import ItemVenda, Venda

router = APIRouter(prefix="/insights", tags=["Insights"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def painel_insights(
    request: Request,
    cliente_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
):
    agora = datetime.utcnow()
    trinta_dias = agora - timedelta(days=30)
    sete_dias = agora - timedelta(days=7)

    vendas_periodo = db.query(Venda).filter(Venda.criado_em >= trinta_dias).all()
    receita_30 = sum(float(v.total_liquido or 0) for v in vendas_periodo)
    dias = [(agora - timedelta(days=i)).date() for i in reversed(range(7))]
    vendas_por_dia = {dia: {"quantidade": 0, "receita": 0.0} for dia in dias}
    for venda in db.query(Venda).filter(Venda.criado_em >= sete_dias).all():
        dia = (venda.criado_em - timedelta(hours=3)).date() if venda.criado_em else None
        if dia in vendas_por_dia:
            vendas_por_dia[dia]["quantidade"] += 1
            vendas_por_dia[dia]["receita"] += float(venda.total_liquido or 0)
    max_receita = max((d["receita"] for d in vendas_por_dia.values()), default=0) or 1
    grafico = [{"dia": dia.strftime("%d/%m"), "receita": dados["receita"], "altura": max(8, round(dados["receita"] / max_receita * 100)), "vendas": dados["quantidade"]} for dia, dados in vendas_por_dia.items()]

    vendidos = dict(
        db.query(ItemVenda.produto_id, func.coalesce(func.sum(ItemVenda.quantidade), 0))
        .join(Venda, ItemVenda.venda_id == Venda.id)
        .filter(Venda.criado_em >= trinta_dias, ItemVenda.produto_id.isnot(None))
        .group_by(ItemVenda.produto_id).all()
    )
    saldos_filiais = dict(
        db.query(EstoqueFilial.produto_id, func.coalesce(func.sum(EstoqueFilial.quantidade), 0))
        .group_by(EstoqueFilial.produto_id).all()
    )
    produtos = db.query(Produto).filter(Produto.ativo == True).all()
    recomendacoes = []
    for produto in produtos:
        qtd_vendida = int(vendidos.get(produto.id, 0))
        if produto.eh_consumo or not qtd_vendida:
            continue
        estoque = int(saldos_filiais.get(produto.id, produto.estoque_atual or 0))
        if produto.possui_variacoes_tamanho:
            estoque = sum(int(v.estoque_atual or 0) for v in produto.estoques_variacoes)
        media_dia = qtd_vendida / 30
        previsao = round(media_dia * 7, 1)
        sugerido = max(0, int((media_dia * 14) - estoque + 0.999))
        recomendacoes.append({"nome": produto.nome, "estoque": estoque, "vendidos": qtd_vendida, "previsao": previsao, "sugerido": sugerido})
    recomendacoes.sort(key=lambda p: (p["sugerido"] == 0, -p["sugerido"], -p["vendidos"], p["nome"].lower()))

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.ativo == True).first() if cliente_id else None
    telefone_limpo = "".join(c for c in (cliente.telefone or "") if c.isdigit()) if cliente else ""
    whatsapp = ("https://wa.me/55" + telefone_limpo) if len(telefone_limpo) in (10, 11) else ("https://wa.me/" + telefone_limpo if len(telefone_limpo) > 11 else "")
    return templates.TemplateResponse(request, "insights.html", {
        "request": request, "usuario": usuario, "cliente_id": cliente_id,
        "cliente": cliente, "telefone_limpo": telefone_limpo, "whatsapp": whatsapp,
        "grafico": grafico, "receita_30": receita_30,
        "vendas_30": len(vendas_periodo), "previsao_7": round(len(vendas_periodo) / 30 * 7, 1),
        "recomendacoes": recomendacoes[:10],
    })