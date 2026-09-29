import csv
import io
import json
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from app.auth import get_usuario_logado, get_admin
from app.database import get_db
from app.models.produtos import Produto
from app.models.categoria import Categoria
from app.models.usuario import Usuario
from app.models.venda import Venda
from app.models.filial import FILIAIS
from app.models.comercial import MovimentoCaixa, ConferenciaCaixa, AlteracaoEstoquePreco
from app.money import dinheiro, ZERO
from app.services.vendas import PAGAMENTOS, validar_token

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
FUSO = timezone(timedelta(hours=-3))
ROTULOS = {"credito": "Crédito", "debito": "Débito", "dinheiro": "Dinheiro", "pix": "Pix", "convite": "Convite", "outros": "Não informado"}

def brl(valor):
    return f"{dinheiro(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def local(valor):
    return valor.replace(tzinfo=timezone.utc).astimezone(FUSO).strftime("%d/%m/%Y %H:%M")

templates.env.filters.update(brl=brl, local=local, fromjson=json.loads)

def limites(inicio, fim):
    return (datetime.combine(inicio, time.min, FUSO).astimezone(timezone.utc).replace(tzinfo=None),
            datetime.combine(fim + timedelta(days=1), time.min, FUSO).astimezone(timezone.utc).replace(tzinfo=None))

def filtros(request, usuario):
    hoje = datetime.now(FUSO).date()
    try:
        inicio = date.fromisoformat(request.query_params.get("inicio") or hoje.replace(day=1).isoformat())
        fim = date.fromisoformat(request.query_params.get("fim") or hoje.isoformat())
        operador = int(request.query_params.get("operador") or 0)
        pagina = max(1, int(request.query_params.get("pagina") or 1))
        if fim < inicio or (fim - inicio).days > 366:
            raise ValueError()
    except ValueError:
        raise HTTPException(400, "Informe um período válido de até 367 dias.") from None
    filial = request.query_params.get("filial", "")
    pagamento = request.query_params.get("pagamento", "")
    if filial not in ("", "legado", *FILIAIS) or pagamento not in ("", "outros", *PAGAMENTOS):
        raise HTTPException(400, "Filtro inválido.")
    if usuario.get("role") != "admin":
        operador = usuario["id"]
    return dict(inicio=inicio, fim=fim, operador=operador, pagina=pagina, filial=filial, pagamento=pagamento)

def consulta_vendas(db, f):
    inicio, fim = limites(f["inicio"], f["fim"])
    q = db.query(Venda).filter(Venda.criado_em >= inicio, Venda.criado_em < fim)
    if f["operador"]:
        q = q.filter(Venda.usuario_id == f["operador"])
    if f["filial"]:
        q = q.filter(Venda.filial.is_(None) if f["filial"] == "legado" else Venda.filial == f["filial"])
    if f["pagamento"]:
        q = q.filter(Venda.forma_pagamento.is_(None) if f["pagamento"] == "outros" else Venda.forma_pagamento == f["pagamento"])
    return q

def totais_pagamento(vendas):
    totais = dict.fromkeys(ROTULOS, ZERO)
    for venda in vendas:
        chave = venda.forma_pagamento if venda.forma_pagamento in PAGAMENTOS else "outros"
        totais[chave] += venda.total_liquido
    return totais

