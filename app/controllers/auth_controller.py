import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import (
    hash_senha,
    verificar_senha,
    criar_token,
    criar_token_redefinicao_senha,
    validar_token_redefinicao_senha,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])

templates = Jinja2Templates(directory="app/templates")


def enviar_email_redefinicao(destinatario: str, link: str):
    """Envia o link usando as configurações SMTP definidas no ambiente."""
    host = os.getenv("SMTP_HOST")
    porta = int(os.getenv("SMTP_PORT", "587"))
    remetente = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER")
    usuario = os.getenv("SMTP_USER")
    senha = os.getenv("SMTP_PASSWORD")
    usar_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    if not host or not remetente:
        raise RuntimeError("SMTP não configurado")

    mensagem = EmailMessage()
    mensagem["Subject"] = "Redefinição de senha - AAPM"
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(
        "Recebemos uma solicitação para redefinir sua senha no sistema AAPM.\n\n"
        f"Acesse o link abaixo em até 30 minutos:\n{link}\n\n"
        "Se você não solicitou essa alteração, ignore este e-mail."
    )
    link_seguro = escape(link, quote=True)
    mensagem.add_alternative(
        f"""\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @media only screen and (max-width: 600px) {{
      .email-card {{ width: 100% !important; border-radius: 0 !important; }}
      .email-content {{ padding: 34px 24px !important; }}
      .email-title {{ font-size: 28px !important; }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background:#eef0fb; font-family:Arial, Helvetica, sans-serif; color:#17205f;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#eef0fb; padding:40px 16px;">
    <tr>
      <td align="center">
        <table class="email-card" role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:600px; max-width:100%; overflow:hidden; background:#ffffff; border-radius:24px; box-shadow:0 10px 30px rgba(9,20,92,0.16);">
          <tr>
            <td style="padding:30px 42px; background:#09145c; text-align:center;">
              <p style="margin:0; color:#ffffff; font-family:Georgia, 'Times New Roman', serif; font-size:42px; font-weight:700; letter-spacing:2px;">AAPM</p>
              <p style="margin:7px 0 0; color:#d9ddff; font-size:13px; letter-spacing:1px; text-transform:uppercase;">Sistema de Gestão</p>
            </td>
          </tr>
          <tr>
            <td class="email-content" style="padding:42px;">
              <div style="width:54px; height:54px; margin:0 auto 22px; border-radius:50%; background:#e7e9ff; text-align:center; line-height:54px; font-size:26px;">🔐</div>
              <h1 class="email-title" style="margin:0 0 16px; color:#09145c; font-size:32px; line-height:1.2; text-align:center;">Redefinição de senha</h1>
              <p style="margin:0 0 18px; color:#4b5275; font-size:16px; line-height:1.65; text-align:center;">Recebemos uma solicitação para criar uma nova senha para sua conta AAPM.</p>
              <p style="margin:0 0 30px; color:#4b5275; font-size:16px; line-height:1.65; text-align:center;">Clique no botão abaixo para continuar. O link é válido por <strong style="color:#09145c;">30 minutos</strong>.</p>
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center">
                <tr>
                  <td style="border-radius:12px; background:#09145c;">
                    <a href="{link_seguro}" style="display:inline-block; padding:16px 28px; color:#ffffff; font-size:16px; font-weight:700; text-decoration:none;">Redefinir minha senha</a>
                  </td>
                </tr>
              </table>
              <div style="margin:34px 0 0; padding:17px; border-radius:12px; background:#f4f5ff;">
                <p style="margin:0; color:#596080; font-size:13px; line-height:1.55; text-align:center;">Se você não solicitou a redefinição, não é necessário fazer nada. Sua senha continuará segura.</p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:22px 30px; background:#f7f8ff; border-top:1px solid #e5e7f6;">
              <p style="margin:0; color:#737995; font-size:12px; line-height:1.5; text-align:center;">Este é um e-mail automático. Por favor, não responda.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
""",
        subtype="html",
    )

    contexto_ssl = ssl.create_default_context()
    if usar_ssl:
        conexao = smtplib.SMTP_SSL(host, porta, timeout=25, context=contexto_ssl)
    else:
        conexao = smtplib.SMTP(host, porta, timeout=25)

    with conexao as servidor:
        if not usar_ssl and os.getenv("SMTP_USE_TLS", "true").lower() == "true":
            # Alguns provedores exigem o EHLO antes da negociação STARTTLS.
            servidor.ehlo()
            servidor.starttls(context=contexto_ssl)
            servidor.ehlo()
        if usuario and senha:
            servidor.login(usuario, senha)
        servidor.send_message(mensagem)


