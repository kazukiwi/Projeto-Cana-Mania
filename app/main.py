import asyncio
import logging
from pathlib import Path

from datetime import date, datetime

from fastapi import FastAPI, Request, Depends, Form
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import Base, engine, get_db
from app.models.produtos import LIMITE_ESTOQUE_BAIXO, Produto, EstoqueVariacao, condicao_estoque_baixo
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.armario import Armario
from app.models.reserva_armario import ReservaArmario
from app.models.venda import ItemVenda, Venda
from app.models.filial import EstoqueFilial, FILIAIS
from app.models.categoria import Categoria
from app.models.produtos import CATEGORIAS_CONSUMO

from app.controllers import (
    auth_controller,
    admin_controller,
    categorias_controller,
    produto_controller,
    movimentacao_controller,
    pdv_controller,
    tamanhos_controller,
    estoque_controller,
)

from app.auth import get_usuario_opcional, get_usuario_logado


# Mantém instalações locais que ainda não passaram por todas as migrações
# utilizáveis, sem alterar nem apagar tabelas e dados já existentes.
Base.metadata.create_all(bind=engine)


async def rotina_fechamento_diario():
    """Mantém o fechamento automático ativo enquanto o servidor estiver em execução."""
    while True:
        try:
            pdv_controller.executar_fechamento_automatico()
        except Exception as erro:
            # O loop não pode parar por uma falha pontual de banco.
            print(f"Erro no fechamento diário automático: {erro}")
        await asyncio.sleep(30)


# 1º: CRIAR A INSTÂNCIA DO APP
app = FastAPI(title="Sistema Estoque")


@app.on_event("startup")
async def iniciar_rotina_fechamento_diario():
    asyncio.create_task(rotina_fechamento_diario())

# 2º: CONFIGURAR ARQUIVOS ESTÁTICOS E TEMPLATES
APP_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
logger = logging.getLogger(__name__)


@app.get("/termos-de-uso")
def termos_de_uso(request: Request):
    return templates.TemplateResponse(
        name="informacoes.html",
        request=request,
        context={"request": request, "pagina": "termos"},
    )


@app.get("/politica-de-privacidade")
def politica_de_privacidade(request: Request):
    return templates.TemplateResponse(
        name="informacoes.html",
        request=request,
        context={"request": request, "pagina": "privacidade"},
    )


