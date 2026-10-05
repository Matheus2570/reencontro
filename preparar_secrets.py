from pathlib import Path
import json
import tomllib

pasta = Path(__file__).resolve().parent
chave = pasta / ".segredos" / "firebase-admin.json"

dados = json.loads(chave.read_text(encoding="utf-8"))

linhas = ["[firebase]"]

for campo, valor in dados.items():
    if not isinstance(valor, str):
        raise ValueError("Formato de credencial inesperado.")

    linhas.append(
        f"{json.dumps(campo)} = {json.dumps(valor)}"
    )

conteudo = "\n".join(linhas) + "\n"

# Confere o formato antes de salvar.
tomllib.loads(conteudo)

destino = pasta / ".streamlit" / "secrets.toml"
destino.parent.mkdir(exist_ok=True)
destino.write_text(conteudo, encoding="utf-8")

print("Secrets preparados! Não envie esse arquivo ao GitHub ou ao chat.")