@router.get("/esqueci-senha", name="tela_esqueci_senha")
def tela_esqueci_senha(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/esqueci_senha.html",
        {"request": request},
    )


@router.post("/esqueci-senha")
def solicitar_redefinicao_senha(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    email_normalizado = email.strip().lower()
    usuario = (
        db.query(Usuario)
        .filter(func.lower(Usuario.email) == email_normalizado)
        .first()
    )

    # A resposta é a mesma para e-mails cadastrados ou não, evitando enumeração de contas.
    if usuario and usuario.ativo:
        token = criar_token_redefinicao_senha(usuario.email)
        link = str(request.url_for("tela_redefinir_senha", token=token))
        try:
            enviar_email_redefinicao(usuario.email, link)
        except (OSError, smtplib.SMTPException, RuntimeError):
            return templates.TemplateResponse(
                request,
                "auth/esqueci_senha.html",
                {
                    "request": request,
                    "erro": "Não foi possível enviar o e-mail agora. Tente novamente mais tarde.",
                    "email": email,
                },
                status_code=503,
            )

    return templates.TemplateResponse(
        request,
        "auth/esqueci_senha.html",
        {"request": request, "sucesso": True},
    )


@router.get("/redefinir-senha/{token}", name="tela_redefinir_senha")
def tela_redefinir_senha(request: Request, token: str):
    try:
        validar_token_redefinicao_senha(token)
    except JWTError:
        return templates.TemplateResponse(
            request,
            "auth/redefinir_senha.html",
            {"request": request, "token_invalido": True},
            status_code=400,
        )
    return templates.TemplateResponse(
        request,
        "auth/redefinir_senha.html",
        {"request": request, "token": token},
    )


@router.post("/redefinir-senha/{token}")
def redefinir_senha(
    request: Request,
    token: str,
    senha: str = Form(...),
    confirmar_senha: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        email = validar_token_redefinicao_senha(token)
    except JWTError:
        return templates.TemplateResponse(
            request,
            "auth/redefinir_senha.html",
            {"request": request, "token_invalido": True},
            status_code=400,
        )

    if len(senha) < 8 or senha != confirmar_senha:
        return templates.TemplateResponse(
            request,
            "auth/redefinir_senha.html",
            {
                "request": request,
                "token": token,
                "erro": "As senhas devem coincidir e ter pelo menos 8 caracteres.",
            },
            status_code=400,
        )

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not usuario.ativo:
        return templates.TemplateResponse(
            request,
            "auth/redefinir_senha.html",
            {"request": request, "token_invalido": True},
            status_code=400,
        )

    usuario.senha_hash = hash_senha(senha)
    db.commit()
    return RedirectResponse(url="/?senha_redefinida=1", status_code=303)

#Rota de cadastro
@router.get("/login")
def tela_login(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"request": request}
    )

@router.post("/login")
def login_usuario(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    #Verificar se o usuário existe
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"request": request, "erro": "E-mail ou senha inválidos"}
        )
    
    if not usuario.ativo:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"request": request, "erro": "Usuário inativo. Contate o administrador."}
        )
    
    #Criar token de acesso
    token_data = {
        "sub": usuario.email,
        "nome": usuario.nome,
        "role": usuario.role,
        "id": usuario.id
    }

    token = criar_token(token_data)

    #Redirecionar para a tela inicial com o token no cookie
    response = RedirectResponse(url="/?login=ok", status_code=303)
    response.set_cookie(
        key="access_token", 
        value=token, 
        httponly=True, 
        max_age=3600,
        samesite="lax")
    return response

@router.get("/logout")
def logout_usuario():
    response = RedirectResponse(url="/?logout=1", status_code=303)
    # Os atributos devem coincidir com os usados na criação do cookie para
    # que todos os navegadores removam a sessão corretamente.
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return response
