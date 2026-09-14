from pathlib import Path
import re

from sqlalchemy import Column, Integer, Float, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
IMAGEM_PADRAO_URL = "/static/img/produto_padrao.png"
LIMITE_ESTOQUE_BAIXO = 5


def ordenar_tamanhos(tamanhos):
    """Ordena numerações e tamanhos de vestuário do menor para o maior."""
    ordem_roupa = {"PPP": 10, "PP": 20, "P": 30, "M": 40, "G": 50, "GG": 60, "XG": 70, "XGG": 80, "UNICO": 90, "ÚNICO": 90}

    def chave(tamanho):
        nome = tamanho.nome.strip().upper()
        numero = re.fullmatch(r"(\d+)(?:[.,](\d+))?", nome)
        if numero:
            return (0, int(numero.group(1)), int(numero.group(2) or 0), nome)
        if nome in ordem_roupa:
            return (1, ordem_roupa[nome], 0, nome)
        return (2, 0, 0, nome)

    return sorted(tamanhos, key=chave)

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), unique=True, index=True)
    preco = Column(Float)
    estoque_atual = Column(Integer, nullable=False, default=0)
    possui_variacoes_tamanho = Column(Boolean, nullable=False, default=False, server_default="false")
    ativo = Column(Boolean, default=True)

    imagem_path = Column(String(255), nullable=True)

    categoria_id = Column(Integer, ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True)
    categoria = relationship("Categoria", back_populates="produtos")
    estoques_tamanho = relationship(
        "EstoqueTamanho", back_populates="produto", cascade="all, delete-orphan"
    )
    estoques_variacoes = relationship(
        "EstoqueVariacao", back_populates="produto", cascade="all, delete-orphan"
    )

    @property
    def eh_camiseta(self):
        """Compatibilidade com o fluxo antigo de vendas."""
        return self.possui_variacoes_tamanho

    @property
    def preco_exibicao(self):
        """Preço mostrado nas listagens; para variações, informa o maior valor possível."""
        if self.possui_variacoes_tamanho and self.estoques_variacoes:
            return max(variacao.preco for variacao in self.estoques_variacoes)
        return self.preco or 0.0

    def estoque_do_tamanho(self, tamanho_id):
        registro = next((e for e in self.estoques_tamanho if e.tamanho_id == tamanho_id), None)
        return registro.estoque_atual if registro else 0

    @property
    def variacoes_com_estoque_baixo(self):
        """Variações cujo saldo individual atingiu o limite de alerta."""
        if not self.possui_variacoes_tamanho:
            return []
        return [
            variacao
            for variacao in self.estoques_variacoes
            if variacao.estoque_atual <= LIMITE_ESTOQUE_BAIXO
        ]

    @property
    def estoque_baixo(self):
        """Indica estoque baixo no total ou em ao menos uma variação."""
        if self.possui_variacoes_tamanho and self.estoques_variacoes:
            return bool(self.variacoes_com_estoque_baixo)
        return self.estoque_atual <= LIMITE_ESTOQUE_BAIXO

    @property
    def imagem_url(self):
        # 1. Se não houver imagem guardada no banco de dados, retorna a imagem padrão do sistema
        if not self.imagem_path:
            return IMAGEM_PADRAO_URL

        # Remove espaços em branco extras que possam existir no início ou fim
        imagem_path = self.imagem_path.strip()

        # 2. Se já for um link externo completo (http:// ou https://), retorna diretamente
        if imagem_path.startswith(("http://", "https://")):
            return imagem_path

        # 3. Limpa barras iniciais para evitar caminhos duplicados como '//static'
        path_limpo = imagem_path.lstrip('/').replace("\\", "/")

        # 4. Se o banco já gravou o caminho começando com "static/uploads/"
        if path_limpo.startswith("static/"):
            path_limpo = path_limpo.removeprefix("static/")

        # Confirma que o arquivo existe dentro de static antes de gerar uma URL.
        # Assim, registros antigos que apontam para uploads removidos usam o fallback.
        arquivo = (STATIC_DIR / path_limpo).resolve()
        try:
            arquivo.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return IMAGEM_PADRAO_URL

        if not arquivo.is_file():
            return IMAGEM_PADRAO_URL

        return f"/static/{path_limpo}"


class Tamanho(Base):
    __tablename__ = "tamanhos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(30), nullable=False, unique=True, index=True)
    ordem = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=True, server_default="true")

    estoques = relationship("EstoqueTamanho", back_populates="tamanho")


class EstoqueTamanho(Base):
    __tablename__ = "estoques_tamanho"
    __table_args__ = (UniqueConstraint("produto_id", "tamanho_id", name="uq_estoque_tamanho_produto_id"),)

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False)
    tamanho_id = Column(Integer, ForeignKey("tamanhos.id", ondelete="RESTRICT"), nullable=False)
    estoque_atual = Column(Integer, nullable=False, default=0)

    produto = relationship("Produto", back_populates="estoques_tamanho")
    tamanho = relationship("Tamanho", back_populates="estoques")


class EstoqueVariacao(Base):
    """Saldo de uma combinação específica de tamanho e cor."""

    __tablename__ = "estoques_variacoes"
    __table_args__ = (
        UniqueConstraint("produto_id", "tamanho_id", "cor", name="uq_estoque_variacao_produto_tamanho_cor"),
    )

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False)
    tamanho_id = Column(Integer, ForeignKey("tamanhos.id", ondelete="RESTRICT"), nullable=False)
    cor = Column(String(50), nullable=False)
    estoque_atual = Column(Integer, nullable=False, default=0)
    preco = Column(Float, nullable=False, default=0.0)

    produto = relationship("Produto", back_populates="estoques_variacoes")
    tamanho = relationship("Tamanho")


def condicao_estoque_baixo(limite: int = LIMITE_ESTOQUE_BAIXO):
    """Condição SQL para localizar produtos com total ou variação em nível baixo."""
    return (Produto.estoque_atual <= limite) | Produto.estoques_variacoes.any(
        EstoqueVariacao.estoque_atual <= limite
    )
