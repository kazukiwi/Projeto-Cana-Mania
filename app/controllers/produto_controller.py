# controllers/produto_controller.py — CRUD produtos AAPM SENAI
import os
import shutil
import uuid
import json
import math
from pathlib import Path
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from app.models.movimentacao import Movimentacao

from app.database import get_db
from app.models.produtos import Produto, EstoqueTamanho, EstoqueVariacao, Tamanho, condicao_estoque_baixo, ordenar_tamanhos
from app.models.categoria import Categoria
from app.auth import get_usuario_logado, get_admin

router = APIRouter(prefix="/produtos", tags=["Produtos"])

APP_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = APP_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"

templates = Jinja2Templates(directory=APP_DIR / "templates")

# Pasta onde as imagens serão salvas dentro de /static
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
def _salvar_estoques_tamanho(produto: Produto, possui_variacoes_tamanho: bool, estoques: dict[int, int]) -> None:
    if not possui_variacoes_tamanho:
        produto.estoques_tamanho.clear()
        return

    existentes = {registro.tamanho_id: registro for registro in produto.estoques_tamanho}
    for tamanho_id, quantidade in estoques.items():
        registro = existentes.get(tamanho_id)
        if registro:
            registro.estoque_atual = quantidade
        else:
            produto.estoques_tamanho.append(EstoqueTamanho(tamanho_id=tamanho_id, estoque_atual=quantidade))
    produto.estoque_atual = sum(estoques.values())


async def _obter_estoques_tamanho(request: Request, db: Session) -> dict[int, int]:
    """Lê os campos dinâmicos estoque_tamanho_<id>."""
    form = await request.form()
    tamanhos = db.query(Tamanho).filter(Tamanho.ativo == True).all()
    estoques = {}
    for tamanho in tamanhos:
        try:
            quantidade = int(form.get(f"estoque_tamanho_{tamanho.id}", 0) or 0)
        except (TypeError, ValueError):
            raise ValueError("estoque inválido")
        if quantidade < 0:
            raise ValueError("estoque inválido")
        estoques[tamanho.id] = quantidade
    return estoques


async def _obter_variacoes(request: Request, db: Session) -> list[dict]:
    """Lê e valida as combinações de tamanho, cor e estoque enviadas pelo formulário."""
    form = await request.form()
    try:
        variacoes = json.loads(form.get("variacoes_json", "[]"))
    except (TypeError, json.JSONDecodeError):
        raise ValueError("variações inválidas")

    if not isinstance(variacoes, list):
        raise ValueError("variações inválidas")

    tamanho_ids_validos = {t.id for t in db.query(Tamanho).filter(Tamanho.ativo == True).all()}
    combinacoes = set()
    resultado = []
    for variacao in variacoes:
        try:
            tamanho_id = int(variacao.get("tamanho_id"))
            cor = str(variacao.get("cor", "")).strip()
            estoque = int(variacao.get("estoque_atual"))
            preco = float(variacao.get("preco"))
        except (AttributeError, TypeError, ValueError):
            raise ValueError("variações inválidas")
        chave = (tamanho_id, cor.casefold())
        if tamanho_id not in tamanho_ids_validos or not cor or len(cor) > 50 or estoque < 0 or not math.isfinite(preco) or preco < 0 or chave in combinacoes:
            raise ValueError("variações inválidas")
        combinacoes.add(chave)
        resultado.append({"tamanho_id": tamanho_id, "cor": cor, "estoque_atual": estoque, "preco": preco})
    return resultado


def _salvar_variacoes(produto: Produto, variacoes: list[dict]) -> None:
    produto.estoques_variacoes.clear()
    produto.estoques_tamanho.clear()
    produto.estoques_variacoes.extend(EstoqueVariacao(**variacao) for variacao in variacoes)
    produto.estoque_atual = sum(variacao["estoque_atual"] for variacao in variacoes)


# ============================================================
# LISTAGEM
# ============================================================