@router.get("/relatorios")
def relatorios(request: Request, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    f = filtros(request, usuario)
    vendas = consulta_vendas(db, f).options(joinedload(Venda.usuario)).order_by(Venda.criado_em.desc(), Venda.id.desc()).all()
    total = sum((v.total_liquido for v in vendas), ZERO)
    grupos = {}
    for v in vendas:
        chave = (v.filial or "Loja não informada", v.usuario.nome if v.usuario else "Operador não informado")
        grupos[chave] = grupos.get(chave, ZERO) + v.total_liquido
    por_pagina = 50
    return templates.TemplateResponse(request, "comercial/relatorios.html", {
        "usuario": usuario, "f": f, "filiais": FILIAIS, "rotulos": ROTULOS,
        "operadores": db.query(Usuario).order_by(Usuario.nome).all() if usuario.get("role") == "admin" else [],
        "vendas": vendas[(f["pagina"]-1)*por_pagina:f["pagina"]*por_pagina],
        "quantidade": len(vendas), "total": total, "ticket": total / len(vendas) if vendas else ZERO,
        "pagamentos": totais_pagamento(vendas), "grupos": grupos,
        "paginas": max(1, (len(vendas)+por_pagina-1)//por_pagina),
        "exportar": str(request.url.replace(path="/relatorios/exportar.csv")),
    })

def celula_segura(valor):
    texto = str(valor)
    return "'" + texto if texto.lstrip().startswith(("=", "+", "-", "@")) else texto

@router.get("/relatorios/exportar.csv")
def exportar(request: Request, db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    vendas = consulta_vendas(db, filtros(request, usuario)).options(joinedload(Venda.usuario)).order_by(Venda.criado_em, Venda.id).all()
    arquivo = io.StringIO()
    writer = csv.writer(arquivo, delimiter=";")
    writer.writerow(["Venda", "Data (Brasília)", "Loja", "Operador", "Pagamento", "Total (R$)"])
    for venda in vendas:
        writer.writerow([venda.id, local(venda.criado_em), celula_segura(venda.filial or "Loja não informada"),
                         celula_segura(venda.usuario.nome if venda.usuario else "Não informado"),
                         ROTULOS.get(venda.forma_pagamento, "Não informado"), brl(venda.total_liquido)])
    return Response("\ufeff" + arquivo.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="vendas.csv"', "Cache-Control": "no-store"})

def resumo_caixa(db, data, filial, operador):
    f = dict(inicio=data, fim=data, filial=filial, operador=operador, pagamento="")
    vendas = consulta_vendas(db, f).all()
    pagamentos = totais_pagamento(vendas)
    movimentos = db.query(MovimentoCaixa).filter_by(data=data, filial=filial, usuario_id=operador).order_by(MovimentoCaixa.id).all()
    abertura = sum((m.valor for m in movimentos if m.tipo == "abertura"), ZERO)
    reforcos = sum((m.valor for m in movimentos if m.tipo == "reforco"), ZERO)
    retiradas = sum((m.valor for m in movimentos if m.tipo == "retirada"), ZERO)
    esperado = abertura + pagamentos["dinheiro"] + reforcos - retiradas
    return dict(pagamentos=pagamentos, movimentos=movimentos, abertura=abertura,
                reforcos=reforcos, retiradas=retiradas, esperado=esperado,
                total=sum(pagamentos.values(), ZERO), quantidade=len(vendas))

@router.get("/caixa")
def caixa(request: Request, data: date | None = None, filial: str = FILIAIS[0], operador: int = 0,
          db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    data = data or datetime.now(FUSO).date()
    if filial not in FILIAIS:
        raise HTTPException(400, "Loja inválida.")
    operador = operador or usuario["id"]
    if usuario.get("role") != "admin":
        operador = usuario["id"]
    resumo = resumo_caixa(db, data, filial, operador)
    conferencias = db.query(ConferenciaCaixa).filter_by(data=data, filial=filial, usuario_id=operador).order_by(ConferenciaCaixa.id.desc()).all()
    return templates.TemplateResponse(request, "comercial/caixa.html", {
        "usuario": usuario, "data": data, "hoje": datetime.now(FUSO).date(), "filial": filial,
        "operador": operador, "filiais": FILIAIS, "rotulos": ROTULOS,
        "operadores": db.query(Usuario).order_by(Usuario.nome).all() if usuario.get("role") == "admin" else [],
        "conferencias": conferencias, "resumo": resumo, "movimento_token": str(uuid4()), "fechamento_token": str(uuid4()),
        "pode_operar": operador == usuario["id"],
    })

@router.post("/caixa/movimento")
def movimento_caixa(filial: str = Form(...), tipo: str = Form(...), valor: str = Form(...),
                    motivo: str = Form(..., min_length=1, max_length=255), token: str = Form(...),
                    db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    token = validar_token(token)
    try:
        valor = dinheiro(valor.replace(",", "."))
    except ValueError:
        raise HTTPException(400, "Valor inválido.") from None
    if filial not in FILIAIS or tipo not in ("abertura", "reforco", "retirada") or valor <= ZERO or not motivo.strip():
        raise HTTPException(400, "Confira o movimento, o valor e o motivo.")
    dados = dict(token=token, data=datetime.now(FUSO).date(), filial=filial, usuario_id=usuario["id"], tipo=tipo, valor=valor, motivo=motivo.strip())
    existente = db.query(MovimentoCaixa).filter_by(token=token).first()
    if existente:
        if any(getattr(existente, k) != v for k, v in dados.items() if k != "data"):
            raise HTTPException(409, "Movimento já registrado com outros dados.")
    else:
        db.add(MovimentoCaixa(**dados))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existente = db.query(MovimentoCaixa).filter_by(token=token).first()
            if not existente or any(getattr(existente, k) != v for k, v in dados.items() if k != "data"):
                raise HTTPException(409, "Movimento já registrado com outros dados.") from None
    return RedirectResponse("/caixa?filial=" + filial, status_code=303)

@router.post("/caixa/fechar")
def conferir_caixa(data: date = Form(...), filial: str = Form(...), informado: str = Form(...),
                   observacao: str = Form("", max_length=255), token: str = Form(...),
                   db: Session = Depends(get_db), usuario=Depends(get_usuario_logado)):
    token = validar_token(token)
    try:
        informado = dinheiro(informado.replace(",", "."))
    except ValueError:
        raise HTTPException(400, "Valor informado inválido.") from None
    if filial not in FILIAIS or informado < ZERO or data > datetime.now(FUSO).date():
        raise HTTPException(400, "Confira a data, a loja e o dinheiro contado.")
    existente = db.query(ConferenciaCaixa).filter_by(token=token).first()
    dados = dict(data=data, filial=filial, usuario_id=usuario["id"], informado=informado, observacao=observacao)
    if existente:
        if any(getattr(existente, k) != v for k, v in dados.items()):
            raise HTTPException(409, "Conferência já enviada com outros dados.")
    else:
        resumo = resumo_caixa(db, data, filial, usuario["id"])
        snapshot = {k: v for k, v in resumo.items() if k != "movimentos"}
        db.add(ConferenciaCaixa(token=token, **dados, esperado=resumo["esperado"],
                               diferenca=informado-resumo["esperado"], resumo_json=json.dumps(snapshot, default=str)))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existente = db.query(ConferenciaCaixa).filter_by(token=token).first()
            if not existente or any(getattr(existente, k) != v for k, v in dados.items()):
                raise HTTPException(409, "Conferência já enviada com outros dados.") from None
    return RedirectResponse(f"/caixa?data={data}&filial={filial}", status_code=303)

@router.get("/auditoria")
def auditoria(request: Request, pagina: int = 1, db: Session = Depends(get_db), usuario=Depends(get_admin)):
    pagina = max(1, pagina)
    consulta = db.query(AlteracaoEstoquePreco, Usuario.nome).outerjoin(Usuario, Usuario.id == AlteracaoEstoquePreco.usuario_id)
    return templates.TemplateResponse(request, "comercial/auditoria.html", {
        "usuario": usuario, "registros": consulta.order_by(AlteracaoEstoquePreco.id.desc()).offset((pagina-1)*50).limit(50).all(),
        "pagina": pagina, "paginas": max(1, (consulta.count()+49)//50),
    })

def categoria_cardapio(nome):
    texto = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower().replace("-", " ")
    return " ".join(texto.split())

@router.get("/cardapio")
def cardapio(request: Request, db: Session = Depends(get_db)):
    categorias = (("abre alas", "Abre Alas"), ("enredo", "Enredo"), ("maniacos por drink", "Maníacos por Drink"))
    grupos = {chave: [] for chave, _ in categorias}
    produtos = db.query(Produto).join(Categoria).options(joinedload(Produto.categoria)).filter(
        Produto.ativo == True, Categoria.ativo == True, Produto.preco.is_not(None),
    ).order_by(Produto.nome).all()
    for produto in produtos:
        chave = categoria_cardapio(produto.categoria.nome)
        if chave in grupos and produto.preco >= ZERO:
            grupos[chave].append(produto)
    return templates.TemplateResponse(request, "cardapio.html", {"categorias": categorias, "grupos": grupos})
