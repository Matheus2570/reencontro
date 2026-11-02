import time


def validar_acesso(usuario, acesso, exigir_admin=False):
    valido = (
        usuario.get("ativo") is True
        and usuario.get("uid") == acesso.get("uid")
        and usuario.get("token_versao") == acesso.get("versao")
        and usuario.get("token_hash") == acesso.get("hash")
        and time.time() < acesso.get("expira_em", 0)
    )
    if not valido or (exigir_admin and usuario.get("permissao") != "admin"):
        raise PermissionError("Entre novamente com um acesso autorizado para continuar.")
