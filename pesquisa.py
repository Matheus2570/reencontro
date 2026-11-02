import re
import unicodedata


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(letra for letra in texto if not unicodedata.combining(letra))
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", texto).split())


def corresponde_pesquisa(codigo, dados, termo):
    """Busca por todas as palavras nos campos públicos, sem depender da ordem."""
    campos = {
        "nome", "tipo", "categoria", "cor", "local", "descricao", "data_ocorrido",
        "perdido_id", "encontrado_id", "confirmado_em", "participantes",
    }
    valores = [str(codigo)]

    def coletar(registro):
        for campo, valor in registro.items():
            if campo in {"perdido", "encontrado"} and isinstance(valor, dict):
                coletar(valor)
            elif campo in campos or campo.endswith(("_ra", "_nome")):
                valores.append(str(valor or ""))
                if campo == "data_ocorrido" and valor:
                    from datetime import date
                    try:
                        valores.append(date.fromisoformat(valor).strftime("%d/%m/%Y"))
                    except (TypeError, ValueError):
                        pass

    coletar(dados)
    texto = normalizar(" ".join(valores))
    return all(palavra in texto for palavra in normalizar(termo).split())
