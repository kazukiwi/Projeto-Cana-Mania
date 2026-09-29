# ============================================================
# controllers/pdv_controller.py — Ponto de Venda
# ============================================================
# O PDV funciona assim:
# 1. GET /pdv        → tela com produtos + campo de cliente
# 2. O carrinho vive inteiro no JavaScript (sessionStorage)
# 3. POST /pdv/finalizar → recebe um JSON com os itens
#                          cria Venda + ItensVenda + baixa estoque
# ============================================================

import json
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, time, timedelta, timezone
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import Session as SessionLocal, get_db
from app.models.venda import FechamentoDiario, Venda, ItemVenda
from app.models.produtos import Produto, EstoqueTamanho, EstoqueVariacao, Tamanho, ordenar_tamanhos
from app.models.categoria import Categoria
from app.models.produtos import CATEGORIAS_PDV
from app.models.filial import EstoqueFilial, FILIAIS
from app.controllers.estoque_controller import garantir_estoque_filiais
from app.pix import gerar_pix
from app.auth import get_usuario_logado

router = APIRouter(prefix="/pdv", tags=["PDV"])
templates = Jinja2Templates(directory="app/templates")
FORMAS_PAGAMENTO = {"credito", "debito", "dinheiro", "pix", "convite"}

# O Brasil não adota horário de verão desde 2019. Usar UTC-3 evita depender do
# pacote tzdata, que não vem instalado em algumas instalações do Windows.
FUSO_HORARIO = timezone(timedelta(hours=-3), name="America/Sao_Paulo")


def fechar_dia(db: Session, data_referencia: date, automatico: bool = False) -> FechamentoDiario:
    """Cria ou atualiza o resumo de vendas de uma data, inclusive quando o total é zero."""
    # SQLite grava CURRENT_TIMESTAMP em UTC. Convertemos os limites do dia de
    # Brasília para UTC antes da consulta, para que uma venda feita às 22h não
    # seja contabilizada no dia seguinte.
    inicio = datetime.combine(data_referencia, time.min, tzinfo=FUSO_HORARIO)
    fim = inicio + timedelta(days=1)
    inicio_utc = inicio.astimezone(timezone.utc).replace(tzinfo=None)
    fim_utc = fim.astimezone(timezone.utc).replace(tzinfo=None)
    total, quantidade = (
        db.query(
            func.coalesce(func.sum(Venda.total_liquido), 0.0),
            func.count(Venda.id),
        )
        .filter(Venda.criado_em >= inicio_utc, Venda.criado_em < fim_utc)
        .one()
    )

    fechamento = db.query(FechamentoDiario).filter(FechamentoDiario.data == data_referencia).first()
    if not fechamento:
        fechamento = FechamentoDiario(data=data_referencia)
        db.add(fechamento)

    fechamento.total_vendido = round(float(total or 0.0), 2)
    fechamento.quantidade_vendas = int(quantidade or 0)
    fechamento.fechado_em = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
    fechamento.fechado_automaticamente = fechamento.fechado_automaticamente or automatico
    db.commit()
    db.refresh(fechamento)
    return fechamento


def executar_fechamento_automatico() -> None:
    """Fecha o dia atual e recupera somente o dia anterior se o sistema reiniciou."""
    agora = datetime.now(FUSO_HORARIO)
    db = SessionLocal()
    try:
        if agora.hour == 23 and agora.minute == 59:
            fechar_dia(db, agora.date(), automatico=True)
        else:
            ontem = agora.date() - timedelta(days=1)
            if not db.query(FechamentoDiario.id).filter(FechamentoDiario.data == ontem).first():
                fechar_dia(db, ontem, automatico=True)
    finally:
        db.close()


def obter_tamanho_id_item(item: dict) -> int | None:
    """Lê o identificador do tamanho; o nome não é uma fonte confiável."""
    tamanho_id = item.get("tamanho_id")
    if tamanho_id in (None, ""):
        return None
    try:
        tamanho_id = int(tamanho_id)
    except (TypeError, ValueError):
        raise ValueError("tamanho inválido")
    if tamanho_id <= 0:
        raise ValueError("tamanho inválido")
    return tamanho_id


def obter_cor_item(item: dict) -> str | None:
    cor = item.get("cor")
    if cor in (None, ""):
        return None
    cor = str(cor).strip()
    if not cor or len(cor) > 50:
        raise ValueError("cor inválida")
    return cor


