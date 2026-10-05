import time

import streamlit as st
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import GoogleAPICallError
from correspondencias import pontuar_objetos
from objetos import link_foto_valido


def confirmar_devolucao(banco, perdido_id, encontrado_id, acesso):
    if perdido_id == encontrado_id:
        raise ValueError("Selecione dois cadastros diferentes.")

    usuario_ref = banco.collection("usuarios").document(acesso["ra"])
    perdido_ref = banco.collection("itens").document(perdido_id)
    encontrado_ref = banco.collection("itens").document(encontrado_id)
    devolucao_ref = banco.collection("devolucoes").document()

    @firestore.transactional
    def confirmar(transacao):
        usuario = usuario_ref.get(
            transaction=transacao, timeout=15
        ).to_dict() or {}

        perdido = perdido_ref.get(
            transaction=transacao, timeout=15
        ).to_dict() or {}

        encontrado = encontrado_ref.get(
            transaction=transacao, timeout=15
        ).to_dict() or {}

        autorizado = (
            usuario.get("ativo") is True
            and usuario.get("permissao") == "admin"
            and usuario.get("uid") == acesso["uid"]
            and usuario.get("token_versao") == acesso["versao"]
            and usuario.get("token_hash") == acesso["hash"]
            and time.time() < acesso["expira_em"]
        )

        if not autorizado:
            raise PermissionError(
                "A confirmação exige um acesso de administrador válido."
            )

        if (
            perdido.get("tipo") != "Perdido"
            or encontrado.get("tipo") != "Encontrado"
        ):
            raise ValueError("Confira os dois cadastros selecionados.")

        if (
            perdido.get("status") != "aberto"
            or encontrado.get("status") != "aberto"
            or perdido.get("devolucao_id")
            or encontrado.get("devolucao_id")
        ):
            raise ValueError(
                "Um dos cadastros já foi encerrado ou vinculado."
            )

        if perdido.get("categoria") != encontrado.get("categoria"):
            raise ValueError("Os objetos estão em categorias diferentes.")

        for referencia, outro_id in [
            (perdido_ref, encontrado_id),
            (encontrado_ref, perdido_id),
        ]:
            transacao.update(referencia, {
                "status": "resolvido",
                "devolucao_id": devolucao_ref.id,
                "correspondencia_id": outro_id,
                "resolvido_em": firestore.SERVER_TIMESTAMP,
                "resolvido_por_uid": usuario["uid"],
                "status_alterado_em": firestore.SERVER_TIMESTAMP,
                "status_alterado_por_uid": usuario["uid"],
            })

        transacao.create(devolucao_ref, {
            "perdido_id": perdido_id,
            "encontrado_id": encontrado_id,
            "recebedor_uid": perdido["autor_uid"],
            "encontrado_por_uid": encontrado["autor_uid"],
            "confirmado_por_uid": usuario["uid"],
            "confirmado_em": firestore.SERVER_TIMESTAMP,
        })

    confirmar(banco.transaction())


def mostrar_detalhes(item, codigo):
    st.write("Nome:", item.get("nome", ""))
    st.write("Categoria:", item.get("categoria", ""))
    st.write("Cor:", item.get("cor", ""))
    st.write("Local:", item.get("local", ""))
    st.write("Data:", item.get("data_ocorrido", ""))
    st.write("Descrição:", item.get("descricao", ""))

    st.caption("Código do cadastro:")
    st.code(codigo, language=None)

    foto = item.get("foto_url", "")
    if foto and link_foto_valido(foto):
        st.link_button("Ver foto", foto)


