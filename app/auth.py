from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request, HTTPException, status
from dotenv import load_dotenv
import os

#Carregar as variaveis de ambiente
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRACAO_MINUTOS = os.getenv("ACCESS_TOKEN_EXPIRACAO_MINUTOS")
RESET_TOKEN_EXPIRACAO_MINUTOS = int(os.getenv("RESET_TOKEN_EXPIRACAO_MINUTOS", "30"))

#CryptContent
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#Funções de senha
def hash_senha(senha: str):
    return pwd_context.hash(senha)

def verificar_senha(senha: str, senha_hash: str):

    return pwd_context.verify(senha, senha_hash)



#Funções do token
def criar_token(data: dict):
    payload = data.copy()

    #Define quando o token expira
    expira = datetime.now(timezone.utc) + timedelta(minutes=int(ACCESS_TOKEN_EXPIRACAO_MINUTOS))
    payload.update({"exp": expira})

    #Criar o token
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def criar_token_redefinicao_senha(email: str):
    """Cria um token de uso exclusivo para a redefinição de senha."""
    payload = {
        "sub": email,
        "finalidade": "redefinir_senha",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRACAO_MINUTOS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def validar_token_redefinicao_senha(token: str):
    """Retorna o e-mail do token válido ou levanta JWTError."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("finalidade") != "redefinir_senha" or not payload.get("sub"):
        raise JWTError("Token inválido para redefinição de senha")
    return payload["sub"]

def decodificar_token(token: str):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload

#Dependência do fastapi
def get_usuario_logado(request: Request):
    
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado"
        )
    try:
        payload = decodificar_token(token)
        email = payload.get("sub")

        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )
    
def get_usuario_opcional(request: Request):
    try:
        return get_usuario_logado(request)
    except HTTPException:
        return None
    
# dependendia do fatsapi para administradores
def get_admin(request: Request):
    usuario = get_usuario_logado(request)

    if usuario.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado (Somente administradores)"
        )
    
    return usuario
