from pathlib import Path
import hashlib
import secrets
import uuid

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import AlreadyExists

pasta = Path(__file__).resolve().parent
chave = pasta / ".segredos" / "firebase-admin.json"

firebase_admin.initialize_app(
    credentials.Certificate(str(chave))
)
banco = firestore.client()

integrantes = [
    ("2609724", "Matheus de Carvalho"),
    ("2609622", "Lucas Casagrande da Silva"),
    ("2603109", "Guilherme Azevedo"),
    ("2608687", "Gustavo Silva Gomes"),
    ("2600292", "Matheus Maiolo"),
]

lote = banco.batch()
tokens = []

for ra, nome in integrantes:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    referencia = banco.collection("usuarios").document(ra)

    lote.create(referencia, {
        "uid": str(uuid.uuid4()),
        "ra": ra,
        "nome": nome,
        "ativo": True,
        "permissao": "admin" if ra == "2609724" else "usuario",
        "token_hash": token_hash,
        "token_versao": 1,
        "criado_em": firestore.SERVER_TIMESTAMP,
    })

    tokens.append((nome, ra, token))

try:
    lote.commit(timeout=20)
except AlreadyExists:
    print("Já existe um desses RAs. Nenhum cadastro foi alterado.")
    raise SystemExit(1)

print("\nCinco usuários cadastrados!")
print("Guarde os tokens abaixo em um local privado.\n")

for nome, ra, token in tokens:
    print(f"{nome}\nRA: {ra}\nToken: {token}\n")