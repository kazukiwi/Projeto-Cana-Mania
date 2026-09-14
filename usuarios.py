from app.database import Session, engine, Base
from app.models.usuario import Usuario
from app.auth import hash_senha

Usuarios = [
    {
    "nome": "Admin",
    "email": "admin2@example.com",
    "senha": "admin@123456",
    "role": "admin"
    }
]

def criar_usuarios():
    db = Session()

    try:
        for usuario in Usuarios:
            existente = db.query(Usuario).filter(Usuario.email == usuario["email"]).first()
            if existente:
                print(f"Usuário {usuario['email']} já existe. Pulando...")
                continue
            novo_usuario = Usuario(
                nome=usuario["nome"],
                email=usuario["email"],
                senha_hash= hash_senha(usuario["senha"]),
                role=usuario["role"]
            )
            db.add(novo_usuario)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Erro ao criar usuários: {e}")
    finally:
        db.close()

criar_usuarios()