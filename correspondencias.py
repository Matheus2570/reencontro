from datetime import date
import re
import unicodedata

import streamlit as st
from rapidfuzz import fuzz
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1.base_query import FieldFilter


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(
        letra for letra in texto
        if not unicodedata.combining(letra)
    )
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return " ".join(texto.split())


def pontuar_objetos(origem, candidato):
    def comparar(campo, funcao):
        a = normalizar(origem.get(campo, ""))
        b = normalizar(candidato.get(campo, ""))
        return funcao(a, b) if a and b else 0.0

    notas = {
        "Descrição": comparar("descricao", fuzz.WRatio),
        "Nome": comparar("nome", fuzz.token_sort_ratio),
        "Local": comparar("local", fuzz.token_set_ratio),
        "Cor": comparar("cor", fuzz.ratio),
    }

    try:
        data_a = date.fromisoformat(origem["data_ocorrido"])
        data_b = date.fromisoformat(candidato["data_ocorrido"])
        diferenca = abs((data_a - data_b).days)
        notas["Data"] = max(0, 100 - diferenca * 10)
    except (KeyError, TypeError, ValueError):
        notas["Data"] = 0

    total = (
        notas["Descrição"] * 0.35
        + notas["Nome"] * 0.25
        + notas["Local"] * 0.20
        + notas["Cor"] * 0.10
        + notas["Data"] * 0.10
    )

    return total, notas


def mostrar_correspondencias(banco, usuario):
    st.divider()
    st.subheader("Buscar correspondências")

    try:
        documentos = list(
            banco.collection("itens")
            .where(
                filter=FieldFilter("autor_uid", "==", usuario["uid"])
            )
            .limit(50)
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
        st.info("Cadastre um objeto para buscar correspondências.")
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
            .limit(100)
            .stream(timeout=15)
        )
    except GoogleAPICallError:
        st.error("Não foi possível buscar correspondências.")
        return

    resultados = []

    for documento in candidatos:
        candidato = documento.to_dict()

        if (
            candidato.get("status") != "aberto"
            or candidato.get("categoria") != origem["categoria"]
        ):
            continue

        pontuacao, notas = pontuar_objetos(origem, candidato)

        if pontuacao >= 60:
            resultados.append((pontuacao, notas, candidato))

    resultados.sort(key=lambda resultado: resultado[0], reverse=True)

    st.caption(
        "Busca em até 100 registros do tipo oposto, "
        "comparando objetos da mesma categoria. "
        "Exibe até cinco resultados com pelo menos 60 pontos."
    )

    if not resultados:
        st.info("Nenhuma correspondência atingiu a pontuação mínima.")
        return

    st.info(
        "A pontuação indica semelhança entre os cadastros. "
        "A identidade do objeto precisa ser confirmada por uma pessoa."
    )

    for pontuacao, notas, candidato in resultados[:5]:
        with st.expander(
            f"{pontuacao:.1f}/100 pontos — {candidato['nome']}"
        ):
            st.write("Situação:", candidato["tipo"])
            st.write("Cor:", candidato["cor"])
            st.write("Local:", candidato["local"])
            st.write("Data:", candidato["data_ocorrido"])
            st.write("Descrição:", candidato["descricao"])

            st.table([
                {"Critério": criterio, "Pontos": round(valor, 1)}
                for criterio, valor in notas.items()
            ])