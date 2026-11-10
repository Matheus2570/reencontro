from datetime import date

import streamlit as st
from rapidfuzz import fuzz
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1.base_query import FieldFilter


from pesquisa import normalizar, corresponde_pesquisa
from caracteristicas import comparar_caracteristicas


def pontuar_objetos(origem, candidato):
    def comparar(campo, funcao):
        a = normalizar(origem.get(campo, ""))
        b = normalizar(candidato.get(campo, ""))
        return funcao(a, b) if a and b else 0.0

    notas = {
        "Descrição": comparar("descricao", fuzz.WRatio),
        "Nome": comparar("nome", fuzz.token_sort_ratio),
        "Local": comparar("local", fuzz.token_set_ratio),
    }

    try:
        data_a = date.fromisoformat(origem["data_ocorrido"])
        data_b = date.fromisoformat(candidato["data_ocorrido"])
        diferenca = abs((data_a - data_b).days)
        notas["Data"] = max(0, 100 - diferenca * 10)
    except (KeyError, TypeError, ValueError):
        notas["Data"] = 0

    total = (
        notas["Descrição"] * 0.40
        + notas["Nome"] * 0.30
        + notas["Local"] * 0.20
        + notas["Data"] * 0.10
    )

    return total, notas


def classificar_candidatos(origem, candidatos):
    """Única ordenação para aluno e administrador; candidatos são (id, item)."""
    resultados = []
    for codigo, candidato in candidatos:
        if candidato.get("status") != "aberto" or candidato.get("categoria") != origem.get("categoria"):
            continue
        pontuacao, notas = pontuar_objetos(origem, candidato)
        avaliacao = comparar_caracteristicas(origem, candidato)
        resultados.append(dict(id=codigo, item=candidato, pontuacao=pontuacao,
                               notas=notas, avaliacao=avaliacao))
    # Nenhuma nota textual compensa uma divergência explícita.
    resultados.sort(key=lambda r: (bool(r["avaliacao"]["divergencias"]),
                                  -r["avaliacao"]["compativeis"],
                                  len(r["avaliacao"]["divergencias"]),
                                  -r["pontuacao"], r["id"]))
    return resultados


def mostrar_avaliacao(resultado):
    avaliacao = resultado["avaliacao"]
    st.write("Características:", avaliacao["situacao"])
    for detalhe in avaliacao["divergencias"]:
        st.warning(f"{detalhe['Característica']} — Divergência: {detalhe['Origem']} × {detalhe['Candidato']}.")
    if avaliacao["detalhes"]:
        st.table(avaliacao["detalhes"])
    st.caption("Informação ausente não conta como acordo nem como divergência.")
    st.write(f"Similaridade textual e de contexto: {resultado['pontuacao']:.1f}/100")


def mostrar_correspondencias(banco, usuario):
    st.divider()
    st.subheader("Buscar correspondências")

    try:
        documentos = list(
            banco.collection("itens")
            .where(
                filter=FieldFilter("autor_uid", "==", usuario["uid"])
            )
            .where(filter=FieldFilter("status", "==", "aberto"))
            .where(filter=FieldFilter("tipo", "==", "Perdido"))
            .stream(timeout=15)
        )
    except GoogleAPICallError:
        st.error("Não foi possível carregar seus objetos.")
        return

    meus_itens = {
        documento.id: documento.to_dict()
        for documento in documentos
        if documento.to_dict().get("status") == "aberto"
    }

    if not meus_itens:
        st.info("Cadastre um objeto perdido para buscar correspondências.")
        return

    termo = st.text_input(
        "Pesquisar objeto para comparar", key="pesquisa_comparar",
        placeholder="Nome, descrição, cor, local ou código",
    )
    meus_itens = {codigo: item for codigo, item in meus_itens.items()
                  if corresponde_pesquisa(codigo, item, termo)}
    if not meus_itens:
        st.info("Nenhum objeto corresponde à pesquisa.")
        return

    with st.form("busca_correspondencias"):
        escolhido = st.selectbox(
            "Qual dos seus objetos você quer comparar?",
            options=list(meus_itens),
            format_func=lambda chave: (
                f"{meus_itens[chave]['tipo']} — "
                f"{meus_itens[chave]['nome']} "
                f"({meus_itens[chave]['data_ocorrido']})"
            ),
        )
        buscar = st.form_submit_button("Buscar correspondências")

    if not buscar:
        return

    origem = meus_itens[escolhido]
    tipo_oposto = (
        "Encontrado" if origem["tipo"] == "Perdido" else "Perdido"
    )

    try:
        candidatos = list(
            banco.collection("itens")
            .where(filter=FieldFilter("tipo", "==", tipo_oposto))
            .where(filter=FieldFilter("status", "==", "aberto"))
            .where(filter=FieldFilter("categoria", "==", origem["categoria"]))
            .stream(timeout=15)
        )
    except GoogleAPICallError:
        st.error("Não foi possível buscar correspondências.")
        return

    resultados = classificar_candidatos(
        origem, ((doc.id, doc.to_dict()) for doc in candidatos)
    )
    st.caption(
        "Até cinco resultados da mesma categoria, priorizando características "
        "compatíveis. Candidatos com divergências ficam abaixo dos demais."
    )

    if not resultados:
        st.info("Não há objetos encontrados abertos nessa categoria.")
        return

    st.info(
        "A similaridade textual e de contexto é separada das características. "
        "A identidade do objeto precisa ser confirmada por uma pessoa."
    )

    for resultado in resultados[:5]:
        candidato = resultado["item"]
        pontuacao, notas = resultado["pontuacao"], resultado["notas"]
        with st.expander(
            f"{resultado['avaliacao']['situacao']} — {candidato['nome']}"
        ):
            mostrar_avaliacao(resultado)
            st.write("Situação:", candidato["tipo"])
            st.write("Cor:", candidato["cor"])
            st.write("Local:", candidato["local"])
            st.write("Data:", candidato["data_ocorrido"])
            st.write("Descrição:", candidato["descricao"])

            st.table([
                {"Critério": criterio, "Pontos": round(valor, 1)}
                for criterio, valor in notas.items()
            ])
