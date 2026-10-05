from pathlib import Path
import hashlib
import hmac
import time

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import GoogleAPICallError
import streamlit as st

from objetos import mostrar_objetos
from correspondencias import mostrar_correspondencias
from devolucoes import mostrar_devolucoes

st.set_page_config(
    page_title="Reencontro",
    page_icon="🔎",
)


@st.cache_resource
def conectar_banco():
    try:
        firebase_admin.get_app()
    except ValueError:
        chave = (
            Path(__file__).resolve().parent
            / ".segredos"
            / "firebase-admin.json"
        )

        if chave.is_file():
            credencial = credentials.Certificate(str(chave))
        else:
            credencial = credentials.Certificate(
                dict(st.secrets["firebase"])
            )

        firebase_admin.initialize_app(credencial)

    return firestore.client()

try:
    banco = conectar_banco()
except (FileNotFoundError, ValueError, KeyError):
    st.error("Não foi possível carregar a configuração do Firebase.")
    st.stop()


def buscar_usuario(ra):
    try:
        documento = (
            banco.collection("usuarios")
            .document(ra)
            .get(timeout=15)
        )
    except GoogleAPICallError:
        st.error("Não foi possível consultar o banco. Tente novamente.")
        st.stop()

    return documento.to_dict() if documento.exists else None


def exigir_login():
    acesso = st.session_state.get("acesso")

    if acesso:
        usuario = buscar_usuario(acesso["ra"])

        valido = (
            usuario is not None
            and usuario.get("ativo") is True
            and usuario.get("uid") == acesso["uid"]
            and usuario.get("token_versao") == acesso["versao"]
            and usuario.get("token_hash") == acesso["hash"]
            and time.time() < acesso["expira_em"]
        )

        if valido:
            return usuario

        st.session_state.clear()
        st.warning("Seu acesso expirou ou foi alterado. Entre novamente.")

    st.subheader("Entrar")

    with st.form("login", clear_on_submit=True):
        ra = st.text_input("RA", max_chars=7)
        token = st.text_input(
            "Token",
            type="password",
            max_chars=128,
        )
        entrar = st.form_submit_button("Entrar")

    if entrar:
        ra = ra.strip()
        token = token.strip()
        usuario = None

        if len(ra) == 7 and ra.isascii() and ra.isdigit() and token:
            usuario = buscar_usuario(ra)

        hash_digitado = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

        if (
            usuario
            and usuario.get("ativo") is True
            and hmac.compare_digest(
                hash_digitado,
                usuario.get("token_hash", ""),
            )
        ):
            st.session_state["acesso"] = {
                "ra": ra,
                "uid": usuario["uid"],
                "versao": usuario["token_versao"],
                "hash": hash_digitado,
                "expira_em": time.time() + 8 * 60 * 60,
            }
            st.rerun()
        else:
            st.error("RA ou token inválido.")

    st.stop()


st.title("Reencontro")

usuario = exigir_login()

with st.sidebar:
    st.write(f"Olá, {usuario['nome']}!")
    st.caption(f"RA: {usuario['ra']}")

    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()

st.write(
    "Cadastre objetos perdidos ou encontrados "
    "e busque correspondências."
)

mostrar_objetos(banco, usuario)
mostrar_correspondencias(banco, usuario)
mostrar_devolucoes(banco, usuario)