@router.get("/")
def tela_pdv(
    request: Request,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    """
    Carrega a tela do PDV com todos os produtos ativos
    e a lista de clientes para o campo de busca.
    """
    produtos  = (
        db.query(Produto)
        .join(Categoria, Produto.categoria_id == Categoria.id)
        .filter(Produto.ativo == True, func.lower(Categoria.nome).in_(CATEGORIAS_PDV))
        .order_by(Produto.nome)
        .all()
    )
    tamanhos = ordenar_tamanhos(db.query(Tamanho).filter(Tamanho.ativo == True).all())
    garantir_estoque_filiais(db)
    # Os itens de consumo não têm estoque: exibimos o total vendido no dia.
    hoje = datetime.now(FUSO_HORARIO).date()
    inicio_hoje = datetime.combine(hoje, time.min, tzinfo=FUSO_HORARIO).astimezone(timezone.utc).replace(tzinfo=None)
    inicio_amanha = inicio_hoje + timedelta(days=1)
    fechamento_de_hoje = db.query(FechamentoDiario).filter(FechamentoDiario.data == hoje).first()
    # Depois de fechar o dia manualmente, o próximo consumo começa uma nova
    # contagem, sem apagar o histórico já consolidado.
    inicio_contagem = fechamento_de_hoje.fechado_em if fechamento_de_hoje else inicio_hoje
    vendas_hoje = dict(
        db.query(ItemVenda.produto_id, func.coalesce(func.sum(ItemVenda.quantidade), 0))
        .join(Venda, ItemVenda.venda_id == Venda.id)
        .filter(Venda.criado_em >= inicio_contagem, Venda.criado_em < inicio_amanha)
        .group_by(ItemVenda.produto_id)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "pdv/index.html",
        {
            "request":             request,
            "usuario":             usuario,
            "produtos":            produtos,
            "tamanhos":            tamanhos,
            "filiais": FILIAIS,
            "estoque_filiais": {
                (saldo.produto_id, saldo.filial): saldo.quantidade
                for saldo in (
                    db.query(EstoqueFilial)
                    .join(Produto, EstoqueFilial.produto_id == Produto.id)
                    .join(Categoria, Produto.categoria_id == Categoria.id)
                    .filter(Produto.ativo == True, func.lower(Categoria.nome) == "cookies")
                    .all()
                )
            },
            "vendas_hoje": vendas_hoje,
        }
    )


@router.post("/pix")
def gerar_pix_carrinho(
    carrinho_json: str = Form(..., max_length=100000),
    filial: str = Form(...),
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado),
):
    """Gera uma solicitação de pagamento; não registra venda nem confirma pagamento."""
    if filial not in FILIAIS:
        raise HTTPException(status_code=400, detail="Loja inválida.")
    try:
        itens = json.loads(carrinho_json)
        if not isinstance(itens, list) or not 1 <= len(itens) <= 500:
            raise ValueError()
        quantidades = {}
        for item in itens:
            if not isinstance(item, dict):
                raise ValueError()
            produto_id, quantidade = item.get("produto_id"), item.get("quantidade")
            if type(produto_id) is not int or type(quantidade) is not int or produto_id <= 0 or not 1 <= quantidade <= 100000:
                raise ValueError()
            quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Carrinho inválido. Confira os itens e quantidades.") from None

    total = Decimal("0")
    for produto_id, quantidade in quantidades.items():
        produto = (
            db.query(Produto).join(Categoria, Produto.categoria_id == Categoria.id)
            .filter(Produto.id == produto_id, Produto.ativo == True, func.lower(Categoria.nome).in_(CATEGORIAS_PDV))
            .first()
        )
        if not produto:
            raise HTTPException(status_code=400, detail="Um produto não está mais disponível.")
        if not produto.eh_consumo:
            saldo = db.query(EstoqueFilial).filter(
                EstoqueFilial.produto_id == produto_id, EstoqueFilial.filial == filial,
            ).first()
            if not saldo or saldo.quantidade < quantidade:
                raise HTTPException(status_code=400, detail="Estoque insuficiente na loja selecionada.")
        try:
            preco = Decimal(str(produto.preco))
        except InvalidOperation:
            raise HTTPException(status_code=400, detail="Produto sem preço válido.") from None
        if not preco.is_finite() or preco < 0:
            raise HTTPException(status_code=400, detail="Produto com preço inválido.")
        total += preco * quantidade
    try:
        return JSONResponse(gerar_pix(total), headers={"Cache-Control": "no-store"})
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from None


