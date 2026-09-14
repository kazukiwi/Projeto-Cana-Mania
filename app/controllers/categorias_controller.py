import os

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional # <-- Importado para permitir descrição vazia

from app.database import get_db
from app.models.categoria import Categoria
from app.models.produtos import Produto
from app.auth import get_admin

router = APIRouter(prefix="/categorias", tags=["categorias"])

templates = Jinja2Templates(directory="app/templates")


# LISTAGEM DE CATEGORIAS
@router.get("/")
def listar_categorias(
    request: Request,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    categorias_db = db.query(Categoria).order_by(Categoria.nome).all()

    return templates.TemplateResponse(
        request,
        "categoria/index.html",
        {
            "request": request,
            "categorias": categorias_db,
            "usuario": admin
        }
    )


# CADASTRO DE CATEGORIAS
@router.get("/nova")
def form_nova_categoria(
    request: Request,
    admin = Depends(get_admin)
):
    return templates.TemplateResponse(
        request,
        "categoria/form.html",
        {
            "request": request,
            "usuario": admin,
            "editando": None,
        }
    )

@router.post("/nova")
def criar_categoria(
    request: Request,
    nome: str = Form(...),
    descricao: Optional[str] = Form(None), # <-- 1. CAPTURA A DESCRIÇÃO DO FORMULÁRIO
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    existente = db.query(Categoria).filter(Categoria.nome.ilike(nome)).first()

    if existente:
        return templates.TemplateResponse(
            request,
            "categoria/form.html",
            {
                "request": request,
                "usuario": admin,
                "editando": None,
                "erro": "Já existe uma categoria com esse nome.",
                "valores": {"nome": nome, "descricao": descricao}, # Devolve o valor digitado
            },
            status_code=400
        )
    
    # <-- 2. ADICIONA A DESCRIÇÃO NO OBJETO DO BANCO
    nova_categoria = Categoria(
        nome=nome.strip(), 
        descricao=descricao.strip() if descricao else None
    )
    db.add(nova_categoria)
    db.commit()

    return RedirectResponse("/categorias/", status_code=302)


# EDIÇÃO DE CATEGORIAS
@router.get("/{categoria_id}/editar")
def form_editar_categoria(
    request: Request,
    categoria_id: int,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()

    if not categoria:
        return RedirectResponse("/categorias/", status_code=302)

    return templates.TemplateResponse(
        request,
        "categoria/form.html",
        {
            "request": request,
            "usuario": admin,
            "editando": categoria,
        }
    )

@router.post("/{categoria_id}/editar")
def editar_categoria(
    categoria_id: int,
    request: Request,
    nome: str = Form(...),
    descricao: Optional[str] = Form(None), # <-- 3. CAPTURA A DESCRIÇÃO NA EDIÇÃO
    ativo: bool = Form(True),
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    editando = db.query(Categoria).filter(
        Categoria.id == categoria_id
    ).first()
    if not editando:
        return RedirectResponse("/categorias/", status_code=302)
    
    conflito = db.query(Categoria).filter(
        Categoria.nome.ilike(nome), 
        Categoria.id != categoria_id
    ).first() 

    if conflito:
        return templates.TemplateResponse(
            # CORREÇÃO: Ajustado caminho do template para 'categoria/form.html' (estava categorias com 's')
            request,
            "categoria/form.html", 
            {
                "request": request,
                "usuario": admin,
                "editando": editando,
                "erro": "Já existe uma categoria com esse nome.",
                "valores": {"nome": nome, "descricao": descricao},
            },
            status_code=400
        )
    
    # <-- 4. ATUALIZA A DESCRIÇÃO NO BANCO
    editando.nome = nome.strip()
    editando.descricao = descricao.strip() if descricao else None
    editando.ativo = ativo

    db.query(Produto).filter(Produto.categoria_id == categoria_id).update(
        {Produto.ativo: ativo},
        synchronize_session=False,
    )
    db.commit() 

    return RedirectResponse("/categorias/", status_code=302)


# TOGGLE DE ATIVAÇÃO
@router.post("/{categoria_id}/toggle-ativo")
def toggle_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()

    if not categoria:
        return RedirectResponse("/categorias/", status_code=302)

    if categoria.ativo:
        produtos_ativos = [p for p in categoria.produtos if p.ativa]

        if produtos_ativos:
            return RedirectResponse(
                url=f"/categorias?erro=produtos_vinculados&categoria={categoria.nome}",
                status_code=302
            )

    categoria.ativo = not categoria.ativo
    db.commit()

    return RedirectResponse("/categorias/", status_code=302)
