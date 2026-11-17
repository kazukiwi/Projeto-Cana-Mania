"""Endpoints autenticados da simulação SmartPDV RFID."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import get_usuario_logado
from app.services.rfid_demo import RFIDComunicacaoError, obter_maquininha

router = APIRouter(prefix="/pdv/rfid", tags=["RFID demo"])


def _usuario_id(usuario: dict) -> int:
    try:
        return int(usuario["id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Sessão inválida.") from None


def _resposta_transacao(id_transacao: str, usuario_id: int):
    try:
        transacao = obter_maquininha().consultar(id_transacao)
    except RFIDComunicacaoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    if not transacao or transacao.get("usuario_id") != usuario_id:
        raise HTTPException(status_code=404, detail="Demonstração não encontrada.")
    transacao.pop("usuario_id", None)
    return transacao


@router.post("/iniciar")
async def iniciar(request: Request, usuario=Depends(get_usuario_logado)):
    try:
        dados = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Envie um JSON válido.") from None
    centavos = dados.get("centavos") if isinstance(dados, dict) else None
    operacao = dados.get("operacao", "pagar") if isinstance(dados, dict) else "pagar"
    if operacao not in {"pagar", "carregar"}:
        raise HTTPException(status_code=400, detail="Operacao RFID invalida.")
    if operacao == "carregar" and usuario.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Somente administradores podem carregar saldo de teste.")
    if type(centavos) is not int or not 1 <= centavos <= 999999:
        raise HTTPException(status_code=400, detail="Valor de demonstração inválido.")
    try:
        transacao = obter_maquininha().iniciar(centavos, _usuario_id(usuario), operacao)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except RFIDComunicacaoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return JSONResponse(transacao, status_code=201, headers={"Cache-Control": "no-store"})


@router.get("/status/{id_transacao}")
def consultar(id_transacao: str, usuario=Depends(get_usuario_logado)):
    return JSONResponse(_resposta_transacao(id_transacao, _usuario_id(usuario)), headers={"Cache-Control": "no-store"})


@router.post("/cancelar/{id_transacao}")
def cancelar(id_transacao: str, usuario=Depends(get_usuario_logado)):
    usuario_id = _usuario_id(usuario)
    transacao = _resposta_transacao(id_transacao, usuario_id)
    if transacao["status"] != "aguardando_tag":
        raise HTTPException(status_code=409, detail="A demonstração já terminou.")
    try:
        resultado = obter_maquininha().cancelar(id_transacao)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except RFIDComunicacaoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return JSONResponse(resultado, headers={"Cache-Control": "no-store"})