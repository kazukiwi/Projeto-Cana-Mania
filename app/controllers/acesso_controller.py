"""Entrada pelo celular e QR Code de acesso à rede local."""
import base64
import ipaddress
import os
import socket
import secrets
from io import BytesIO
from urllib.parse import urlsplit

import qrcode
from qrcode.image.svg import SvgPathImage
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import criar_token, get_usuario_logado, hash_senha
from app.database import get_db
from app.models.usuario import Usuario

router = APIRouter(prefix="/acesso", tags=["Acesso pelo celular"])
templates = Jinja2Templates(directory="app/templates")


def endereco_celular(request: Request) -> str:
    configurado = os.getenv("ACESSO_PUBLICO_URL", "").strip().rstrip("/")
    if configurado:
        parts = urlsplit(configurado)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.path or parts.query or parts.fragment:
            raise ValueError("Configure ACESSO_PUBLICO_URL como endereço base, por exemplo http://192.168.1.10:8000.")
        return configurado + "/acesso/"
    host = request.url.hostname or ""
    if host.lower() in {"localhost", "127.0.0.1", "::1", "testserver"}:
        try:
            addresses = socket.gethostbyname_ex(socket.gethostname())[2]
            host = next(address for address in addresses if ipaddress.ip_address(address).is_private and not ipaddress.ip_address(address).is_loopback)
        except (OSError, StopIteration, ValueError):
            raise ValueError("Não foi possível descobrir o IP da rede. Configure ACESSO_PUBLICO_URL.") from None
    port = f":{request.url.port}" if request.url.port else ""
    return f"{request.url.scheme}://{host}{port}/acesso/"


@router.get("/")
def entrada(request: Request):
    return templates.TemplateResponse(request, "acesso/entrada.html", {"request": request})


@router.get("/usuario")
def entrada_usuario(request: Request):
    return templates.TemplateResponse(request, "acesso/usuario.html", {"request": request})


def iniciar_sessao(usuario: Usuario):
    token = criar_token({"sub": usuario.email, "nome": usuario.nome, "role": usuario.role, "id": usuario.id})
    response = RedirectResponse("/cliente/cardapio", status_code=303)
    response.set_cookie("access_token", token, httponly=True, max_age=3600, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/visitante")
def visitante(db: Session = Depends(get_db)):
    identificador = secrets.token_hex(16)
    usuario = Usuario(nome="Visitante", email=f"{identificador}@visitante.invalid",
                      senha_hash=hash_senha(secrets.token_urlsafe(32)), role="visitante", ativo=True)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return iniciar_sessao(usuario)


@router.get("/cadastro")
def formulario_cadastro(request: Request):
    return templates.TemplateResponse(request, "acesso/cadastro.html", {"request": request})


@router.post("/cadastro")
def cadastrar(request: Request, nome: str = Form(...), email: str = Form(...), senha: str = Form(...),
              db: Session = Depends(get_db)):
    nome, email = nome.strip(), email.strip().lower()
    erro = None
    if not nome or len(nome) > 100 or len(email) > 100 or "@" not in email:
        erro = "Confira seu nome e e-mail."
    elif not 8 <= len(senha) or len(senha.encode("utf-8")) > 72:
        erro = "Use uma senha com pelo menos 8 caracteres e até 72 bytes."
    elif email.endswith("@visitante.invalid"):
        erro = "Informe um e-mail válido."
    elif db.query(Usuario.id).filter(func.lower(Usuario.email) == email).first():
        erro = "Este e-mail já está cadastrado. Entre com sua conta."
    if erro:
        return templates.TemplateResponse(request, "acesso/cadastro.html", {"request": request, "erro": erro, "nome": nome, "email": email}, status_code=400)
    usuario = Usuario(nome=nome, email=email, senha_hash=hash_senha(senha), role="cliente", ativo=True)
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(request, "acesso/cadastro.html", {"request": request, "erro": "Este e-mail já está cadastrado.", "nome": nome, "email": email}, status_code=400)
    db.refresh(usuario)
    return iniciar_sessao(usuario)


@router.get("/qr")
def qr_acesso(request: Request, usuario=Depends(get_usuario_logado)):
    if usuario.get("role") not in {"admin", "funcionario"}:
        raise HTTPException(403, "Acesso disponível para a equipe.")
    try:
        url = endereco_celular(request)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    arquivo = BytesIO()
    qrcode.make(url, image_factory=SvgPathImage).save(arquivo)
    imagem = "data:image/svg+xml;base64," + base64.b64encode(arquivo.getvalue()).decode("ascii")
    return templates.TemplateResponse(request, "acesso/qr.html", {"request": request, "usuario": usuario, "url": url, "imagem": imagem})
