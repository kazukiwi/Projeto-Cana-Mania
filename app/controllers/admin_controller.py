from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import get_admin, hash_senha

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def listar_usuarios(
    request: Request, 
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    usuarios = db.query(Usuario).filter(Usuario.role != "visitante").order_by(Usuario.nome)
    return templates.TemplateResponse(
        request,
        "users/index.html",
        {
            "request": request, 
            "usuarios": usuarios,
            "usuario": admin
        }
    )

@router.get("/novo", response_class=HTMLResponse)
def form_novo_usuario(
    request: Request,
    admin = Depends(get_admin)
):
    return templates.TemplateResponse(
        request,
        "users/criar_usuarios.html",
        {
            "request": request,
            "usuario": admin
        }
    )

@router.post("/novo")
def cadastrar_usuario(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    role: str = Form("funcionario"),
    db: Session = Depends(get_db),
    admin = Depends(get_admin),
):
    nome, email = nome.strip(), email.strip().lower()
    valores = {"nome": nome, "email": email, "role": role}
    erro = None
    if role not in {"funcionario", "admin", "cliente"}:
        erro = "Selecione um perfil de acesso válido."
    elif (
        not nome or len(nome) > 100 or len(email) > 100
        or email.count("@") != 1 or email.startswith("@") or email.endswith("@")
        or any(c.isspace() for c in email)
    ):
        erro = "Confira o nome e o e-mail informados."
    elif len(senha) < 8 or len(senha.encode("utf-8")) > 72:
        erro = "A senha deve ter pelo menos 8 caracteres e no máximo 72 bytes."
    elif db.query(Usuario.id).filter(func.lower(Usuario.email) == email).first():
        erro = "Este e-mail já está cadastrado."
    if erro:
        return templates.TemplateResponse(
            request,
            "users/criar_usuarios.html",
            {"request": request, "usuario": admin, "erro": erro, "valores": valores},
            status_code=400,
        )

    senha_hash = hash_senha(senha)
    novo_usuario = Usuario(nome=nome, email=email, senha_hash=senha_hash, role=role, ativo=True)
    db.add(novo_usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "users/criar_usuarios.html",
            {"request": request, "usuario": admin, "erro": "Este e-mail já está cadastrado.", "valores": valores},
            status_code=400,
        )

    return RedirectResponse("/usuarios?criado=ok", status_code=303)

@router.post("/{usuario_id}/toggle-ativo")
def toggle_usuario_ativo(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    # Impede o admin de desativar a própria conta
    if usuario_id == admin["id"]:
        return RedirectResponse(
            url="/usuarios?erro=autoproprio",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Busca o usuário
    usuario_alvo = db.query(Usuario).filter(
        Usuario.id == usuario_id
    ).first()

    # Se não encontrar
    if not usuario_alvo:
        return RedirectResponse(
            url="/usuarios?erro=nao_encontrado",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Alterna ativo/inativo
    usuario_alvo.ativo = not usuario_alvo.ativo

    db.commit()
    db.refresh(usuario_alvo)

    return RedirectResponse(
        url="/usuarios?editado=ok",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/assosiados")
def listar_usuarios_assosiados(
    request: Request,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    usuarios = db.query(Usuario).filter(Usuario.role == "associado").order_by(Usuario.nome)
    return templates.TemplateResponse(
        request,
        "assosiados.html", 
        {
            "request": request, 
            "usuarios": usuarios,
            "usuario": admin
        }
    )

@router.post("/assosiados/novo")
def cadastrar_usuario_assosiado(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    #Verificar se o email já existe
    usuario_existente = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario_existente:
        return templates.TemplateResponse(
            request,
            "templates/users/criar_assosiados.html",
            {"request": request, "erro": "E-mail já cadastrado"}
        )
    
    #Criar novo usuário
    senha_hash = hash_senha(senha)
    novo_usuario = Usuario(nome=nome, email=email, senha_hash=senha_hash, role="associado")
    db.add(novo_usuario)
    db.commit()

    #Redirecionar para a tela de login após cadastro
    return RedirectResponse("/usuarios/assosiados?cadastro=success", status_code=303)

@router.post("/assosiados/{usuario_id}/toggle-ativo")
def toggle_usuario_assosiado_ativo(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    # Impede o admin de desativar a própria conta
    if usuario_id == admin["id"]:
        return RedirectResponse(
            url="/usuarios/assosiados?erro=autoproprio",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Busca o usuário
    usuario_alvo = db.query(Usuario).filter(
        Usuario.id == usuario_id,
        Usuario.role == "associado"
    ).first()

    # Se não encontrar
    if not usuario_alvo:
        return RedirectResponse(
            url="/usuarios/assosiados?erro=nao_encontrado",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    # Alterna ativo/inativo
    usuario_alvo.ativo = not usuario_alvo.ativo

    db.commit()
    db.refresh(usuario_alvo)

    return RedirectResponse(
        url="/usuarios/assosiados?editado=ok",
        status_code=status.HTTP_303_SEE_OTHER
    )
