from pathlib import Path
import hashlib
import secrets

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import GoogleAPICallError

chave = (
    Path(__file__).resolve().parent
    / ".segredos"
    / "firebase-admin.json"
)

firebase_admin.initialize_app(
    credentials.Certificate(str(chave))
)
banco = firestore.client()

ra = input("RA do integrante que receberá um novo token: ").strip()

if not (len(ra) == 7 and ra.isascii() and ra.isdigit()):
    print("RA inválido.")
    raise SystemExit(1)

referencia = banco.collection("usuarios").document(ra)

try:
    documento = referencia.get(timeout=15)

    if not documento.exists:
        print("Esse RA não está cadastrado.")
        raise SystemExit(1)

    usuario = documento.to_dict()
    novo_token = secrets.token_urlsafe(32)

    referencia.update({
        "token_hash": hashlib.sha256(
            novo_token.encode("utf-8")
        ).hexdigest(),
        "token_versao": firestore.Increment(1),
        "token_alterado_em": firestore.SERVER_TIMESTAMP,
    }, timeout=15)

except GoogleAPICallError:
    print(
        "Não foi possível confirmar a troca. "
        "Execute novamente para gerar outro token."
    )
    raise SystemExit(1)

print(f"\nToken alterado para {usuario['nome']} — RA {ra}")
print(f"Novo token: {novo_token}")
print("Guarde esse token em um local privado.")