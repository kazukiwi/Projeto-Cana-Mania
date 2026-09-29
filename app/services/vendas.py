import hashlib
import json
from uuid import UUID
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.models.venda import Venda, ItemVenda
from app.models.produtos import Produto, CATEGORIAS_PDV
from app.models.categoria import Categoria
from app.models.filial import EstoqueFilial, FILIAIS
from app.money import dinheiro, ZERO

PAGAMENTOS = ("credito", "debito", "dinheiro", "pix", "convite")

def normalizar_pedido(carrinho_json, filial, pagamento, observacao):
    if filial not in FILIAIS or pagamento not in PAGAMENTOS:
        raise HTTPException(400, "Confira a loja e a forma de pagamento.")
    try:
        itens = json.loads(carrinho_json)
        if not isinstance(itens, list) or not 1 <= len(itens) <= 500:
            raise ValueError()
        quantidades = {}
        for item in itens:
            if not isinstance(item, dict):
                raise ValueError()
            produto_id, quantidade = item.get("produto_id"), item.get("quantidade")
            if type(produto_id) is not int or type(quantidade) is not int or produto_id <= 0 or not 1 <= quantidade <= 100000:
                raise ValueError()
            # O PDV atual vende o produto base, sem tamanhos e cores.
            if item.get("tamanho_id") or item.get("cor"):
                raise ValueError()
            quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade
        if any(q > 100000 for q in quantidades.values()) or len(observacao) > 255:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(400, "Carrinho inválido. Confira as quantidades.") from None
    dados = [sorted(quantidades.items()), filial, pagamento, observacao.strip()]
    digest = hashlib.sha256(json.dumps(dados, ensure_ascii=True).encode()).hexdigest()
    return quantidades, digest

def validar_token(token):
    try:
        return str(UUID(token))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Identificador da venda inválido. Recarregue o PDV.") from None

def conferir_repeticao(venda, usuario_id, digest):
    if venda.usuario_id != usuario_id or venda.pedido_hash != digest:
        raise HTTPException(409, "Este pedido já foi enviado com outros dados. Abra uma nova venda.")
    return venda

def registrar_venda(db, usuario_id, token, carrinho_json, filial, pagamento, observacao=""):
    token = validar_token(token)
    quantidades, digest = normalizar_pedido(carrinho_json, filial, pagamento, observacao)
    existente = db.query(Venda).filter_by(pedido_token=token).first()
    if existente:
        return conferir_repeticao(existente, usuario_id, digest)
    venda = Venda(
        usuario_id=usuario_id, filial=filial, pedido_token=token, pedido_hash=digest,
        forma_pagamento=pagamento, observacao=observacao.strip() or None,
        desconto_percentual=0, total_bruto=ZERO, total_liquido=ZERO,
        criado_em=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.info.update(usuario_id=usuario_id, origem="pdv/venda")
    try:
        # A restrição UNIQUE arbitra tentativas concorrentes ANTES de alterar estoque.
        db.add(venda)
        db.flush()
        total = ZERO
        for produto_id, quantidade in sorted(quantidades.items()):
            produto = (
                db.query(Produto).join(Categoria)
                .filter(Produto.id == produto_id, Produto.ativo == True, Categoria.ativo == True,
                        func.lower(Categoria.nome).in_(CATEGORIAS_PDV))
                .with_for_update().first()
            )
            if not produto:
                raise HTTPException(400, "Um produto não está mais disponível.")
            try:
                preco = dinheiro(produto.preco)
            except ValueError:
                raise HTTPException(400, "Produto com preço inválido.") from None
            if preco < ZERO:
                raise HTTPException(400, "Produto com preço inválido.")
            if not produto.eh_consumo:
                saldo = db.query(EstoqueFilial).filter_by(produto_id=produto.id, filial=filial).with_for_update().first()
                if not saldo or saldo.quantidade < quantidade or produto.estoque_atual < quantidade:
                    raise HTTPException(400, f"Estoque insuficiente para {produto.nome} na loja selecionada.")
                saldo.quantidade -= quantidade
                produto.estoque_atual -= quantidade
            total += preco * quantidade
            db.add(ItemVenda(venda_id=venda.id, produto_id=produto.id, produto_nome=produto.nome,
                             quantidade=quantidade, preco_unitario=preco))
        venda.total_bruto = dinheiro(total)
        venda.total_liquido = dinheiro(total)
        db.commit()
        return venda
    except IntegrityError:
        db.rollback()
        existente = db.query(Venda).filter_by(pedido_token=token).first()
        if existente:
            return conferir_repeticao(existente, usuario_id, digest)
        raise
    except Exception:
        db.rollback()
        raise
