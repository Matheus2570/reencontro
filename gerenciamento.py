"""Gestão administrativa com arquivamento reversível e autorização no servidor."""
from datetime import date

import streamlit as st
from firebase_admin import firestore
from google.api_core.exceptions import GoogleAPICallError

from acesso import validar_acesso
from devolucoes import mostrar_detalhes
from identificacao import identificar_pessoa
from formulario_objeto import CATEGORIAS, campos_caracteristicas, validar_dados_objeto
from pesquisa import corresponde_pesquisa


def exigir_admin(banco, acesso, transacao=None):
    if not acesso or not acesso.get("ra"):
        raise PermissionError("Entre novamente com um acesso de administrador.")
    usuario = banco.collection("usuarios").document(acesso["ra"]).get(
        transaction=transacao, timeout=15
    ).to_dict() or {}
    validar_acesso(usuario, acesso, exigir_admin=True)
    return usuario


def carregar_objetos_admin(banco, acesso):
    exigir_admin(banco, acesso)
    return sorted(((doc.id, doc.to_dict()) for doc in banco.collection("itens").stream(timeout=15)),
                  key=lambda par: par[0])


def item_devolvido(item):
    return item.get("status") == "resolvido" or bool(item.get("devolucao_id") or item.get("correspondencia_id"))


def alterar_objeto(banco, codigo, acesso, acao, dados=None, esperado=None):
    """Lê novamente permissão e estado dentro da transação antes de escrever.

    Atualiza somente campos permitidos: identidade, autoria e vínculos não
    podem ser substituídos pelo conteúdo enviado pelo formulário.
    """
    if not codigo or "/" in codigo:
        raise ValueError("Código de objeto inválido.")
    referencia = banco.collection("itens").document(codigo)

    @firestore.transactional
    def alterar(transacao):
        admin = exigir_admin(banco, acesso, transacao)
        atual = referencia.get(transaction=transacao, timeout=15).to_dict()
        if not atual:
            raise ValueError("Objeto não localizado.")
        if item_devolvido(atual):
            raise ValueError("Itens devolvidos estão disponíveis apenas para consulta.")
        if esperado is not None and atual != esperado:
            raise ValueError("O cadastro mudou. Atualize a lista e confira o objeto novamente.")
        if acao == "editar":
            if atual.get("status") != "aberto":
                raise ValueError("Somente itens em aberto podem ser editados.")
            alteracoes = validar_dados_objeto(dict(dados or {}, tipo=atual["tipo"]))
            alteracoes.pop("tipo")
        elif acao == "arquivar":
            if atual.get("status") != "aberto":
                raise ValueError("Somente itens em aberto podem ser arquivados.")
            alteracoes = {"status": "arquivado", "arquivado_em": firestore.SERVER_TIMESTAMP,
                          "arquivado_por_uid": admin["uid"], "arquivado_por_ra": admin["ra"]}
        elif acao == "restaurar":
            if atual.get("status") != "arquivado":
                raise ValueError("Somente itens arquivados podem ser restaurados.")
            alteracoes = {"status": "aberto", "restaurado_em": firestore.SERVER_TIMESTAMP,
                          "restaurado_por_uid": admin["uid"], "restaurado_por_ra": admin["ra"]}
        else:
            raise ValueError("Ação inválida.")
        alteracoes.update(atualizado_em=firestore.SERVER_TIMESTAMP,
                          atualizado_por_uid=admin["uid"], atualizado_por_ra=admin["ra"])
        transacao.update(referencia, alteracoes)

    alterar(banco.transaction())


def filtrar_objetos(registros, termo="", tipo="Todos", situacao="Todas", banco=None):
    cache = {}
    resultado = []
    for codigo, item in registros:
        if tipo != "Todos" and item.get("tipo") != tipo:
            continue
        estado = "Devolvido" if item_devolvido(item) else {"aberto": "Em aberto", "arquivado": "Arquivado"}.get(item.get("status"), "Desconhecido")
        if situacao != "Todas" and estado != situacao:
            continue
        pesquisavel = dict(item)
        if termo.strip() and banco is not None and not corresponde_pesquisa(codigo, pesquisavel, termo):
            pesquisavel["participantes"] = " ".join(
                identificar_pessoa(banco, item.get(f"{campo}_uid"), item.get(f"{campo}_ra"),
                                   item.get(f"{campo}_nome"), cache)
                for campo in ("autor", "cadastrado_por", "encontrado_por")
            )
        if corresponde_pesquisa(codigo, pesquisavel, termo):
            resultado.append((codigo, item))
    return resultado


def concluir_acao(banco, codigo, acesso, acao, item, dados=None):
    try:
        alterar_objeto(banco, codigo, acesso, acao, dados, esperado=item)
    except (PermissionError, ValueError) as erro:
        st.error(str(erro))
    except GoogleAPICallError:
        st.error("Não foi possível confirmar a alteração. Atualize a lista antes de tentar novamente.")
    else:
        st.session_state.pop("ranking_admin", None)
        st.session_state.get("gestao_bases", {}).pop(codigo, None)
        st.session_state["aviso_gestao"] = {"editar": "Cadastro atualizado.", "arquivar": "Item arquivado. Você pode restaurá-lo pelo filtro Arquivado.",
                                           "restaurar": "Item restaurado para em aberto."}[acao]
        st.rerun()


