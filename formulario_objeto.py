"""Campos e validacoes compartilhados pelo cadastro e gerenciamento."""
from datetime import date
from urllib.parse import urlsplit

import streamlit as st

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


def validar_dados_objeto(dados):
    """Validação compartilhada pelo cadastro e pela edição administrativa."""
    limpos = {campo: str(dados.get(campo) or "").strip() for campo in (
        "nome", "tipo", "categoria", "cor", "local", "descricao", "foto_url", "data_ocorrido"
    )}
    erros = []
    for campo, rotulo, minimo, maximo in (
        ("nome", "Nome", 3, 100), ("cor", "Cor", 2, 50),
        ("local", "Local", 3, 150), ("descricao", "Descrição", 10, 1000),
    ):
        if not minimo <= len(limpos[campo]) <= maximo:
            erros.append(f"{rotulo}: use entre {minimo} e {maximo} caracteres.")
    if limpos["tipo"] not in {"Perdido", "Encontrado"}:
        erros.append("Situação inválida.")
    if limpos["categoria"] not in CATEGORIAS:
        erros.append("Categoria inválida.")
    try:
        data = date.fromisoformat(limpos["data_ocorrido"])
        if not date(2000, 1, 1) <= data <= date.today():
            raise ValueError
    except ValueError:
        erros.append("Confira a data informada.")
    if len(limpos["foto_url"]) > 1000 or not link_foto_valido(limpos["foto_url"]):
        erros.append("Use um link HTTPS do Google Drive ou deixe vazio.")
    caracteristicas = dados.get("caracteristicas", {})
    if not isinstance(caracteristicas, dict):
        erros.append("Características inválidas.")
        caracteristicas = {}
    permitidos = CAMPOS_COMUNS + CAMPOS_CATEGORIA.get(limpos["categoria"], ())
    limpos["caracteristicas"] = {}
    for campo, valor in caracteristicas.items():
        if campo not in permitidos or not isinstance(valor, str) or len(valor.strip()) > 100:
            erros.append("Característica inválida para a categoria.")
            continue
        valor = valor.strip()
        if not valor:
            continue
        if campo in OPCOES and valor not in OPCOES[campo]:
            erros.append(f"{ROTULOS[campo]}: selecione uma opção válida.")
        if campo == "capacidade" and not canonico(campo, valor):
            erros.append("Capacidade: informe um valor positivo em ml ou L, como 750 ml ou 1,2 L.")
        limpos["caracteristicas"][campo] = valor
    if erros:
        raise ValueError("\n".join(erros))
    return limpos


def campos_caracteristicas(categoria, chave, valores=None):
    valores = valores or {}
    resultado = {}
    st.caption("Características opcionais: preencha apenas o que souber com certeza.")
    for campo in CAMPOS_COMUNS + CAMPOS_CATEGORIA[categoria]:
        valor_atual = valores.get(campo, "")
        if campo in OPCOES:
            opcoes = OPCOES[campo]
            valor = st.selectbox(ROTULOS[campo], opcoes, key=f"{chave}_{campo}",
                                 index=opcoes.index(valor_atual) if valor_atual in opcoes else 0,
                                 format_func=lambda v: v or "Não informado")
        else:
            valor = st.text_input(ROTULOS[campo] + " — opcional", max_chars=100,
                                  value=valor_atual, key=f"{chave}_{campo}")
        if valor.strip():
            resultado[campo] = valor.strip()
    return resultado