def mostrar_devolucoes(banco, usuario):
    if usuario.get("permissao") != "admin":
        return

    st.divider()
    st.subheader("Admin — confirmar devolução")

    aviso = st.session_state.pop("aviso_devolucao", None)
    if aviso:
        st.success(aviso)

    with st.form("localizar_perdido"):
        codigo = st.text_input(
            "Código do cadastro perdido",
            max_chars=128,
            help="O aluno encontra esse código em Meus objetos.",
        )
        buscar = st.form_submit_button("Buscar objetos encontrados")

    if buscar:
        st.session_state.pop("ranking_admin", None)
        codigo = codigo.strip()

        if not codigo or "/" in codigo:
            st.warning("Informe um código de cadastro válido.")
            return

        try:
            documento = (
                banco.collection("itens")
                .document(codigo)
                .get(timeout=15)
            )
            perdido = documento.to_dict() or {}

            if (
                perdido.get("tipo") != "Perdido"
                or perdido.get("status") != "aberto"
            ):
                st.warning(
                    "O código precisa identificar um objeto perdido e aberto."
                )
                return

            candidatos = (
                banco.collection("itens")
                .where(filter=FieldFilter("tipo", "==", "Encontrado"))
                .where(filter=FieldFilter("status", "==", "aberto"))
                .where(
                    filter=FieldFilter(
                        "categoria", "==", perdido["categoria"]
                    )
                )
                .stream(timeout=15)
            )

            ranking = []

            for candidato_doc in candidatos:
                candidato = candidato_doc.to_dict()
                pontuacao, notas = pontuar_objetos(perdido, candidato)

                ranking.append({
                    "id": candidato_doc.id,
                    "item": candidato,
                    "pontuacao": pontuacao,
                    "notas": notas,
                })

            ranking.sort(
                key=lambda resultado: (
                    -resultado["pontuacao"],
                    resultado["id"],
                )
            )

            st.session_state["ranking_admin"] = {
                "perdido_id": codigo,
                "perdido": perdido,
                "resultados": ranking,
            }

        except GoogleAPICallError:
            st.error("Não foi possível consultar os cadastros.")
            return

    busca = st.session_state.get("ranking_admin")
    if not busca:
        return

    perdido_id = busca["perdido_id"]
    ranking = busca["resultados"]

    st.caption(
        "Resultados da última busca. Busque novamente para atualizar."
    )

    if not ranking:
        st.info("Não há objetos encontrados abertos nessa categoria.")
        return

    st.write(
        f"{len(ranking)} candidatos, ordenados pela semelhança."
    )

    quantidade_paginas = (len(ranking) + 9) // 10

    pagina = st.selectbox(
        "Página de candidatos",
        options=list(range(1, quantidade_paginas + 1)),
        key=f"pagina_admin_{perdido_id}",
    )

    inicio = (pagina - 1) * 10
    resultados_pagina = ranking[inicio:inicio + 10]
    opcoes = {
        resultado["id"]: resultado
        for resultado in resultados_pagina
    }

    escolhido = st.selectbox(
        "Objeto encontrado para conferir",
        options=list(opcoes),
        index=None,
        placeholder="Selecione um candidato",
        format_func=lambda chave: (
            f"{opcoes[chave]['pontuacao']:.1f}/100 — "
            f"{opcoes[chave]['item']['nome']} — "
            f"{opcoes[chave]['item']['local']} — "
            f"Código: {chave}"
        ),
        key=f"candidato_admin_{perdido_id}_{pagina}",
    )

    if escolhido is None:
        return

    resultado = opcoes[escolhido]

    esquerda, direita = st.columns(2)

    with esquerda:
        st.subheader("Objeto perdido")
        mostrar_detalhes(busca["perdido"], perdido_id)

    with direita:
        st.subheader("Objeto encontrado")
        mostrar_detalhes(resultado["item"], escolhido)

    st.write(
        f"Pontuação de semelhança: "
        f"{resultado['pontuacao']:.1f}/100"
    )

    st.table([
        {"Critério": criterio, "Pontos": round(pontos, 1)}
        for criterio, pontos in resultado["notas"].items()
    ])

    st.info(
        "Confira o objeto físico e a propriedade antes de entregar. "
        "A pontuação não confirma que os objetos são o mesmo."
    )

    with st.form(
        f"entrega_admin_{perdido_id}_{escolhido}",
        clear_on_submit=True,
    ):
        conferido = st.checkbox(
            "Conferi os dois cadastros e já entreguei "
            "o objeto ao proprietário."
        )
        confirmar = st.form_submit_button("Confirmar devolução")

    if confirmar:
        if not conferido:
            st.warning("Confirme a conferência e a entrega.")
            return

        acesso = st.session_state.get("acesso")
        if not acesso:
            st.error("Entre novamente para continuar.")
            return

        try:
            confirmar_devolucao(
                banco, perdido_id, escolhido, dict(acesso)
            )
        except (PermissionError, ValueError) as erro:
            st.error(str(erro))
        except GoogleAPICallError:
            st.error(
                "Não foi possível confirmar a operação. "
                "Atualize a busca para conferir os cadastros."
            )
        else:
            st.session_state.pop("ranking_admin", None)
            st.session_state["aviso_devolucao"] = (
                "Devolução registrada! Os dois cadastros foram resolvidos."
            )
            st.rerun()