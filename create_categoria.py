from app.database import Session
from app.models.categoria import Categoria

db = Session()

nova = Categoria(nome="Teste")
db.add(nova)
db.commit()
db.close()

print("Categoria criada!")