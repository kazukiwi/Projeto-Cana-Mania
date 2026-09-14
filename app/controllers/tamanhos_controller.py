from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_admin
from app.database import get_db
from app.models.produtos import EstoqueTamanho, Tamanho, ordenar_tamanhos

router = APIRouter(prefix="/tamanhos", tags=["Tamanhos"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def listar_tamanhos(request: Request, db: Session = Depends(get_db), admin=Depends(get_admin)):
    tamanhos = ordenar_tamanhos(db.query(Tamanho).all())
    return templates.TemplateResponse(request, "tamanhos/index.html", {"request": request, "usuario": admin, "tamanhos": tamanhos})


@router.post("/")
def criar_tamanho(nome: str = Form(...), db: Session = Depends(get_db), admin=Depends(get_admin)):
    nome = nome.strip().upper()
    if not nome or len(nome) > 30 or db.query(Tamanho).filter(func.lower(Tamanho.nome) == nome.lower()).first():
        return RedirectResponse(url="/tamanhos?erro=nome", status_code=303)
    db.add(Tamanho(nome=nome, ativo=True))
    db.commit()
    return RedirectResponse(url="/tamanhos?criado=ok", status_code=303)


@router.post("/{tamanho_id}/alternar")
def alternar_tamanho(tamanho_id: int, db: Session = Depends(get_db), admin=Depends(get_admin)):
    tamanho = db.query(Tamanho).filter(Tamanho.id == tamanho_id).first()
    if not tamanho:
        return RedirectResponse(url="/tamanhos", status_code=303)
    if tamanho.ativo:
        possui_saldo = db.query(EstoqueTamanho.id).filter(
            EstoqueTamanho.tamanho_id == tamanho.id, EstoqueTamanho.estoque_atual > 0
        ).first()
        if possui_saldo:
            return RedirectResponse(url="/tamanhos?erro=estoque", status_code=303)
    tamanho.ativo = not tamanho.ativo
    db.commit()
    return RedirectResponse(url="/tamanhos", status_code=303)
