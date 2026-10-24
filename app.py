import hashlib
import html
import hmac
import time
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import GoogleAPICallError
import streamlit as st

from objetos import mostrar_objetos
from correspondencias import mostrar_correspondencias
from devolucoes import mostrar_devolucoes


# -----------------------------------------------------------------------------
# Configuração da página e identidade visual
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Reencontro — arquivo de objetos",
    page_icon="R",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --rr-paper: var(--background-color, #F4F1E9);
        --rr-panel: var(--secondary-background-color, #FBFAF6);
        --rr-ink: var(--text-color, #24251F);
        --rr-muted: #62635C;
        --rr-line: var(--border-color, #D8D1C5);
        --rr-accent: var(--primary-color, #3F6B58);
    }

    .stApp {
        color: var(--rr-ink);
    }

    [data-testid="stMainBlockContainer"] {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 5rem;
    }

    h1, h2, h3 {
        color: var(--rr-ink);
        letter-spacing: 0;
    }

    h1 {
        font-size: 3.25rem;
        line-height: 1.08;
    }

    h2 {
        font-size: 2rem;
        line-height: 1.2;
    }

    h3 {
        font-size: 1.25rem;
    }

    [data-testid="stCaptionContainer"] {
        color: var(--rr-muted);
        font-size: .82rem;
    }

    hr {
        border: 0;
        border-top: 1px solid var(--rr-line);
        margin: 1.5rem 0;
    }

    .masthead {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        border-top: 2px solid var(--rr-ink);
        border-bottom: 1px solid var(--rr-line);
        padding: .8rem 0 1rem;
        margin-bottom: 2rem;
    }

    .wordmark {
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 1.65rem;
        font-weight: 600;
        color: var(--rr-ink);
    }

    .wordmark span {
        color: var(--rr-accent);
    }

    .mast-meta, .mono {
        font-family: ui-monospace, Consolas, monospace;
        font-size: .72rem;
        text-transform: uppercase;
        color: var(--rr-muted);
    }

    .hero-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.6fr) minmax(220px, .7fr);
        gap: 2.5rem;
        align-items: end;
        padding: .75rem 0 1.75rem;
        border-bottom: 1px solid var(--rr-ink);
        margin-bottom: 1.75rem;
    }

    .hero-title {
        margin: .5rem 0 .75rem;
    }

    .hero-copy {
        max-width: 600px;
        font-size: 1rem;
        line-height: 1.65;
        color: var(--rr-muted);
    }

    .hero-note {
        border-left: 1px solid var(--rr-line);
        padding: .2rem 0 .2rem 1rem;
        color: var(--rr-muted);
        font-size: .9rem;
        line-height: 1.65;
    }

    .hero-note strong {
        color: var(--rr-ink);
        display: block;
        margin-bottom: .35rem;
    }

    .section-kicker {
        font-family: ui-monospace, Consolas, monospace;
        color: var(--rr-muted);
        text-transform: uppercase;
        font-size: .72rem;
        margin-bottom: .45rem;
    }

    .page-heading {
        border-bottom: 1px solid var(--rr-ink);
        padding: .6rem 0 1.3rem;
        margin-bottom: 1.5rem;
    }

    .page-heading p {
        color: var(--rr-muted);
        max-width: 650px;
        line-height: 1.6;
    }

    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus,
    [data-testid="stDateInput"] input:focus,
    [data-testid="stNumberInput"] input:focus,
    [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
        outline: 2px solid var(--rr-accent);
        outline-offset: 1px;
    }

    .stButton > button:focus-visible,
    [data-testid="stFormSubmitButton"] button:focus-visible,
    [data-testid="stLinkButton"] a:focus-visible {
        outline: 2px solid var(--rr-accent);
        outline-offset: 2px;
    }

    [data-testid="stForm"] {
        background: var(--rr-panel);
        border: 1px solid var(--rr-line);
        padding: 1.25rem 1.35rem 1rem;
    }

    [data-testid="stExpander"] {
        border: 0;
        border-top: 1px solid var(--rr-line);
        border-radius: 0;
        background: transparent;
    }

    [data-testid="stExpander"] summary {
        padding: .9rem .2rem;
        font-weight: 600;
        color: var(--rr-ink);
    }

    .login-title {
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 2rem;
        line-height: 1.1;
        color: var(--rr-ink);
    }

    .login-copy {
        color: var(--rr-muted);
        line-height: 1.65;
        margin: .8rem 0 1.5rem;
    }

    .footer-line {
        border-top: 1px solid var(--rr-line);
        margin-top: 2rem;
        padding-top: 1rem;
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        color: var(--rr-muted);
        font-family: ui-monospace, Consolas, monospace;
        font-size: .72rem;
        text-transform: uppercase;
    }

    @media (max-width: 700px) {
        [data-testid="stMainBlockContainer"] {
            padding: 1rem 1rem 3rem;
        }

        .masthead {
            margin-bottom: 1.4rem;
        }

        .mast-meta {
            text-align: right;
        }

        .hero-grid {
            grid-template-columns: 1fr;
            gap: 1.2rem;
        }

        .hero-note {
            max-width: 420px;
        }

        h1 {
            font-size: 2.45rem;
        }

        h2 {
            font-size: 1.7rem;
        }

        .login-title {
            font-size: 1.8rem;
        }

        .footer-line {
            flex-direction: column;
            gap: .4rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Firebase — mantém a configuração existente
# -----------------------------------------------------------------------------
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
            credencial = credentials.Certificate(dict(st.secrets["firebase"]))

        firebase_admin.initialize_app(credencial)

    return firestore.client()


try:
    banco = conectar_banco()
except (FileNotFoundError, ValueError, KeyError):
    st.markdown(
        "<div class='masthead'><div class='wordmark'>re<span>en</span>contro</div>"
        "<div class='mast-meta'>Arquivo de objetos · acesso restrito</div></div>",
        unsafe_allow_html=True,
    )
    st.error("Não foi possível carregar a configuração do Firebase.")
    st.caption(
        "Verifique o arquivo .segredos/firebase-admin.json ou a configuração st.secrets."
    )
    st.stop()


def buscar_usuario(ra):
    try:
        documento = banco.collection("usuarios").document(ra).get(timeout=15)
    except GoogleAPICallError:
        st.error("Não foi possível consultar o banco. Tente novamente.")
        st.stop()

    return documento.to_dict() if documento.exists else None


def cabecalho(usuario=None):
    nome = usuario.get("nome", "") if usuario else "Acesso acadêmico"
    nome_exibicao = html.escape(nome)
    st.markdown(
        "<div class='masthead'>"
        "<div class='wordmark'>re<span>en</span>contro</div>"
        f"<div class='mast-meta'>Arquivo de objetos &nbsp; / &nbsp; {nome_exibicao}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


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

    cabecalho()

    esquerda, direita = st.columns([1.15, 1], gap="large")

    with esquerda:
        st.markdown(
            "<div class='section-kicker'>Um arquivo para reencontrar</div>",
            unsafe_allow_html=True,
        )
        st.markdown("# Algumas coisas merecem voltar.")
        st.markdown(
            "<p class='hero-copy'>Um lugar para registrar objetos perdidos e encontrados, "
            "cruzar detalhes e ajudar cada coisa a voltar para quem sente falta dela.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='footer-line'><span>Registrar</span>"
            "<span>Comparar</span><span>Devolver</span></div>",
            unsafe_allow_html=True,
        )

    with direita:
        st.markdown(
            "<div class='section-kicker'>Acesso de estudante</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='login-title'>Entrar no arquivo</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='login-copy'>Use seu RA e o token de acesso fornecido "
            "pela equipe do projeto.</div>",
            unsafe_allow_html=True,
        )

        with st.form("login", clear_on_submit=True):
            ra = st.text_input(
                "Registro acadêmico (RA)",
                max_chars=7,
                placeholder="7 dígitos",
            )
            token = st.text_input(
                "Token de acesso",
                type="password",
                max_chars=128,
            )
            entrar = st.form_submit_button(
                "Entrar no Reencontro",
                type="primary",
                use_container_width=True,
            )

    if entrar:
        ra = ra.strip()
        token = token.strip()
        usuario = None

        if len(ra) == 7 and ra.isascii() and ra.isdigit() and token:
            usuario = buscar_usuario(ra)

        hash_digitado = hashlib.sha256(token.encode("utf-8")).hexdigest()

        if (
            usuario
            and usuario.get("ativo") is True
            and hmac.compare_digest(hash_digitado, usuario.get("token_hash", ""))
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


# -----------------------------------------------------------------------------
# Aplicação principal
# -----------------------------------------------------------------------------
usuario = exigir_login()
cabecalho(usuario)

st.markdown(
    "<div class='hero-grid'>"
    "<div><div class='section-kicker'>Caderno de achados · edição 01</div>"
    "<h1 class='hero-title'>Tudo o que se perde<br>pode ser reencontrado.</h1>"
    "<div class='hero-copy'>Registre um objeto, compare informações e ajude a fechar "
    "o caminho entre quem perdeu e quem encontrou.</div></div>"
    "<div class='hero-note'><strong>Como funciona</strong>Cadastre os detalhes com cuidado. "
    "O sistema procura semelhanças; a confirmação final sempre depende de uma pessoa.</div>"
    "</div>",
    unsafe_allow_html=True,
)

opcoes = ["Objetos", "Correspondências"]

if usuario.get("permissao") == "admin":
    opcoes.append("Devoluções")

pagina = st.radio(
    "Índice do arquivo",
    options=opcoes,
    horizontal=True,
    label_visibility="collapsed",
    key="navegacao_principal",
)

with st.sidebar:
    st.markdown("### Reencontro")
    st.caption(f"Conectado como {usuario.get('nome', 'estudante')}")
    st.caption(f"RA {usuario.get('ra', '')}")

    if st.button("Sair da conta", use_container_width=True):
        st.session_state.clear()
        st.rerun()


if pagina == "Objetos":
    st.markdown(
        "<div class='page-heading'><div class='section-kicker'>01 / Registro</div>"
        "<h2>Objetos do arquivo</h2>"
        "<p>Registre uma perda ou um achado e consulte os itens que você já cadastrou.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    mostrar_objetos(banco, usuario)

elif pagina == "Correspondências":
    st.markdown(
        "<div class='page-heading'><div class='section-kicker'>02 / Pesquisa</div>"
        "<h2>Possíveis reencontros</h2>"
        "<p>Compare os detalhes do seu cadastro com objetos da mesma categoria e veja quais se parecem mais.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    mostrar_correspondencias(banco, usuario)

else:
    st.markdown(
        "<div class='page-heading'><div class='section-kicker'>03 / Conferência</div>"
        "<h2>Registrar uma devolução</h2>"
        "<p>Área restrita à equipe responsável. Confira os dois cadastros antes de confirmar a entrega.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    mostrar_devolucoes(banco, usuario)


st.markdown(
    "<div class='footer-line'><span>Reencontro · arquivo de objetos</span>"
    "<span>Feito para aproximar pessoas e coisas</span></div>",
    unsafe_allow_html=True,
)