@router.post("/finalizar")
def finalizar_venda(
    request: Request,
    carrinho_json: str = Form(...),  # JSON serializado pelo JS
    observacao: str    = Form(""),
    forma_pagamento: str = Form(""),
    filial: str        = Form("Pinheiros"),
    db: Session        = Depends(get_db),
    usuario            = Depends(get_usuario_logado)
):
    """
    Recebe o carrinho como JSON, valida e persiste a venda.

    Formato esperado do carrinho_json:
    [
        {"produto_id": 1, "nome": "Caneta", "preco": 2.50, "quantidade": 3},
        {"produto_id": 2, "nome": "Caderno", "preco": 15.00, "quantidade": 1}
    ]
    """
    if filial not in FILIAIS:
        return RedirectResponse(url="/pdv?erro=filial", status_code=302)
    if forma_pagamento not in FORMAS_PAGAMENTO:
        return RedirectResponse(url="/pdv?erro=pagamento", status_code=302)

    try:
        itens = json.loads(carrinho_json)
    except (json.JSONDecodeError, ValueError):
        return RedirectResponse(url="/pdv?erro=json", status_code=302)

    if not isinstance(itens, list) or not itens:
        return RedirectResponse(url="/pdv?erro=vazio", status_code=302)

    desconto_percentual = 0.0

    # ── Valida estoque e calcula totais ──────────────────────
    total_bruto = 0.0
    itens_validados = []
    quantidades_por_produto = {}
    quantidades_por_variacao = {}

    for item in itens:
        if not isinstance(item, dict):
            return RedirectResponse(url="/pdv?erro=json", status_code=302)

        try:
            produto_id = int(item.get("produto_id"))
        except (TypeError, ValueError):
            return RedirectResponse(url="/pdv?erro=produto_inexistente", status_code=302)

        if produto_id <= 0:
            return RedirectResponse(url="/pdv?erro=produto_inexistente", status_code=302)

        produto = (
            db.query(Produto)
            .join(Categoria, Produto.categoria_id == Categoria.id)
            .filter(Produto.id == produto_id, Produto.ativo == True, func.lower(Categoria.nome).in_(CATEGORIAS_PDV))
            .with_for_update()
            .first()
        )

        if not produto:
            return RedirectResponse(
                url=f"/pdv?erro=produto_inexistente&id={produto_id}",
                status_code=302
            )

        try:
            qtd = int(item["quantidade"])
        except (KeyError, TypeError, ValueError):
            return RedirectResponse(url="/pdv?erro=quantidade", status_code=302)

        if qtd <= 0:
            return RedirectResponse(url="/pdv?erro=quantidade", status_code=302)

        saldo_filial = None
        if not produto.eh_consumo:
            garantir_estoque_filiais(db, produto)
            saldo_filial = db.query(EstoqueFilial).filter(
                EstoqueFilial.produto_id == produto.id,
                EstoqueFilial.filial == filial,
            ).with_for_update().first()
            quantidade_total_produto = quantidades_por_produto.get(produto.id, 0) + qtd
            if not saldo_filial or quantidade_total_produto > saldo_filial.quantidade:
                return RedirectResponse(url=f"/pdv?erro=estoque&produto={produto.nome}", status_code=302)
            quantidades_por_produto[produto.id] = quantidade_total_produto
        try:
            tamanho_id = obter_tamanho_id_item(item)
            cor = obter_cor_item(item)
        except ValueError:
            return RedirectResponse(url="/pdv?erro=variacao", status_code=302)

        if False and produto.eh_camiseta and (not tamanho_id or not cor):
            return RedirectResponse(url="/pdv?erro=variacao", status_code=302)

        estoque_tamanho = None
        estoque_variacao = None
        if False and produto.eh_camiseta:
            estoque_variacao = db.query(EstoqueVariacao).filter(
                EstoqueVariacao.produto_id == produto.id,
                EstoqueVariacao.tamanho_id == tamanho_id,
                EstoqueVariacao.cor == cor,
            ).with_for_update().first()
            if estoque_variacao:
                chave_variacao = (produto.id, tamanho_id, cor)
                quantidade_total_variacao = quantidades_por_variacao.get(chave_variacao, 0) + qtd
                if quantidade_total_variacao > estoque_variacao.estoque_atual:
                    return RedirectResponse(url=f"/pdv?erro=estoque_variacao&produto={produto.nome}", status_code=302)
                quantidades_por_variacao[chave_variacao] = quantidade_total_variacao
            else:
                estoque_tamanho = db.query(EstoqueTamanho).filter(
                    EstoqueTamanho.produto_id == produto.id,
                    EstoqueTamanho.tamanho_id == tamanho_id,
                ).with_for_update().first()
                chave_variacao = (produto.id, tamanho_id, None)
                quantidade_total_variacao = quantidades_por_variacao.get(chave_variacao, 0) + qtd
                if not estoque_tamanho or quantidade_total_variacao > estoque_tamanho.estoque_atual:
                    return RedirectResponse(url=f"/pdv?erro=estoque_variacao&produto={produto.nome}", status_code=302)
                quantidades_por_variacao[chave_variacao] = quantidade_total_variacao

        preco_unitario = produto.preco
        subtotal    = preco_unitario * qtd
        total_bruto += subtotal

        itens_validados.append({
            "produto":       produto,
            "quantidade":    qtd,
            "preco":         preco_unitario,
            "produto_nome":  produto.nome,
            "tamanho":       estoque_variacao.tamanho.nome if estoque_variacao else (estoque_tamanho.tamanho.nome if estoque_tamanho else None),
            "cor":           estoque_variacao.cor if estoque_variacao else ("Padrão" if estoque_tamanho else None),
            "estoque_tamanho": estoque_tamanho,
            "estoque_variacao": estoque_variacao,
            "saldo_filial": saldo_filial,
        })

    # ── Calcula desconto e total final
    desconto_valor = total_bruto * (desconto_percentual / 100)
    total_liquido  = total_bruto - desconto_valor

    # ── Persiste tudo em uma única transação
    venda = Venda(
        usuario_id          = usuario.get("id"),
        desconto_percentual = desconto_percentual,
        total_bruto         = round(total_bruto, 2),
        total_liquido       = round(total_liquido, 2),
        observacao          = observacao or None,
        forma_pagamento     = forma_pagamento,
    )
    db.add(venda)
    db.flush()  # gera o venda.id sem commitar ainda

    for item in itens_validados:
        db.add(ItemVenda(
            venda_id       = venda.id,
            produto_id     = item["produto"].id,
            produto_nome   = item["produto_nome"],
            tamanho        = item["tamanho"],
            cor            = item["cor"],
            quantidade     = item["quantidade"],
            preco_unitario = item["preco"],
        ))
        # Baixa o estoque do produto
        if item["saldo_filial"]:
            item["produto"].estoque_atual -= item["quantidade"]
            item["saldo_filial"].quantidade -= item["quantidade"]
            if item["estoque_tamanho"]:
                item["estoque_tamanho"].estoque_atual -= item["quantidade"]
            if item["estoque_variacao"]:
                item["estoque_variacao"].estoque_atual -= item["quantidade"]

    db.commit()

    return RedirectResponse(
        url=f"/pdv/venda/{venda.id}?sucesso=ok",
        status_code=302
    )


