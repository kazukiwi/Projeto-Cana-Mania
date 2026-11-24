from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_usuario_logado
from app.database import get_db
from app.models.categoria import Categoria
from app.models.filial import EstoqueFilial, FILIAIS
from app.models.produtos import CATEGORIAS_CONSUMO, LIMITE_ESTOQUE_BAIXO, EstoqueVariacao, Produto
from app.models.reposicao_estoque import ReposicaoEstoque
from app.models.transferencia_estoque import TransferenciaEstoque
from app.models.usuario import Usuario

router = APIRouter(prefix="/estoque", tags=["Estoque por filial"])
templates = Jinja2Templates(directory="app/templates")


def garantir_estoque_filiais(db: Session, produto: Produto | None = None) -> None:
    """Cria saldos por filial sem alterar o estoque já distribuído."""
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


def usuario_autorizado(db: Session, token: dict) -> Usuario:
    """Autoriza funcionários ativos e administradores na tela de estoque."""
    if token.get("role") not in {"funcionario", "admin"}:
        raise HTTPException(status_code=403, detail="Acesso permitido somente a funcionários.")
    usuario = db.query(Usuario).filter(Usuario.id == token.get("id")).first()
    if not usuario or not usuario.ativo or usuario.role not in {"funcionario", "admin"}:
        raise HTTPException(status_code=403, detail="Acesso permitido somente a funcionários ativos.")
    return usuario


@router.get("/")
def painel_estoque(request: Request, db: Session = Depends(get_db), token=Depends(get_usuario_logado)):
    usuario = usuario_autorizado(db, token)
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
    variacoes = {
        str(produto.id): [
            {
                "id": variacao.id,
                "label": f"{variacao.tamanho.nome if variacao.tamanho else 'Tamanho'} / {variacao.cor}",
            }
            for variacao in produto.estoques_variacoes
        ]
        for produto in produtos if produto.possui_variacoes_tamanho
    }
    historico = (
        db.query(ReposicaoEstoque)
        .order_by(ReposicaoEstoque.criado_em.desc(), ReposicaoEstoque.id.desc())
        .all()
    )
    transferencias = (
        db.query(TransferenciaEstoque)
        .order_by(TransferenciaEstoque.criado_em.desc(), TransferenciaEstoque.id.desc())
        .limit(100).all()
        if usuario.role == "admin" else []
    )
    saldos_json = {
        f"{produto.id}|{filial}": por_produto.get((produto.id, filial), 0)
        for produto in produtos for filial in FILIAIS
    }
    return templates.TemplateResponse(request, "estoque/index.html", {
        "request": request,
        "usuario": usuario,
        "produtos": produtos,
        "filiais": FILIAIS,
        "por_produto": por_produto,
        "resumo": resumo,
        "alertas": alertas,
        "variacoes_json": variacoes,
        "saldos_json": saldos_json,
        "historico": historico,
        "transferencias": transferencias,
    })


@router.post("/reposicoes")
def registrar_reposicao(
    produto_id: int = Form(...),
    filial: str = Form(...),
    local_compra: str = Form(..., max_length=150),
    quantidade: int = Form(...),
    variacao_id: str = Form(""),
    db: Session = Depends(get_db),
    token=Depends(get_usuario_logado),
):
    usuario = usuario_autorizado(db, token)
    local_compra = local_compra.strip()
    if filial not in FILIAIS or quantidade <= 0 or not local_compra:
        return RedirectResponse("/estoque/?erro=dados", status_code=303)
    produto = db.query(Produto).filter(Produto.id == produto_id, Produto.ativo == True).first()
    if not produto or produto.eh_consumo:
        return RedirectResponse("/estoque/?erro=produto", status_code=303)

    variacao = None
    if produto.possui_variacoes_tamanho:
        try:
            variacao_pk = int(variacao_id)
        except (TypeError, ValueError):
            return RedirectResponse("/estoque/?erro=variacao", status_code=303)
        variacao = db.query(EstoqueVariacao).filter(
            EstoqueVariacao.id == variacao_pk,
            EstoqueVariacao.produto_id == produto.id,
        ).first()
        if not variacao:
            return RedirectResponse("/estoque/?erro=variacao", status_code=303)
    elif variacao_id:
        return RedirectResponse("/estoque/?erro=variacao", status_code=303)

    garantir_estoque_filiais(db, produto)
    saldo = (
        db.query(EstoqueFilial)
        .filter_by(produto_id=produto.id, filial=filial)
        .with_for_update()
        .first()
    )
    if not saldo:
        return RedirectResponse("/estoque/?erro=produto", status_code=303)

    saldo_anterior = saldo.quantidade
    saldo.quantidade += quantidade
    produto.estoque_atual += quantidade
    if variacao:
        variacao.estoque_atual += quantidade
    db.add(ReposicaoEstoque(
        produto_id=produto.id,
        produto_nome=produto.nome,
        variacao_id=variacao.id if variacao else None,
        variacao_label=(
            f"{variacao.tamanho.nome if variacao.tamanho else 'Tamanho'} / {variacao.cor}"
            if variacao else None
        ),
        usuario_id=usuario.id,
        usuario_nome=usuario.nome,
        filial=filial,
        local_compra=local_compra,
        quantidade=quantidade,
        saldo_anterior=saldo_anterior,
        saldo_atualizado=saldo.quantidade,
    ))
    db.commit()
    return RedirectResponse("/estoque/?reposicao=ok", status_code=303)
@router.post("/transferencias")
def transferir_estoque(
    produto_id: int = Form(...),
    filial_origem: str = Form(...),
    filial_destino: str = Form(...),
    quantidade: int = Form(...),
    db: Session = Depends(get_db),
    token=Depends(get_usuario_logado),
):
    usuario = usuario_autorizado(db, token)
    if usuario.role != "admin":
        raise HTTPException(status_code=403, detail="Somente administradores podem transferir estoque.")
    if filial_origem not in FILIAIS or filial_destino not in FILIAIS or filial_origem == filial_destino or quantidade <= 0:
        return RedirectResponse("/estoque/?erro=transferencia", status_code=303)
    produto = db.query(Produto).filter(Produto.id == produto_id, Produto.ativo == True).first()
    if not produto or produto.eh_consumo:
        return RedirectResponse("/estoque/?erro=transferencia", status_code=303)
    garantir_estoque_filiais(db, produto)
    saldos = {
        saldo.filial: saldo
        for saldo in db.query(EstoqueFilial)
        .filter(EstoqueFilial.produto_id == produto.id, EstoqueFilial.filial.in_([filial_origem, filial_destino]))
        .with_for_update().all()
    }
    origem, destino = saldos.get(filial_origem), saldos.get(filial_destino)
    if not origem or not destino or origem.quantidade < quantidade:
        return RedirectResponse("/estoque/?erro=transferencia", status_code=303)
    origem_antes, destino_antes = origem.quantidade, destino.quantidade
    origem.quantidade -= quantidade
    destino.quantidade += quantidade
    db.add(TransferenciaEstoque(
        produto_id=produto.id, produto_nome=produto.nome,
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        filial_origem=filial_origem, filial_destino=filial_destino,
        quantidade=quantidade,
        saldo_origem_anterior=origem_antes, saldo_origem_atualizado=origem.quantidade,
        saldo_destino_anterior=destino_antes, saldo_destino_atualizado=destino.quantidade,
    ))
    db.commit()
    return RedirectResponse("/estoque/?transferencia=ok", status_code=303)
