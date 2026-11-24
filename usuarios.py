"""Cria o primeiro administrador de forma interativa."""
from getpass import getpass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.auth import hash_senha
from app.database import Base, Session, engine
from app.models.usuario import Usuario


def criar_admin_inicial():
    # Permite bootstrap antes do primeiro start da aplicação.
    Base.metadata.create_all(bind=engine)

    with Session() as db:
        if db.query(Usuario.id).filter(Usuario.role == "admin").first():
            print("Já existe uma conta administradora. Entre pela tela de acesso da equipe.")
            return

        nome = input("Nome do administrador: ").strip()
        email = input("E-mail do administrador: ").strip().lower()
        senha = getpass("Senha (mínimo 8 caracteres): ")
        confirmar = getpass("Confirme a senha: ")

        if not nome or len(nome) > 100:
            raise ValueError("Informe um nome com até 100 caracteres.")
        if (
            not email or len(email) > 100 or email.count("@") != 1
            or email.startswith("@") or email.endswith("@")
            or any(caractere.isspace() for caractere in email)
        ):
            raise ValueError("Informe um e-mail válido com até 100 caracteres.")
        if len(senha) < 8 or len(senha.encode("utf-8")) > 72:
            raise ValueError("A senha deve ter pelo menos 8 caracteres e no máximo 72 bytes.")
        if senha != confirmar:
            raise ValueError("As senhas não coincidem.")
        if db.query(Usuario.id).filter(func.lower(Usuario.email) == email).first():
            raise ValueError("Este e-mail já pertence a outra conta.")

        db.add(Usuario(
            nome=nome,
            email=email,
            senha_hash=hash_senha(senha),
            role="admin",
            ativo=True,
        ))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError("Não foi possível criar a conta. Confira se o e-mail já está cadastrado.") from None

    print("Administrador criado. Acesse /auth/login para entrar.")


if __name__ == "__main__":
    try:
        criar_admin_inicial()
    except (EOFError, KeyboardInterrupt):
        print("Criação cancelada.")
    except ValueError as erro:
        print(erro)