@router.get("/venda/{venda_id}")
def detalhe_venda(
    venda_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    """Comprovante da venda — exibido imediatamente após finalizar."""
    venda = db.query(Venda).filter(Venda.id == venda_id).first()

    if not venda:
        return RedirectResponse(url="/pdv", status_code=302)

    return templates.TemplateResponse(
        request,
        "pdv/comprovante.html",
        {"request": request, "usuario": usuario, "venda": venda}
    )


@router.post("/finalizar-dia")
def finalizar_dia(
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado),
):
    """Fecha manualmente o caixa do dia atual; uma nova ação atualiza o mesmo registro."""
    fechar_dia(db, datetime.now(FUSO_HORARIO).date())
    return RedirectResponse(url="/pdv/historico?dia_finalizado=ok", status_code=303)


@router.get("/historico")
def historico_vendas(
    request: Request,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    """Histórico de todas as vendas — Corrigido para alimentar o modal."""
    vendas = (
        db.query(Venda)
        .order_by(Venda.criado_em.desc())
        .limit(100)
        .all()
    )

    # CORREÇÃO: Buscando os produtos ativos para que o modal nesta página não fique em branco
    produtos = (
        db.query(Produto)
        .filter(Produto.ativo == True)
        .order_by(Produto.nome)
        .all()
    )
    fechamentos = (
        db.query(FechamentoDiario)
        .order_by(FechamentoDiario.data.desc())
        .limit(100)
        .all()
    )
    tamanhos = ordenar_tamanhos(db.query(Tamanho).filter(Tamanho.ativo == True).all())

    return templates.TemplateResponse(
        request,
        "pdv/historico.html",
        {
            "request": request, 
            "usuario": usuario, 
            "vendas": vendas,
            "produtos": produtos,
            "fechamentos": fechamentos,
            "tamanhos": tamanhos,
        }
    )
