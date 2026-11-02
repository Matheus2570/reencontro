from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1.base_query import FieldFilter


def identificar_pessoa(banco, uid=None, ra=None, nome=None, cache=None):
    """Exibe RA e resolve vínculos antigos por UID sem alterar o banco."""
    if not ra and banco is not None and uid:
        if cache is None:
            cache = {}
        if uid not in cache:
            try:
                documentos = list(
                    banco.collection("usuarios")
                    .where(filter=FieldFilter("uid", "==", uid))
                    .limit(1).stream(timeout=15)
                )
            except GoogleAPICallError:
                documentos = []
            cache[uid] = (
                (documentos[0].to_dict() or {}).get("ra") or documentos[0].id
            ) if documentos else None
        ra = cache[uid]
    if ra:
        return f"RA {ra}"
    return f"{nome} (RA não localizado)" if nome else "RA não localizado"
