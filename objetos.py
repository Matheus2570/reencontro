from datetime import date
from urllib.parse import urlsplit

import streamlit as st
from firebase_admin import firestore
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1.base_query import FieldFilter


CATEGORIAS = [
    "Eletrônicos",
    "Material escolar",
    "Documentos",
    "Roupas e acessórios",
    "Garrafas e recipientes",
    "Chaves",
    "Outros",
]


def link_foto_valido(link):
    if not link:
        return True

    try:
        endereco = urlsplit(link)

        return (
            endereco.scheme == "https"
            and endereco.netloc in {
                "drive.google.com",
                "docs.google.com",
            }
            and bool(endereco.path)
        )
    except ValueError:
        return False


def mostrar_objetos(banco, usuario):
    st.divider()
    st.subheader("Cadastrar objeto")

    with st.form("cadastro_objeto", clear_on_submit=True):
        st.markdown(
            '<div class="section-kicker">01 / Identificação</div>',
            unsafe_allow_html=True,
        )

        coluna_tipo, coluna_categoria = st.columns([1, 1.5])
        with coluna_tipo:
            tipo = st.selectbox(
                "Situação",
                ["Perdido", "Encontrado"],
            )

        with coluna_categoria:
            categoria = st.selectbox(
                "Categoria",
                CATEGORIAS,
            )

        nome = st.text_input(
            "Nome do objeto",
            max_chars=100,
        )

        st.markdown(
            '<div class="section-kicker">02 / Onde e quando</div>',
            unsafe_allow_html=True,
        )

        coluna_cor, coluna_local = st.columns([1, 2])
        with coluna_cor:
            cor = st.text_input(
                "Cor",
                max_chars=50,
            )

        with coluna_local:
            local = st.text_input(
                "Local da perda ou encontro",
                max_chars=150,
            )

        data_ocorrido = st.date_input(
            "Data da perda ou encontro",
            value=date.today(),
            min_value=date(2000, 1, 1),
            max_value=date.today(),
        )

        st.markdown(
            '<div class="section-kicker">03 / Detalhes para reconhecer</div>',
            unsafe_allow_html=True,
        )

        descricao = st.text_area(
            "Descrição e características",
            max_chars=1000,
            placeholder="Marca, adesivos, detalhes e sinais de uso...",
        )

        foto_url = st.text_input(
            "Link da foto no Google Drive — opcional",
            max_chars=1000,
            help="Use um link de visualização que as pessoas possam abrir.",
        )

        salvar = st.form_submit_button(
            "Salvar objeto",
            type="primary",
        )

    if salvar:
        nome = nome.strip()
        cor = cor.strip()
        local = local.strip()
        descricao = descricao.strip()
        foto_url = foto_url.strip()

        erros = []

        for rotulo, valor, minimo, maximo in [
            ("Nome", nome, 3, 100),
            ("Cor", cor, 2, 50),
            ("Local", local, 3, 150),
            ("Descrição", descricao, 10, 1000),
        ]:
            if not minimo <= len(valor) <= maximo:
                erros.append(
                    f"{rotulo}: use entre {minimo} e {maximo} caracteres."
                )

        if tipo not in ["Perdido", "Encontrado"]:
            erros.append("Situação inválida.")

        if categoria not in CATEGORIAS:
            erros.append("Categoria inválida.")

        if not date(2000, 1, 1) <= data_ocorrido <= date.today():
            erros.append("Confira a data informada.")

        if len(foto_url) > 1000 or not link_foto_valido(foto_url):
            erros.append(
                "Use um link HTTPS do Google Drive ou deixe vazio."
            )

        if erros:
            for erro in erros:
                st.warning(erro)
        else:
            referencia = banco.collection("itens").document()

            try:
                referencia.create(
                    {
                        "nome": nome,
                        "tipo": tipo,
                        "categoria": categoria,
                        "cor": cor,
                        "local": local,
                        "data_ocorrido": data_ocorrido.isoformat(),
                        "descricao": descricao,
                        "foto_url": foto_url,
                        "status": "aberto",
                        "autor_uid": usuario["uid"],
                        "criado_em": firestore.SERVER_TIMESTAMP,
                    },
                    timeout=15,
                )
            except GoogleAPICallError:
                st.error(
                    "Não foi possível confirmar o salvamento. "
                    "Confira seus cadastros antes de tentar novamente."
                )
            else:
                st.success("Objeto salvo no Firebase!")

    st.subheader("Meus objetos")
    st.caption("Exibindo até 50 dos seus cadastros.")

    try:
        documentos = list(
            banco.collection("itens")
            .where(
                filter=FieldFilter(
                    "autor_uid",
                    "==",
                    usuario["uid"],
                )
            )
            .limit(50)
            .stream(timeout=15)
        )
    except GoogleAPICallError:
        st.error("Não foi possível carregar seus objetos.")
        return

    if not documentos:
        st.info(
            "Seu catálogo ainda está vazio. Cadastre um objeto acima "
            "para começar a busca por um reencontro."
        )
        return

    for documento in documentos:
        item = documento.to_dict()

        with st.expander(f"{item['tipo']}  /  {item['nome']}"):
            st.caption(item["categoria"])
            st.write(item["descricao"])

            coluna_local, coluna_data, coluna_cor = st.columns(3)
            with coluna_local:
                st.caption("LOCAL")
                st.write(item["local"])
            with coluna_data:
                st.caption("DATA")
                st.write(item["data_ocorrido"])
            with coluna_cor:
                st.caption("COR")
                st.write(item["cor"])

            if item["status"] == "resolvido":
                st.success("Devolução concluída")
            elif item["status"] == "aberto":
                st.info("Aguardando devolução")
            else:
                st.caption(f"Status: {item['status']}")

            st.caption("Código do cadastro:")
            st.code(documento.id, language=None)

            link = item.get("foto_url", "")

            if link and link_foto_valido(link):
                st.link_button("Ver foto", link)