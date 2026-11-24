"""Populate the Canamania beverage and snack catalog."""
from alembic import op
import sqlalchemy as sa


revision = "ff03c4d5e6f7"
down_revision = "ff02a3b4c5d6"
branch_labels = None
depends_on = None


PRODUCTS = (
    ("Dan\u00e7a Siciliana", "Abre-Alas", 25.0),
    ("Cana Cl\u00e1ssico", "Abre-Alas", 25.0),
    ("Cana Princesa", "Abre-Alas", 25.0),
    ("Mango Tropical", "Abre-Alas", 25.0),
    ("Doce Paix\u00e3o", "Abre-Alas", 25.0),
    ("Cahana", "Abre-Alas", 25.0),
    ("Canacchino", "Abre-Alas", 25.0),
    ("Canatch\u00e1", "Abre-Alas", 25.0),
    ("Cana Mix", "Abre-Alas", 28.0),
    ("Cana M\u00e1gica", "Enredo", 30.0),
    ("Encanto", "Enredo", 30.0),
    ("Rota da Cana", "Enredo", 30.0),
    ("Mango Coco", "Enredo", 30.0),
    ("Paix\u00e3o de Cacau", "Enredo", 30.0),
    ("Bacanaoffe", "Enredo", 33.0),
    ("Cana Cacau", "Enredo", 30.0),
    ("Canatch\u00e1 Leite", "Enredo", 30.0),
    ("Cocanas", "Enredo", 30.0),
    ("Canarinha", "Maniacos por drink", 35.0),
    ("Caipicolada", "Maniacos por drink", 35.0),
    ("Caiprincesa", "Maniacos por drink", 35.0),
    ("Baile Siciliano", "Maniacos por drink", 35.0),
    ("Ginga Tropical", "Maniacos por drink", 35.0),
    ("Louca Paix\u00e3o", "Maniacos por drink", 35.0),
    ("Bacanininha", "Maniacos por drink", 35.0),
    ("Ai Mo da Cana", "Maniacos por drink", 35.0),
    ("Pinhado Louco", "Maniacos por drink", 35.0),
    ("Kampai", "Maniacos por drink", 35.0),
    ("Palitinho Cl\u00e1ssico", "Palitinho de Cana", 15.0),
    ("Palitinho Morango", "Palitinho de Cana", 15.0),
    ("Palitinho Maracuj\u00e1", "Palitinho de Cana", 15.0),
    ("Palitinho Manga", "Palitinho de Cana", 15.0),
    ("Palitinho Lim\u00e3o Taiti", "Palitinho de Cana", 15.0),
    ("Palitinho Abacaxi", "Palitinho de Cana", 15.0),
)

NEW_PRODUCTS = tuple(
    name for name, category, price in PRODUCTS
    if name not in {"Cana Cl\u00e1ssico", "Cana Princesa", "Encanto"}
)


def upgrade():
    connection = op.get_bind()
    category_ids = {}
    for _, category, _ in PRODUCTS:
        if category in category_ids:
            continue
        category_id = connection.execute(
            sa.text("SELECT id FROM categorias WHERE lower(nome) = lower(:nome)"),
            {"nome": category},
        ).scalar_one_or_none()
        if category_id is None:
            connection.execute(
                sa.text("INSERT INTO categorias (nome, ativo) VALUES (:nome, :ativo)"),
                {"nome": category, "ativo": True},
            )
            category_id = connection.execute(
                sa.text("SELECT id FROM categorias WHERE lower(nome) = lower(:nome)"),
                {"nome": category},
            ).scalar_one()
        category_ids[category] = category_id

    for name, category, price in PRODUCTS:
        existing_id = connection.execute(
            sa.text("SELECT id FROM produtos WHERE lower(nome) = lower(:nome)"),
            {"nome": name},
        ).scalar_one_or_none()
        values = {"nome": name, "preco": price, "categoria_id": category_ids[category]}
        if existing_id is None:
            connection.execute(
                sa.text(
                    "INSERT INTO produtos "
                    "(nome, preco, estoque_atual, possui_variacoes_tamanho, ativo, imagem_path, categoria_id) "
                    "VALUES (:nome, :preco, 0, :variacoes, :ativo, NULL, :categoria_id)"
                ),
                {**values, "variacoes": False, "ativo": True},
            )
        else:
            connection.execute(
                sa.text("UPDATE produtos SET preco = :preco, categoria_id = :categoria_id WHERE id = :id"),
                {**values, "id": existing_id},
            )


def downgrade():
    connection = op.get_bind()
    for name in NEW_PRODUCTS:
        connection.execute(
            sa.text("DELETE FROM produtos WHERE lower(nome) = lower(:nome)"),
            {"nome": name},
        )
    connection.execute(
        sa.text("UPDATE produtos SET preco = 28 WHERE lower(nome) = lower('Encanto')")
    )
