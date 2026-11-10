from datetime import date
from urllib.parse import urlsplit

import streamlit as st
from firebase_admin import firestore
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1.base_query import FieldFilter
from acesso import validar_acesso
from identificacao import identificar_pessoa
from pesquisa import corresponde_pesquisa
from caracteristicas import CAMPOS_COMUNS, CAMPOS_CATEGORIA, ROTULOS, OPCOES, canonico


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


def registrar_objeto(banco, dados, acesso, encontrado_por_ra="", recebido=False):
    tipo = dados.get("tipo")
    if tipo not in {"Perdido", "Encontrado"}:
        raise ValueError("Situação inválida.")
    if tipo == "Encontrado":
        if not recebido:
            raise ValueError("Confirme o recebimento do objeto no almoxarifado.")
        if not (len(encontrado_por_ra) == 7 and encontrado_por_ra.isascii()
                and encontrado_por_ra.isdigit()):
            raise ValueError("Informe o RA de sete dígitos de quem encontrou.")
    if not acesso.get("ra"):
        raise PermissionError("Entre novamente para continuar.")
    referencia = banco.collection("itens").document()
    usuario_ref = banco.collection("usuarios").document(acesso["ra"])

    @firestore.transactional
    def salvar(transacao):
        usuario = usuario_ref.get(transaction=transacao, timeout=15).to_dict() or {}
        validar_acesso(usuario, acesso, exigir_admin=tipo == "Encontrado")
        encontrado_por = {}
        if tipo == "Encontrado":
            encontrado_por = (
                banco.collection("usuarios").document(encontrado_por_ra)
                .get(transaction=transacao, timeout=15).to_dict() or {}
            )
            if not encontrado_por.get("uid"):
                raise ValueError("O RA de quem encontrou precisa estar cadastrado no sistema.")
        registro = dict(dados)
        registro.update({
            "status": "aberto",
            "autor_uid": usuario["uid"],
            "autor_nome": usuario["nome"],
            "autor_ra": usuario["ra"],
            "cadastrado_por_uid": usuario["uid"],
            "cadastrado_por_nome": usuario["nome"],
            "cadastrado_por_ra": usuario["ra"],
            "criado_em": firestore.SERVER_TIMESTAMP,
        })
        if tipo == "Encontrado":
            registro.update({
                "encontrado_por_uid": encontrado_por["uid"],
                "encontrado_por_nome": encontrado_por["nome"],
                "encontrado_por_ra": encontrado_por_ra,
                "recebido_no_almoxarifado_em": firestore.SERVER_TIMESTAMP,
            })
        transacao.create(referencia, registro)
    salvar(banco.transaction())
    return referencia.id