def mostrar_gerenciamento(banco, usuario):
    if usuario.get("permissao") != "admin":
        return
    st.divider()
    st.subheader("Gerenciar objetos")
    acesso = dict(st.session_state.get("acesso", {}))
    try:
        registros = carregar_objetos_admin(banco, acesso)
    except (PermissionError, GoogleAPICallError) as erro:
        st.error(str(erro) if isinstance(erro, PermissionError) else "Não foi possível carregar os objetos.")
        return
    aviso = st.session_state.pop("aviso_gestao", None)
    if aviso:
        st.success(aviso)
    if st.button("Atualizar lista", key="atualizar_gestao"):
        st.session_state.pop("gestao_bases", None)
        for chave in list(st.session_state):
            if chave.startswith(("nome_edicao_", "cor_edicao_", "local_edicao_", "data_edicao_", "descricao_edicao_",
                                 "foto_edicao_", "categoria_edicao_", "edicao_")):
                del st.session_state[chave]
    termo = st.text_input("Pesquisar em todos os objetos", placeholder="Nome, RA ou código", key="pesquisa_gestao")
    tipo = st.selectbox("Tipo de objeto", ["Todos", "Perdido", "Encontrado"], key="tipo_gestao")
    situacao = st.selectbox("Situação do cadastro", ["Todas", "Em aberto", "Arquivado", "Devolvido"], key="situacao_gestao")
    try:
        filtrados = filtrar_objetos(registros, termo, tipo, situacao, banco)
    except GoogleAPICallError:
        st.error("Não foi possível consultar os responsáveis pelos objetos.")
        return
    st.caption(f"{len(filtrados)} de {len(registros)} objetos. Devolvidos ficam apenas para consulta.")
    if not filtrados:
        st.info("Nenhum objeto corresponde aos filtros.")
        return
    filtro = f"{tipo}_{situacao}_{termo}_{len(filtrados)}"
    pagina = st.selectbox("Página de gerenciamento", range(1, (len(filtrados) + 9) // 10 + 1), key=f"pagina_gestao_{filtro}")
    opcoes = dict(filtrados[(pagina - 1) * 10:pagina * 10])
    codigo = st.selectbox("Objeto para gerenciar", list(opcoes), index=None,
                          format_func=lambda c: f"{opcoes[c].get('tipo')} — {opcoes[c].get('nome')} — {opcoes[c].get('status')} — {c}",
                          key=f"objeto_gestao_{filtro}_{pagina}")
    if codigo is None:
        return
    item = opcoes[codigo]
    mostrar_detalhes(item, codigo, banco)
    st.write("Autor:", identificar_pessoa(banco, item.get("autor_uid"), item.get("autor_ra"), item.get("autor_nome")))
    st.write("Situação:", item.get("status", "Não informado"))
    if item_devolvido(item):
        st.info("Item devolvido: disponível apenas para consulta, para preservar o histórico.")
        return
    bases = st.session_state.setdefault("gestao_bases", {})
    if codigo not in bases:
        bases[codigo] = item
    if bases[codigo] != item:
        st.warning("O cadastro mudou desde que você o abriu. Clique em Atualizar lista e confira os dados novamente.")
        return
    if item.get("status") == "arquivado":
        st.info("Este item está arquivado e não aparece nas listas e buscas normais.")
        if st.button("Restaurar item", key=f"restaurar_{codigo}"):
            concluir_acao(banco, codigo, acesso, "restaurar", item)
        return
    if item.get("status") != "aberto":
        st.info("Este cadastro está disponível apenas para consulta.")
        return
    categoria_atual = item.get("categoria", "Outros")
    categoria = st.selectbox("Categoria para edição", CATEGORIAS,
                             index=CATEGORIAS.index(categoria_atual) if categoria_atual in CATEGORIAS else CATEGORIAS.index("Outros"),
                             key=f"categoria_edicao_{codigo}")
    with st.form(f"editar_objeto_{codigo}"):
        nome = st.text_input("Nome do objeto", value=item.get("nome", ""), max_chars=100, key=f"nome_edicao_{codigo}")
        cor = st.text_input("Cor", value=item.get("cor", ""), max_chars=50, key=f"cor_edicao_{codigo}")
        local = st.text_input("Local da perda ou encontro", value=item.get("local", ""), max_chars=150, key=f"local_edicao_{codigo}")
        try:
            data_atual = date.fromisoformat(item.get("data_ocorrido", ""))
        except (ValueError, TypeError):
            data_atual = date.today()
        data = st.date_input("Data da perda ou encontro", value=max(date(2000, 1, 1), min(data_atual, date.today())),
                             min_value=date(2000, 1, 1), max_value=date.today(), key=f"data_edicao_{codigo}")
        descricao = st.text_area("Descrição e características", value=item.get("descricao", ""), max_chars=1000, key=f"descricao_edicao_{codigo}")
        caracteristicas = campos_caracteristicas(categoria, f"edicao_{codigo}_{categoria}", item.get("caracteristicas"))
        foto = st.text_input("Link da foto no Google Drive — opcional", value=item.get("foto_url", ""), max_chars=1000, key=f"foto_edicao_{codigo}")
        salvar = st.form_submit_button("Salvar alterações")
    if salvar:
        concluir_acao(banco, codigo, acesso, "editar", item, dict(nome=nome, categoria=categoria, cor=cor, local=local,
                      data_ocorrido=data.isoformat(), descricao=descricao, caracteristicas=caracteristicas, foto_url=foto))
    st.caption("Remover item arquiva o cadastro. Os dados e o código são preservados e podem ser restaurados.")
    with st.form(f"arquivar_objeto_{codigo}"):
        confirmado = st.checkbox(f"Confirmo remover o item {item.get('nome')} — código {codigo}.")
        remover = st.form_submit_button("Remover item")
    if remover:
        if not confirmado:
            st.warning("Confirme o nome e o código do item antes de remover.")
        else:
            concluir_acao(banco, codigo, acesso, "arquivar", item)
