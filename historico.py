from datetime import datetime, timedelta, timezone

import streamlit as st
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1.base_query import FieldFilter

from devolucoes import mostrar_detalhes
from identificacao import identificar_pessoa


def carregar_historico(banco, usuario, todas=False):
    colecao = banco.collection("devolucoes")
    if todas:
        if usuario.get("permissao") != "admin":
            raise PermissionError("Somente o administrador pode consultar todas as devoluções.")
        documentos = list(colecao.stream(timeout=15))
    else:
        documentos = []
        for campo in ("recebedor_uid", "encontrado_por_uid"):
            documentos.extend(
                colecao.where(filter=FieldFilter(campo, "==", usuario["uid"]))
                .stream(timeout=15)
            )
    registros = {doc.id: doc.to_dict() for doc in documentos}
    minimo = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(
        registros.items(),
        key=lambda registro: (registro[1].get("confirmado_em") or minimo, registro[0]),
        reverse=True,
    )


def formatar_data_devolucao(valor):
    if not isinstance(valor, datetime):
        return "Não informado"
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    brasilia = timezone(timedelta(hours=-3))
    return valor.astimezone(brasilia).strftime("%d/%m/%Y às %H:%M") + " (Brasília)"


def mostrar_historico(banco, usuario):
    st.divider()
    st.subheader("Histórico de devoluções")
    todas = False
    if usuario.get("permissao") == "admin":
        todas = st.radio("Exibir histórico", ["Meu histórico", "Todas as devoluções"]) == "Todas as devoluções"
    try:
        registros = carregar_historico(banco, usuario, todas)
    except GoogleAPICallError:
        st.error("Não foi possível carregar o histórico de devoluções.")
        return
    if not registros:
        st.info("Nenhuma devolução registrada." if todas else "Você ainda não participou de uma devolução.")
        return
    st.caption(f"{len(registros)} devoluções. Exibindo dez por página, das mais recentes para as mais antigas.")
    pagina = st.selectbox(
        "Página do histórico", range(1, (len(registros) + 9) // 10 + 1),
        key=f"historico_pagina_{usuario['uid']}_{todas}_{len(registros)}",
    )
    cache_pessoas = {}
    for codigo, registro in registros[(pagina - 1) * 10:pagina * 10]:
        try:
            # Devoluções antigas não têm cópias dos dados dos objetos.
            perdido = registro.get("perdido")
            encontrado = registro.get("encontrado")
            if perdido is None:
                perdido = banco.collection("itens").document(registro["perdido_id"]).get(timeout=15).to_dict() or {}
            if encontrado is None:
                encontrado = banco.collection("itens").document(registro["encontrado_id"]).get(timeout=15).to_dict() or {}
        except GoogleAPICallError:
            st.error("Não foi possível carregar os detalhes desta devolução.")
            continue
        with st.expander(f"Devolvido — {perdido.get('nome', encontrado.get('nome', 'Objeto'))} — {codigo}"):
            participacoes = []
            if registro.get("recebedor_uid") == usuario["uid"]:
                participacoes.append("Você recuperou este objeto.")
            if registro.get("encontrado_por_uid") == usuario["uid"]:
                participacoes.append("Você encontrou este objeto.")
            for texto in participacoes:
                st.write(texto)
            st.write("Devolvido em:", formatar_data_devolucao(registro.get("confirmado_em")))
            for rotulo, campo, uid_padrao, ra_padrao in (
                ("Proprietário:", "recebedor", perdido.get("autor_uid"), perdido.get("autor_ra")),
                ("Encontrado por:", "encontrado_por", encontrado.get("encontrado_por_uid") or encontrado.get("autor_uid"), encontrado.get("encontrado_por_ra")),
                ("Cadastro do encontrado feito por:", "cadastrado_por", encontrado.get("cadastrado_por_uid") or encontrado.get("autor_uid"), encontrado.get("cadastrado_por_ra") or encontrado.get("autor_ra")),
                ("Devolução confirmada por:", "confirmado_por", None, None),
            ):
                st.write(rotulo, identificar_pessoa(
                    banco, registro.get(f"{campo}_uid") or uid_padrao,
                    registro.get(f"{campo}_ra") or ra_padrao,
                    registro.get(f"{campo}_nome"), cache_pessoas,
                ))
            # O registro da devolução também identifica participantes de itens antigos.
            encontrado = dict(encontrado)
            for campo in ("encontrado_por", "cadastrado_por"):
                for sufixo in ("uid", "ra", "nome"):
                    chave = f"{campo}_{sufixo}"
                    if registro.get(chave):
                        encontrado[chave] = registro[chave]
            st.caption("Cadastro perdido")
            mostrar_detalhes(perdido, registro["perdido_id"], banco, cache_pessoas)
            st.caption("Cadastro encontrado")
            mostrar_detalhes(encontrado, registro["encontrado_id"], banco, cache_pessoas)