def mostrar_objetos(banco, usuario):
    st.divider()
    st.subheader("Cadastrar objeto")

    admin = usuario.get("permissao") == "admin"
    tipo = st.selectbox("Situação", ["Perdido", "Encontrado"]) if admin else "Perdido"
    if not admin:
        st.caption("Cadastre seu objeto perdido. Se encontrou algo, entregue ao almoxarifado para o administrador cadastrar.")

    # Fora do form para atualizar os campos opcionais ao trocar a categoria.
    categoria = st.selectbox("Categoria", CATEGORIAS)
    with st.form(f"cadastro_objeto_{tipo}", clear_on_submit=True):
        encontrado_por_ra = ""
        recebido = False
        if tipo == "Encontrado":
            encontrado_por_ra = st.text_input(
                "RA de quem encontrou o objeto", max_chars=7,
                help="A pessoa que encontrou e entregou o objeto precisa estar cadastrada no sistema.",
            )
            recebido = st.checkbox("Recebi o objeto físico no almoxarifado.")

        nome = st.text_input(
            "Nome do objeto",
            max_chars=100,
        )

        st.caption("Características opcionais: preencha apenas o que souber com certeza.")
        caracteristicas = {}
        for campo in CAMPOS_COMUNS + CAMPOS_CATEGORIA[categoria]:
            chave = f"caracteristica_{tipo}_{categoria}_{campo}"
            if campo in OPCOES:
                valor = st.selectbox(ROTULOS[campo], OPCOES[campo], key=chave,
                                     format_func=lambda v: v or "Não informado")
            else:
                valor = st.text_input(ROTULOS[campo] + " — opcional", max_chars=100, key=chave)
            if valor.strip():
                caracteristicas[campo] = valor.strip()

        cor = st.text_input(
            "Cor",
            max_chars=50,
        )

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

        salvar = st.form_submit_button("Salvar objeto")

    if salvar:
        nome = nome.strip()
        cor = cor.strip()
        local = local.strip()
        descricao = descricao.strip()
        foto_url = foto_url.strip()

        erros = []
        if "capacidade" in caracteristicas and not canonico("capacidade", caracteristicas["capacidade"]):
            erros.append("Capacidade: informe um valor positivo em ml ou L, como 750 ml ou 1,2 L.")

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
            try:
                codigo = registrar_objeto(
                    banco,
                    {
                        "nome": nome,
                        "tipo": tipo,
                        "categoria": categoria,
                        "cor": cor,
                        "local": local,
                        "data_ocorrido": data_ocorrido.isoformat(),
                        "descricao": descricao,
                        "foto_url": foto_url,
                        "caracteristicas": caracteristicas,
                    },
                    dict(st.session_state.get("acesso", {})),
                    encontrado_por_ra.strip(),
                    recebido,
                )
            except (PermissionError, ValueError) as erro:
                st.error(str(erro))
            except GoogleAPICallError:
                st.error(
                    "Não foi possível confirmar o salvamento. "
                    "Confira seus cadastros antes de tentar novamente."
                )
            else:
                st.success("Objeto cadastrado!")
                st.code(codigo, language=None)

    st.subheader("Meus objetos")
    st.caption("Cadastros em aberto. Os devolvidos aparecem no histórico.")

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
            .where(filter=FieldFilter("status", "==", "aberto"))
            .stream(timeout=15)
        )
    except GoogleAPICallError:
        st.error("Não foi possível carregar seus objetos.")
        return

    if not documentos:
        st.info("Você não tem cadastros em aberto.")
    cache_pessoas = {}
    mostrar_lista_objetos(documentos, banco, cache_pessoas, "meus_objetos", "Pesquisar em meus objetos")

    if admin:
        st.subheader("Almoxarifado — objetos encontrados")
        try:
            encontrados = list(
                banco.collection("itens")
                .where(filter=FieldFilter("tipo", "==", "Encontrado"))
                .where(filter=FieldFilter("status", "==", "aberto"))
                .stream(timeout=15)
            )
        except GoogleAPICallError:
            st.error("Não foi possível carregar o almoxarifado.")
            return
        if not encontrados:
            st.info("Não há objetos encontrados em aberto.")
        mostrar_lista_objetos(encontrados, banco, cache_pessoas, "almoxarifado", "Pesquisar no almoxarifado")


def mostrar_lista_objetos(documentos, banco, cache_pessoas, chave, rotulo):
    termo = st.text_input(rotulo, key=f"pesquisa_{chave}",
                          placeholder="Nome, descrição, categoria, cor, local, RA ou código")
    filtrados = [doc for doc in documentos if corresponde_pesquisa(doc.id, doc.to_dict(), termo)]
    st.caption(f"{len(filtrados)} de {len(documentos)} objetos.")
    if not filtrados:
        if documentos:
            st.info("Nenhum objeto corresponde à pesquisa.")
        return
    pagina = st.selectbox(
        "Página de objetos" if chave == "meus_objetos" else "Página do almoxarifado",
        range(1, (len(filtrados) + 9) // 10 + 1),
        key=f"pagina_{chave}_{termo}_{len(filtrados)}",
    )
    for documento in filtrados[(pagina - 1) * 10:pagina * 10]:
        mostrar_item(documento, banco, cache_pessoas)


def mostrar_item(documento, banco=None, cache_pessoas=None):
    item = documento.to_dict()
    with st.expander(f"{item['tipo']} — {item['nome']}"):
        st.write("Categoria:", item["categoria"])
        st.write("Cor:", item["cor"])
        st.write("Local:", item["local"])
        st.write("Data:", item["data_ocorrido"])
        st.write("Descrição:", item["descricao"])
        for campo, valor in (item.get("caracteristicas") or {}).items():
            if campo in ROTULOS:
                st.write(f"{ROTULOS[campo]}:", valor)
        st.write("Status:", item["status"])
        if item.get("tipo") == "Encontrado":
            st.write("Encontrado por:", identificar_pessoa(
                banco, item.get("encontrado_por_uid") or item.get("autor_uid"),
                item.get("encontrado_por_ra"), item.get("encontrado_por_nome"), cache_pessoas,
            ))
            st.write("Cadastrado por:", identificar_pessoa(
                banco, item.get("cadastrado_por_uid") or item.get("autor_uid"),
                item.get("cadastrado_por_ra") or item.get("autor_ra"),
                item.get("cadastrado_por_nome") or item.get("autor_nome"), cache_pessoas,
            ))

        st.caption("Código do cadastro:")
        st.code(documento.id, language=None)

        link = item.get("foto_url", "")

        if link and link_foto_valido(link):
            st.link_button("Ver foto", link)