@router.get("/")
def listar_produtos(
    request: Request,
    busca: str = "",
    categoria_id: int = 0,
    estoque_baixo: bool = False,
    pagina: int = 1,
    por_pagina: int = 10,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    query = db.query(Produto).filter(Produto.ativo == True)

    if busca:
        query = query.filter(Produto.nome.ilike(f"%{busca}%"))

    if categoria_id:
        query = query.filter(Produto.categoria_id == categoria_id)

    if estoque_baixo:
        query = query.filter(condicao_estoque_baixo())

    total_produtos = query.count()

    # A paginação desta tela é feita no navegador (listagem.js). Portanto,
    # todos os produtos filtrados precisam ser enviados para que as páginas
    # seguintes também possam ser exibidas. A ordenação estável evita que um
    # produto mude de posição entre carregamentos.
    produtos = (
        query.options(
            selectinload(Produto.estoques_variacoes).selectinload(EstoqueVariacao.tamanho)
        )
        .order_by(Produto.nome)
        .all()
    )
   


    categorias  = db.query(Categoria).filter(Categoria.ativo == True).all()

    return templates.TemplateResponse(
        request,
        "produtos/index.html",
        {
            "request":      request,
            "usuario":      usuario,
            "produtos":     produtos,
            "categorias":   categorias,
            "busca":        busca,
            "categoria_id": categoria_id,
            "estoque_baixo": estoque_baixo,

            "total_produtos": total_produtos
        }
    )
# ============================================================
# CADASTRO
# ============================================================

@router.get("/novo")
def form_novo_produto(
    request: Request,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    categorias = db.query(Categoria).filter(Categoria.ativo == True).all()
    tamanhos = ordenar_tamanhos(db.query(Tamanho).filter(Tamanho.ativo == True).all())

    return templates.TemplateResponse(
        request,
        "produtos/form.html",
        {
            "request":    request,
            "usuario":    admin,
            "editando":   None,
            "categorias": categorias,
            "tamanhos": tamanhos,
        }
    )


@router.post("/novo")
async def criar_produto(
    request: Request,
    nome: str          = Form(...),
    preco: float       = Form(...),
    estoque_atual: int = Form(0),
    possui_variacoes_tamanho: bool = Form(False),
    categoria_id: int  = Form(0),   # 0 = sem categoria
    imagem: UploadFile = File(None), # None = campo opcional
    db: Session        = Depends(get_db),
    admin              = Depends(get_admin)
):
    categorias = db.query(Categoria).filter(Categoria.ativo == True).all()
    tamanhos = ordenar_tamanhos(db.query(Tamanho).filter(Tamanho.ativo == True).all())

    # Verifica duplicidade de nome
    if db.query(Produto).filter(Produto.nome.ilike(nome)).first():
        return templates.TemplateResponse(
            request,
            "produtos/form.html",
            {
                "request":    request,
                "usuario":    admin,
                "editando":   None,
                "categorias": categorias,
                "tamanhos": tamanhos,
                "erro":       "Já existe um produto com este nome.",
                "valores":    {"nome": nome, "preco": preco,
                               "estoque_atual": estoque_atual,
                               "categoria_id": categoria_id,
                               "possui_variacoes_tamanho": possui_variacoes_tamanho}
            },
            status_code=400
        )

    # O preço é armazenado em reais, na mesma unidade usada pelo PDV e pelas vendas.
    try:
        variacoes = await _obter_variacoes(request, db)
    except ValueError:
        return RedirectResponse(url="/produtos/novo?erro=estoque", status_code=302)
    if possui_variacoes_tamanho and sum(variacao["estoque_atual"] for variacao in variacoes) == 0:
        return templates.TemplateResponse(
            request,
            "produtos/form.html",
            {
                "request": request,
                "usuario": admin,
                "editando": None,
                "categorias": categorias,
                "tamanhos": tamanhos,
                "erro": "Informe a quantidade de pelo menos um tamanho.",
                "valores": {
                    "nome": nome, "preco": preco, "estoque_atual": estoque_atual,
                    "variacoes": variacoes,
                    "categoria_id": categoria_id,
                    "possui_variacoes_tamanho": possui_variacoes_tamanho,
                },
            },
            status_code=400,
        )

    # Processa o upload da imagem após validar os dados do produto.
    imagem_path = await _salvar_imagem(imagem)

    produto = Produto(
        nome          = nome,
        preco         = preco,
        estoque_atual = sum(variacao["estoque_atual"] for variacao in variacoes) if possui_variacoes_tamanho else estoque_atual,
        possui_variacoes_tamanho = possui_variacoes_tamanho,
        categoria_id  = categoria_id or None,  # 0 vira NULL no banco
        imagem_path   = imagem_path,
    )
    if possui_variacoes_tamanho:
        _salvar_variacoes(produto, variacoes)

    db.add(produto)
    db.commit()

    return RedirectResponse(url="/produtos?criado=ok", status_code=302)


# DETALHE
@router.get("/{produto_id}")
def detalhe_produto(
    produto_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    produto = db.query(Produto).filter(
        Produto.id == produto_id,
        Produto.ativo == True
    ).first()

    if not produto:
        return RedirectResponse(url="/produtos", status_code=302)

    return templates.TemplateResponse(
        request,
        "produtos/detalhe.html",
        {"request": request, "usuario": usuario, "produto": produto}
    )


# EDIÇÃO
@router.get("/{produto_id}/editar")
def form_editar_produto(
    produto_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    editando   = db.query(Produto).filter(Produto.id == produto_id).first()
    categorias = db.query(Categoria).filter(Categoria.ativo == True).all()
    tamanhos = ordenar_tamanhos(db.query(Tamanho).filter(Tamanho.ativo == True).all())

    if not editando:
        return RedirectResponse(url="/produtos", status_code=302)

    return templates.TemplateResponse(
        request,
        "produtos/form.html",
        {
            "request":    request,
            "usuario":    admin,
            "editando":   editando,
            "categorias": categorias,
            "tamanhos": tamanhos,
        }
    )


@router.post("/{produto_id}/editar")
async def editar_produto(
    produto_id: int,
    request: Request,
    nome: str          = Form(...),
    preco: float       = Form(...),
    estoque_atual: int = Form(0),
    possui_variacoes_tamanho: bool = Form(False),
    categoria_id: int  = Form(0),
    imagem: UploadFile = File(None),
    db: Session        = Depends(get_db),
    admin              = Depends(get_admin)
):
    editando   = db.query(Produto).filter(Produto.id == produto_id).first()
    categorias = db.query(Categoria).filter(Categoria.ativo == True).all()
    tamanhos = ordenar_tamanhos(db.query(Tamanho).filter(Tamanho.ativo == True).all())

    if not editando:
        return RedirectResponse(url="/produtos", status_code=302)

    # Verifica conflito de nome com outro produto
    conflito = db.query(Produto).filter(
        Produto.nome.ilike(nome),
        Produto.id != produto_id
    ).first()

    if conflito:
        return templates.TemplateResponse(
            request,
            "produtos/form.html",
            {
                "request":    request,
                "usuario":    admin,
                "editando":   editando,
                "categorias": categorias,
                "tamanhos": tamanhos,
                "erro":       "Já existe outro produto com este nome.",
            },
            status_code=400
        )

    # Mantém o preço em reais ao atualizar o cadastro.
    try:
        variacoes = await _obter_variacoes(request, db)
    except ValueError:
        return RedirectResponse(url=f"/produtos/{produto_id}/editar?erro=estoque", status_code=302)
    if possui_variacoes_tamanho and sum(variacao["estoque_atual"] for variacao in variacoes) == 0:
        return templates.TemplateResponse(
            request,
            "produtos/form.html",
            {
                "request": request,
                "usuario": admin,
                "editando": editando,
                "categorias": categorias,
                "tamanhos": tamanhos,
                "erro": "Informe a quantidade de pelo menos um tamanho.",
            },
            status_code=400,
        )

    # Processa nova imagem — só substitui se um arquivo foi enviado.
    nova_imagem_path = await _salvar_imagem(imagem)
    if nova_imagem_path:
        # Remove a imagem antiga do disco para não acumular arquivos
        _remover_imagem(editando.imagem_path)
        editando.imagem_path = nova_imagem_path

    editando.nome          = nome
    editando.preco         = preco
    editando.estoque_atual = estoque_atual
    editando.possui_variacoes_tamanho = possui_variacoes_tamanho
    editando.categoria_id  = categoria_id or None
    if possui_variacoes_tamanho:
        _salvar_variacoes(editando, variacoes)
    else:
        editando.estoques_variacoes.clear()
        editando.estoques_tamanho.clear()

    db.commit()

    return RedirectResponse(url=f"/produtos/{produto_id}?editado=ok", status_code=302)


# ============================================================
# DESATIVAR
# ============================================================

@router.post("/{produto_id}/desativar")
def desativar_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()

    if produto:
        produto.ativo = False
        db.commit()

    return RedirectResponse(url="/produtos?desativado=ok", status_code=302)


# ============================================================
# FUNÇÕES AUXILIARES DE IMAGEM
# ============================================================

async def _salvar_imagem(imagem: UploadFile | None):
    """
    Salva o arquivo enviado em /app/static/uploads/ e retorna
    o path relativo para guardar no banco.
    """
    if not imagem or not imagem.filename:
        return None

    # Valida a extensão — aceita apenas imagens
    extensoes_permitidas = {".jpg", ".jpeg", ".png", ".webp"}
    _, ext = os.path.splitext(imagem.filename.lower())

    if ext not in extensoes_permitidas:
        return None

    # Garante nome de arquivo único usando UUID para evitar colisões
    nome_arquivo = f"{uuid.uuid4()}{ext}"
    caminho_completo = UPLOAD_DIR / nome_arquivo

    # Salva o arquivo no disco
    with open(caminho_completo, "wb") as buffer:
        shutil.copyfileobj(imagem.file, buffer)

    # Retorna o path relativo que a propriedade do modelo espera encontrar
    return f"uploads/{nome_arquivo}"


def _remover_imagem(imagem_path: str | None) -> None:
    """Remove o arquivo de imagem do disco se ele existir."""
    if not imagem_path:
        return

    # Remove referências de barras iniciais repetidas
    imagem_path_limpo = imagem_path.strip().lstrip('/').replace("\\", "/")
    
    # Se o path salvo já continha 'static/', removemos para não duplicar com o join abaixo
    if imagem_path_limpo.startswith("static/"):
        imagem_path_limpo = imagem_path_limpo.replace("static/", "", 1)

    caminho = (STATIC_DIR / imagem_path_limpo).resolve()

    # Nunca remove arquivos fora da pasta estática, mesmo se o banco tiver um caminho inválido.
    try:
        caminho.relative_to(STATIC_DIR.resolve())
    except ValueError:
        return

    if caminho.is_file():
        caminho.unlink()


@router.get("/mais-vendidos")
def mais_vendidos(db: Session = Depends(get_db)):
    resultado = (
        db.query(
            Produto.id,
            Produto.nome,
            func.sum(Movimentacao.quantidade).label("total_vendido")
        )
    )