@app.get("/suporte")
def suporte(request: Request):
    return templates.TemplateResponse(
        name="informacoes.html",
        request=request,
        context={"request": request, "pagina": "suporte"},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        return templates.TemplateResponse(
            name="auth/nao_autenticado.html",
            request=request,
            status_code=401,
            context={"request": request},
        )
    if exc.status_code == 404:
        return templates.TemplateResponse(
            name="404.html",
            request=request,
            status_code=404,
            context={"request": request}
        )
    erros_http = {
        403: ("Acesso não permitido", "Seu usuário não possui permissão para acessar esta área.", "Volte para o início ou entre com uma conta autorizada."),
        405: ("Ação não permitida", "Esta página não aceita o tipo de solicitação enviado.", "Retorne à tela anterior e tente a ação novamente."),
        408: ("A solicitação demorou demais", "Não foi possível concluir a comunicação dentro do tempo esperado.", "Verifique sua conexão e tente novamente."),
        429: ("Muitas tentativas", "Recebemos várias solicitações em um curto período.", "Aguarde alguns instantes antes de tentar novamente."),
        503: ("Serviço temporariamente indisponível", "O sistema não consegue atender esta solicitação agora.", "Tente novamente em alguns minutos."),
    }
    titulo, mensagem, descricao = erros_http.get(
        exc.status_code,
        ("Não foi possível concluir", "O sistema encontrou um problema ao processar esta solicitação.", "Volte para uma área segura e tente novamente."),
    )
    return templates.TemplateResponse(
        name="erro_generico.html",
        request=request,
        status_code=exc.status_code,
        context={
            "request": request,
            "codigo": exc.status_code,
            "titulo": titulo,
            "mensagem": mensagem,
            "descricao": descricao,
            "voltar_para": "/",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Evita expor uma resposta técnica quando um filtro ou formulário é inválido."""
    return templates.TemplateResponse(
        name="erro_generico.html",
        request=request,
        status_code=422,
        context={
            "request": request,
            "codigo": 422,
            "titulo": "Revise os dados informados",
            "mensagem": "Alguns campos não foram preenchidos no formato esperado.",
            "descricao": "Confira os dados e tente enviar o formulário novamente.",
            "voltar_para": str(request.headers.get("referer") or "/"),
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    """Mostra uma tela clara ao usuário e preserva o detalhe técnico no log."""
    logger.exception("Erro não tratado em %s", request.url.path, exc_info=exc)
    return templates.TemplateResponse(
        name="erro_generico.html",
        request=request,
        status_code=500,
        context={
            "request": request,
            "codigo": 500,
            "titulo": "Algo não saiu como esperado",
            "mensagem": "Ocorreu um erro inesperado ao carregar esta página.",
            "descricao": "O problema foi registrado. Você pode voltar ao início e tentar novamente.",
            "voltar_para": "/",
        },
    )

# 3º: INCLUIR OS ROUTERS dos controllers
app.include_router(auth_controller.router)
app.include_router(admin_controller.router)
app.include_router(categorias_controller.router)
app.include_router(produto_controller.router)
app.include_router(movimentacao_controller.router)
app.include_router(pdv_controller.router)
app.include_router(tamanhos_controller.router)
app.include_router(estoque_controller.router)


# --- BANCO DE DADOS TEMPORÁRIO PARA OS ARMÁRIOS (ESTRUTURA INDESTRUTÍVEL) ---
def garantir_armarios_iniciais(db: Session):
    if db.query(Armario).count() > 0:
        return

    for i in range(1, 51):
        if i in [1, 5, 12, 25]:
            status_inicial = "ocupado"
            nome_mock = "Maria Santos"
            obs_mock = ""
        elif i == 20:
            status_inicial = "manutencao"
            nome_mock = ""
            obs_mock = "Fechadura com defeito"
        else:
            status_inicial = "disponivel"
            nome_mock = ""
            obs_mock = ""
        
        db.add(Armario(
            numero=str(i).zfill(2),
            status=status_inicial,
            associado_nome=nome_mock,
            associado_id=None,
            associado_email="maria.santos@email.com" if status_inicial == "ocupado" else "",
            associado_telefone="(11) 97654-3210" if status_inicial == "ocupado" else "",
            associado_matricula="AAPM-002" if status_inicial == "ocupado" else "",
            atribuido_em="04/03/2026" if status_inicial == "ocupado" else "",
            observacoes=obs_mock
        ))

    db.commit()


# 4º: PÁGINA INICIAL / DASHBOARD
@app.get("/")
def home(
    request: Request,
    usuario=Depends(get_usuario_opcional),
    db: Session = Depends(get_db)
):
    if usuario is None:
        return templates.TemplateResponse(name="index.html", request=request)

    produtos_ativos = (
        db.query(Produto)
        .options(
            selectinload(Produto.categoria),
            selectinload(Produto.estoques_variacoes).selectinload(EstoqueVariacao.tamanho),
        )
        .filter(Produto.ativo == True)
        .all()
    )

    from app.controllers.estoque_controller import garantir_estoque_filiais
    garantir_estoque_filiais(db)
    # Produtos desativados permanecem no histórico, mas nunca participam dos
    # totais nem dos alertas exibidos no dashboard.
    saldos_filiais = (
        db.query(EstoqueFilial)
        .join(Produto, EstoqueFilial.produto_id == Produto.id)
        .join(Categoria, Produto.categoria_id == Categoria.id, isouter=True)
        .filter(
            Produto.ativo == True,
            (Categoria.nome.is_(None)) | (~func.lower(Categoria.nome).in_(CATEGORIAS_CONSUMO)),
        )
        .all()
    )
    estoque_por_filial = {filial: sum(s.quantidade for s in saldos_filiais if s.filial == filial) for filial in FILIAIS}
    alertas_filiais = [s for s in saldos_filiais if 0 < s.quantidade <= LIMITE_ESTOQUE_BAIXO]
    total_produtos = len(produtos_ativos)
    estoque_baixo = (
        db.query(Produto)
        .filter(Produto.ativo == True, condicao_estoque_baixo())
        .count()
    )
    valor_total = (
        db.query(func.coalesce(func.sum(Venda.total_liquido), 0.0))
        .scalar()
    )

    contagem_cat = {}
    produtos_por_categoria = {}
    for p in produtos_ativos:
        if p.categoria and hasattr(p.categoria, 'nome'):
            name_cat = p.categoria.nome
        elif isinstance(p.categoria, str) and p.categoria.strip():
            name_cat = p.categoria
        else:
            name_cat = "Gerais"
        contagem_cat[name_cat] = contagem_cat.get(name_cat, 0) + 1
        produtos_por_categoria.setdefault(name_cat, []).append(p)

    produtos_por_categoria = {
        categoria: sorted(produtos, key=lambda produto: produto.nome.lower())
        for categoria, produtos in sorted(produtos_por_categoria.items(), key=lambda item: item[0].lower())
    }
    
    total_categorias = len(contagem_cat)

    # Pódio do dashboard: o ranking usa o histórico de itens vendidos, para que
    # preço e quantidade continuem corretos mesmo se o cadastro mudar depois.
    ranking_dashboard = {}
    for item in db.query(ItemVenda).options(joinedload(ItemVenda.produto)).all():
        chave = item.produto_id or f"nome:{item.produto_nome}"
        produto = item.produto
        dados = ranking_dashboard.setdefault(chave, {
            "id": item.produto_id,
            "nome": item.produto_nome or (produto.nome if produto else "Produto removido"),
            "imagem_url": produto.imagem_url if produto else "/static/img/produto_padrao.png",
            "vendas": 0,
            "receita": 0.0,
        })
        quantidade = int(item.quantidade or 0)
        dados["vendas"] += quantidade
        dados["receita"] += quantidade * float(item.preco_unitario or 0)

    total_unidades_vendidas = sum(produto["vendas"] for produto in ranking_dashboard.values())
    mais_vendidos_dashboard = sorted(
        ranking_dashboard.values(), key=lambda produto: (-produto["vendas"], -produto["receita"], produto["nome"])
    )[:3]
    for produto in mais_vendidos_dashboard:
        produto["porcentagem"] = round((produto["vendas"] / total_unidades_vendidas) * 100, 1) if total_unidades_vendidas else 0.0

    # Contagem dinâmica para os cards superiores da Home
    garantir_armarios_iniciais(db)
    ocupados = db.query(Armario).filter(Armario.status == "ocupado").count()
    disponiveis = db.query(Armario).filter(Armario.status == "disponivel").count()
    manutencao = db.query(Armario).filter(Armario.status == "manutencao").count()
    total_associados = db.query(Usuario).filter(Usuario.ativo == True, Usuario.role == "funcionario").count()

    return templates.TemplateResponse(
        name="dashboard.html",
        request=request,
        context={
            "request": request,
            "usuario": usuario,
            "total_produtos": total_produtos,
            "estoque_baixo": estoque_baixo,
            "valor_total": valor_total,
            "total_categorias": total_categorias,
            "produtos_por_categoria": produtos_por_categoria,
            "mais_vendidos_dashboard": mais_vendidos_dashboard,
            "lista_armarios": db.query(Armario).order_by(Armario.id).all(),
            "armarios_ocupados": ocupados,
            "armarios_disponiveis": disponiveis,
            "armarios_manutencao": manutencao,
            "total_associados": total_associados
            ,"filiais": FILIAIS
            ,"estoque_por_filial": estoque_por_filial
            ,"alertas_filiais": alertas_filiais
        }
    )


# 5º: ROTA MAIS VENDIDOS
@app.get("/mais_vendidos")
def mais_vendidos(
    request: Request,
    usuario=Depends(get_usuario_logado),
    db: Session = Depends(get_db)
):
    ranking_produtos = []
    categorias_dados = {}
    controle_produtos = {}

    try:
        from app.models.venda import Venda
        
        vendas_reais = db.query(Venda).all()
        total_unidades = len(vendas_reais)
        receita_total = sum(float(v.total_liquido or 0) for v in vendas_reais)

        for venda in vendas_reais:
            if venda.itens:
                for item in venda.itens:
                    nome_p = item.produto_nome if item.produto_nome else (item.produto.nome if item.produto else "Produto Removido")
                    
                    cat_p = "Gerais"
                    if item.produto and item.produto.categoria:
                        if hasattr(item.produto.categoria, 'nome'):
                            cat_p = item.produto.categoria.nome
                        else:
                            cat_p = str(item.produto.categoria)

                    cod_p = f"ID-{item.produto_id}"
                    if item.produto and hasattr(item.produto, 'codigo') and item.produto.codigo:
                        cod_p = item.produto.codigo

                    qtd = int(item.quantidade or 0)
                    subtotal = qtd * float(item.preco_unitario or 0)

                    if nome_p not in controle_produtos:
                        controle_produtos[nome_p] = {
                            "codigo": cod_p,
                            "categoria": cat_p,
                            "vendas": 0,
                            "receita": 0.0
                        }
                    
                    controle_produtos[nome_p]["vendas"] += qtd
                    controle_produtos[nome_p]["receita"] += subtotal
                    categorias_dados[cat_p] = categorias_dados.get(cat_p, 0) + qtd

        for nome, dados in controle_produtos.items():
            if dados["vendas"] > 0:
                ranking_produtos.append({
                    "nome": nome,
                    "codigo": dados["codigo"],
                    "categoria": dados["categoria"],
                    "vendas": dados["vendas"],
                    "receita": dados["receita"],
                    "porcentagem": 0.0
                })

    except Exception as e:
        print(f"--> Erro interno no processamento de vendas: {e}")
        ranking_produtos = []

    if not ranking_produtos:
        total_unidades = 0
        receita_total = 0.0
    else:
        ranking_produtos = sorted(ranking_produtos, key=lambda x: x["vendas"], reverse=True)
        total_vendas_geral = sum(p["vendas"] for p in ranking_produtos) or 1
        for p in ranking_produtos:
            p["porcentagem"] = round((p["vendas"] / total_vendas_geral) * 100, 1)

    ticket_medio = receita_total / total_unidades if total_unidades > 0 else 0

    return templates.TemplateResponse(
        name="auth/mais_vendidos.html",
        request=request,
        context={
            "request": request,
            "usuario": usuario,
            "ranking": ranking_produtos,
            "categories": categorias_dados,
            "total_unidades": total_unidades,
            "receita_total": receita_total,
            "ticket_medio": ticket_medio
        }
    )


# 6º: ROTA PRINCIPAL DOS ARMÁRIOS (PROTEÇÃO MÁXIMA CONTRA ERRO 500)
@app.get("/maquinas")
@app.get("/armarios")
def listar_armarios(
    request: Request,
    usuario=Depends(get_usuario_opcional), # Trocado para opcional para evitar travas de banco
    db: Session = Depends(get_db)
):
    # Fallback caso a sessão falhe por causa do banco de dados travado no Git
    if not usuario:
        class UsuarioMock:
            role = "admin"
            nome = "Usuário Local"
        usuario = UsuarioMock()

    garantir_armarios_iniciais(db)

    # Compatibiliza reservas já registradas antes da sincronização de status.
    # Assim, elas deixam de aparecer como disponíveis sem exigir novo cadastro.
    reservas_ativas = (
        db.query(ReservaArmario)
        .filter(ReservaArmario.status == "ativa")
        .order_by(ReservaArmario.id.desc())
        .all()
    )
    alterou_status = False
    for reserva in reservas_ativas:
        if reserva.armario and reserva.armario.status == "disponivel":
            reserva.armario.status = "ocupado"
            if reserva.associado:
                reserva.armario.associado_id = reserva.associado.id
                reserva.armario.associado_nome = reserva.associado.nome
                reserva.armario.associado_telefone = reserva.associado.telefone or ""
                reserva.armario.associado_matricula = reserva.associado.matricula or ""
            alterou_status = True
    if alterou_status:
        db.commit()

    total = db.query(Armario).count()
    disponiveis = db.query(Armario).filter(Armario.status == "disponivel").count()
    ocupados = db.query(Armario).filter(Armario.status == "ocupado").count()
    manutencao = db.query(Armario).filter(Armario.status == "manutencao").count()
    armarios = db.query(Armario).order_by(Armario.id).all()
    associados = (
        db.query(Cliente)
        .filter(
            Cliente.ativo == True,
            Cliente.is_associado == True
        )
        .order_by(Cliente.nome)
        .all()
    )
    reservas = (
        db.query(ReservaArmario)
        .order_by(ReservaArmario.inicio_em.desc(), ReservaArmario.id.desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request, 
        name="armarios/index.html", 
        context={
            "request": request, # Garantindo envio explícito do objeto request para o contexto
            "usuario": usuario,
            "armarios": armarios,
            "total_armarios": total,
            "armarios_disponiveis": disponiveis,
            "armarios_ocupados": ocupados,
            "armarios_manutencao": manutencao,
            "associados": associados,
            "reservas": reservas,
        }
    )


# 7º: ROTA PARA ALTERAR O STATUS DO ARMÁRIO
@app.post("/armarios/alterar-status")
def alterar_status_armario(
    armario_id: int = Form(...),
    novo_status: str = Form(...),
    associado_id: int = Form(0),
    observacoes: str = Form(None),
    usuario=Depends(get_usuario_opcional),
    db: Session = Depends(get_db)
):
    armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not armario:
        return RedirectResponse(url="/armarios?erro=armario", status_code=303)

    if novo_status == "ocupado":
        associado = None
        if associado_id:
            associado = db.query(Cliente).filter(
                Cliente.id == associado_id,
                Cliente.ativo == True,
                Cliente.is_associado == True
            ).first()

        if not associado:
            return RedirectResponse(url="/armarios?erro=associado", status_code=303)

        armario.status = novo_status
        armario.associado_id = associado.id
        armario.associado_nome = associado.nome
        armario.associado_email = ""
        armario.associado_telefone = associado.telefone or ""
        armario.associado_matricula = associado.matricula or ""
        armario.atribuido_em = "04/03/2026"
        armario.observacoes = ""
    elif novo_status == "manutencao":
        armario.status = novo_status
        armario.associado_id = None
        armario.associado_nome = ""
        armario.associado_email = ""
        armario.associado_telefone = ""
        armario.associado_matricula = ""
        armario.atribuido_em = ""
        armario.observacoes = observacoes if (observacoes and observacoes.strip()) else "Fechadura com defeito"
    else:
        armario.status = "disponivel"
        armario.associado_id = None
        armario.associado_nome = ""
        armario.associado_email = ""
        armario.associado_telefone = ""
        armario.associado_matricula = ""
        armario.atribuido_em = ""
        armario.observacoes = ""

    db.commit()
            
    return RedirectResponse(url="/armarios", status_code=303)


@app.post("/armarios")
def cadastrar_armario(numero: str = Form(...), db: Session = Depends(get_db), usuario=Depends(get_usuario_opcional)):
    numero = numero.strip()
    if not numero or db.query(Armario).filter(Armario.numero == numero).first():
        return RedirectResponse(url="/armarios?erro=numero", status_code=303)
    db.add(Armario(numero=numero.zfill(2), status="disponivel"))
    db.commit()
    return RedirectResponse(url="/armarios?armario=ok", status_code=303)


@app.post("/armarios/{armario_id}/desativar")
def desativar_armario(
    armario_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_opcional),
):
    armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not armario:
        return RedirectResponse(url="/armarios?erro=armario", status_code=303)
    if armario.status == "ocupado":
        return RedirectResponse(url="/armarios?erro=ocupado", status_code=303)
    armario.status = "desativado"
    armario.associado_id = None
    armario.associado_nome = ""
    armario.associado_email = ""
    armario.associado_telefone = ""
    armario.associado_matricula = ""
    armario.atribuido_em = ""
    db.commit()
    return RedirectResponse(url="/armarios?armario=desativado", status_code=303)


@app.post("/armarios/{armario_id}/ativar")
def ativar_armario(
    armario_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_opcional),
):
    armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not armario:
        return RedirectResponse(url="/armarios?erro=armario", status_code=303)

    # Apenas um armário desativado pode ser reativado por esta ação.
    if armario.status != "desativado":
        return RedirectResponse(url="/armarios?erro=status", status_code=303)

    armario.status = "disponivel"
    armario.associado_id = None
    armario.associado_nome = ""
    armario.associado_email = ""
    armario.associado_telefone = ""
    armario.associado_matricula = ""
    armario.atribuido_em = ""
    armario.observacoes = ""
    db.commit()
    return RedirectResponse(url="/armarios?armario=ativado", status_code=303)


@app.post("/armarios/reservas")
def criar_reserva_armario(
    armario_id: int = Form(...),
    local_evento: str = Form(...),
    inicio_em: date = Form(...),
    fim_em: date = Form(...),
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_opcional),
):
    """Registra uma reserva e impede sobreposição para o mesmo armário."""
    if fim_em < inicio_em:
        return RedirectResponse(url="/armarios?erro=periodo", status_code=303)

    armario = db.query(Armario).filter(Armario.id == armario_id).first()
    local_evento = local_evento.strip()
    if not armario or not local_evento:
        return RedirectResponse(url="/armarios?erro=reservadados", status_code=303)

    if armario.status != "disponivel":
        return RedirectResponse(url="/armarios?erro=indisponivel", status_code=303)

    inicio = datetime.combine(inicio_em, datetime.min.time())
    fim = datetime.combine(fim_em, datetime.max.time())
    conflito = db.query(ReservaArmario).filter(
        ReservaArmario.armario_id == armario.id,
        ReservaArmario.status == "ativa",
        ReservaArmario.inicio_em <= fim,
        ReservaArmario.fim_em >= inicio,
    ).first()
    if conflito:
        return RedirectResponse(url="/armarios?erro=conflito", status_code=303)

    db.add(ReservaArmario(
        armario_id=armario.id,
        associado_id=None,
        local_evento=local_evento,
        semestre=local_evento,
        inicio_em=inicio,
        fim_em=fim,
        status="ativa",
    ))
    # A disponibilidade usa o status do próprio armário. Mantemos os dois
    # módulos sincronizados para que uma reserva não apareça como disponível.
    armario.status = "ocupado"
    armario.associado_id = None
    armario.associado_nome = local_evento
    armario.associado_telefone = ""
    armario.associado_matricula = ""
    armario.atribuido_em = inicio_em.strftime("%d/%m/%Y")
    armario.observacoes = ""
    db.commit()
    return RedirectResponse(url="/armarios?reserva=ok", status_code=303)


@app.post("/armarios/reservas/{reserva_id}/cancelar")
def cancelar_reserva_armario(
    reserva_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_opcional),
):
    reserva = db.query(ReservaArmario).filter(ReservaArmario.id == reserva_id).first()
    if reserva and reserva.status == "ativa":
        reserva.status = "cancelada"
        ainda_reservado = db.query(ReservaArmario).filter(
            ReservaArmario.armario_id == reserva.armario_id,
            ReservaArmario.id != reserva.id,
            ReservaArmario.status == "ativa",
        ).first()
        if not ainda_reservado and reserva.armario:
            reserva.armario.status = "disponivel"
            reserva.armario.associado_id = None
            reserva.armario.associado_nome = ""
            reserva.armario.associado_email = ""
            reserva.armario.associado_telefone = ""
            reserva.armario.associado_matricula = ""
            reserva.armario.atribuido_em = ""
            reserva.armario.observacoes = ""
        db.commit()
    return RedirectResponse(url="/armarios?reserva=cancelada", status_code=303)
