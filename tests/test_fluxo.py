import copy
from datetime import datetime, timezone
import time
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from objetos import registrar_objeto
from devolucoes import confirmar_devolucao
from historico import carregar_historico, formatar_data_devolucao
from identificacao import identificar_pessoa


class Documento:
    def __init__(self, banco, colecao, codigo):
        self.banco, self.colecao, self.id = banco, colecao, codigo

    def get(self, **kwargs):
        return self

    def to_dict(self):
        return copy.deepcopy(self.banco.dados[self.colecao].get(self.id))


class Consulta:
    def __init__(self, banco, nome, filtros=(), limite=None):
        self.banco, self.nome = banco, nome
        self.filtros, self.limite = filtros, limite

    def document(self, codigo=None):
        if codigo is None:
            self.banco.contador += 1
            codigo = f"novo-{self.banco.contador}"
        return Documento(self.banco, self.nome, codigo)

    def where(self, *, filter):
        return Consulta(self.banco, self.nome, self.filtros + (filter,), self.limite)

    def limit(self, numero):
        return Consulta(self.banco, self.nome, self.filtros, numero)

    def stream(self, **kwargs):
        documentos = [
            Documento(self.banco, self.nome, codigo)
            for codigo, dados in self.banco.dados[self.nome].items()
            if all(dados.get(f.field_path) == f.value for f in self.filtros)
        ]
        return iter(documentos[:self.limite])


class Banco:
    """Substituto em memória: nenhum teste acessa o Firebase."""
    def __init__(self):
        self.dados = {"usuarios": {}, "itens": {}, "devolucoes": {}}
        self.contador = 0

    def collection(self, nome):
        return Consulta(self, nome)

    def transaction(self):
        return self

    def create(self, ref, dados):
        self.dados[ref.colecao][ref.id] = copy.deepcopy(dados)
        if ref.colecao == "devolucoes":
            self.dados[ref.colecao][ref.id]["confirmado_em"] = datetime.now(timezone.utc)

    def update(self, ref, dados):
        self.dados[ref.colecao][ref.id].update(copy.deepcopy(dados))


def usuario(uid, ra, admin=False):
    return dict(uid=uid, ra=ra, nome=uid, ativo=True,
                permissao="admin" if admin else "usuario", token_versao=1, token_hash="hash")


def acesso(pessoa):
    return dict(ra=pessoa["ra"], uid=pessoa["uid"], versao=1,
                hash="hash", expira_em=time.time() + 600)


class FluxoTest(unittest.TestCase):
    def setUp(self):
        self.banco = Banco()
        self.admin = usuario("administrador", "1111111", True)
        self.dono = usuario("proprietario", "2222222")
        self.finder = usuario("encontrou", "3333333")
        self.outro = usuario("outro", "4444444")
        for pessoa in (self.admin, self.dono, self.finder, self.outro):
            self.banco.dados["usuarios"][pessoa["ra"]] = pessoa
        for modulo in ("objetos", "devolucoes"):
            remendo = patch(f"{modulo}.firestore.transactional", side_effect=lambda funcao: funcao)
            remendo.start()
            self.addCleanup(remendo.stop)
        self.item = dict(nome="Garrafa azul", tipo="Perdido", categoria="Outros",
                         cor="Azul", local="Biblioteca", data_ocorrido="2026-10-05",
                         descricao="Garrafa com adesivo", foto_url="")

    def cadastrar_par(self):
        perdido = registrar_objeto(self.banco, self.item, acesso(self.dono))
        encontrado = registrar_objeto(
            self.banco, dict(self.item, tipo="Encontrado"), acesso(self.admin),
            self.finder["ra"], True,
        )
        return perdido, encontrado

    def devolver(self):
        par = self.cadastrar_par()
        confirmar_devolucao(self.banco, *par, acesso(self.admin))
        return par

    def test_usuario_nao_cadastra_encontrado(self):
        with self.assertRaises(PermissionError):
            registrar_objeto(self.banco, dict(self.item, tipo="Encontrado"),
                             acesso(self.dono), self.finder["ra"], True)
        self.assertFalse(self.banco.dados["itens"])

    def test_recebimento_e_ra_obrigatorios(self):
        for ra, recebido in [(self.finder["ra"], False), ("", True), ("9999999", True)]:
            with self.subTest(ra=ra, recebido=recebido), self.assertRaises(ValueError):
                registrar_objeto(self.banco, dict(self.item, tipo="Encontrado"),
                                 acesso(self.admin), ra, recebido)
        self.assertFalse(self.banco.dados["itens"])

    def test_identidades_separadas(self):
        _, encontrado = self.cadastrar_par()
        item = self.banco.dados["itens"][encontrado]
        self.assertEqual(item["encontrado_por_uid"], self.finder["uid"])
        self.assertEqual(item["cadastrado_por_uid"], self.admin["uid"])

    def test_sessao_expirada_ou_permissao_revogada(self):
        sessao = acesso(self.admin)
        sessao["expira_em"] = 0
        with self.assertRaises(PermissionError):
            registrar_objeto(self.banco, self.item, sessao)
        self.admin["permissao"] = "usuario"
        with self.assertRaises(PermissionError):
            registrar_objeto(self.banco, dict(self.item, tipo="Encontrado"),
                             acesso(self.admin), self.finder["ra"], True)

    def test_devolucao_resolve_par_e_historicos(self):
        par = self.devolver()
        for codigo in par:
            self.assertEqual(self.banco.dados["itens"][codigo]["status"], "resolvido")
        for pessoa in (self.dono, self.finder):
            self.assertEqual(len(carregar_historico(self.banco, pessoa)), 1)
        self.assertEqual(carregar_historico(self.banco, self.admin), [])
        self.assertEqual(carregar_historico(self.banco, self.outro), [])
        self.assertEqual(len(carregar_historico(self.banco, self.admin, todas=True)), 1)
        with self.assertRaises(PermissionError):
            carregar_historico(self.banco, self.outro, todas=True)

    def test_devolucao_repetida_nao_cria_historico_duplicado(self):
        par = self.devolver()
        with self.assertRaises(ValueError):
            confirmar_devolucao(self.banco, *par, acesso(self.admin))
        self.assertEqual(len(self.banco.dados["devolucoes"]), 1)

    def test_usuario_nao_confirma_devolucao(self):
        par = self.cadastrar_par()
        with self.assertRaises(PermissionError):
            confirmar_devolucao(self.banco, *par, acesso(self.dono))
        self.assertFalse(self.banco.dados["devolucoes"])
        self.assertTrue(all(i["status"] == "aberto" for i in self.banco.dados["itens"].values()))

    def test_cadastro_antigo_preserva_autor_como_encontrador(self):
        par = self.cadastrar_par()
        item = self.banco.dados["itens"][par[1]]
        item.pop("encontrado_por_uid")
        item.pop("encontrado_por_nome")
        confirmar_devolucao(self.banco, *par, acesso(self.admin))
        self.assertEqual(len(carregar_historico(self.banco, self.admin)), 1)

    def test_mesma_pessoa_encontrou_e_perdeu_nao_duplica_historico(self):
        self.finder = self.dono
        self.devolver()
        self.assertEqual(len(carregar_historico(self.banco, self.dono)), 1)

    def tela(self, pessoa):
        app = AppTest.from_string("""
import streamlit as st
from objetos import mostrar_objetos
from correspondencias import mostrar_correspondencias
from devolucoes import mostrar_devolucoes
from historico import mostrar_historico
banco, usuario = st.session_state['banco'], st.session_state['usuario']
mostrar_objetos(banco, usuario)
mostrar_correspondencias(banco, usuario)
mostrar_devolucoes(banco, usuario)
mostrar_historico(banco, usuario)
""")
        app.session_state["banco"] = self.banco
        app.session_state["usuario"] = pessoa
        app.session_state["acesso"] = acesso(pessoa)
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_interface_usuario_apenas_perdidos(self):
        app = self.tela(self.dono)
        self.assertFalse(any(s.label == "Situação" for s in app.selectbox))
        self.assertFalse(app.radio)

    def test_interface_admin_cadastro_encontrado(self):
        app = self.tela(self.admin)
        next(s for s in app.selectbox if s.label == "Situação").select("Encontrado").run()
        self.assertFalse(app.exception)
        self.assertTrue(any(t.label == "RA de quem encontrou o objeto" for t in app.text_input))
        self.assertTrue(any("Recebi" in c.label for c in app.checkbox))

    def test_interface_resolvidos_so_no_historico(self):
        self.devolver()
        app = self.tela(self.dono)
        titulos = [e.label for e in app.expander]
        self.assertEqual(len(titulos), 1)
        self.assertTrue(titulos[0].startswith("Devolvido"))
        app_admin = self.tela(self.admin)
        app_admin.radio[0].set_value("Todas as devoluções").run()
        self.assertFalse(app_admin.exception)
        self.assertEqual(len(app_admin.expander), 1)

    def test_interface_cadastro_e_entrega_completos(self):
        perdido = registrar_objeto(self.banco, self.item, acesso(self.dono))
        app = self.tela(self.admin)
        next(s for s in app.selectbox if s.label == "Situação").select("Encontrado").run()
        valores = {
            "RA de quem encontrou o objeto": self.finder["ra"],
            "Nome do objeto": self.item["nome"], "Cor": "Azul",
            "Local da perda ou encontro": "Biblioteca",
        }
        for campo in app.text_input:
            if campo.label in valores:
                campo.set_value(valores[campo.label])
        app.text_area[0].set_value(self.item["descricao"])
        next(s for s in app.selectbox if s.label == "Categoria").set_value("Outros")
        app.checkbox[0].check()
        next(b for b in app.button if b.label == "Salvar objeto").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        next(t for t in app.text_input if t.label == "Código do cadastro perdido").set_value(perdido)
        next(b for b in app.button if b.label == "Buscar objetos encontrados").click().run()
        self.assertFalse(app.exception)
        encontrado = next(c for c, i in self.banco.dados["itens"].items() if i["tipo"] == "Encontrado")
        next(s for s in app.selectbox if s.label == "Objeto encontrado para conferir").set_value(encontrado).run()
        next(c for c in app.checkbox if c.label.startswith("Conferi")).check()
        next(b for b in app.button if b.label == "Confirmar devolução").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(self.banco.dados["devolucoes"]), 1)
        self.assertEqual(len(carregar_historico(self.banco, self.finder)), 1)
        self.assertTrue(all(i["status"] == "resolvido" for i in self.banco.dados["itens"].values()))

    def test_ras_salvos_em_novos_registros(self):
        perdido, encontrado = self.devolver()
        self.assertEqual(self.banco.dados["itens"][perdido]["autor_ra"], self.dono["ra"])
        registro = next(iter(self.banco.dados["devolucoes"].values()))
        for campo, pessoa in (("recebedor", self.dono), ("encontrado_por", self.finder),
                              ("cadastrado_por", self.admin), ("confirmado_por", self.admin)):
            self.assertEqual(registro[f"{campo}_ra"], pessoa["ra"])

    def test_data_devolucao_em_brasilia(self):
        data = datetime(2026, 10, 21, 0, 54, 57, tzinfo=timezone.utc)
        self.assertEqual(formatar_data_devolucao(data), "20/10/2026 às 21:54 (Brasília)")
        self.assertEqual(formatar_data_devolucao(None), "Não informado")

    def test_ra_antigo_resolvido_pelo_uid_sem_escrita(self):
        cache = {}
        self.assertEqual(identificar_pessoa(self.banco, self.dono["uid"], cache=cache), "RA 2222222")
        self.assertEqual(cache[self.dono["uid"]], "2222222")
        self.assertEqual(identificar_pessoa(self.banco, "usuario-excluido"), "RA não localizado")
        # Mesmo que o usuário deixe de existir, o RA salvo na devolução é exibido.
        self.assertEqual(identificar_pessoa(self.banco, "usuario-excluido", "5555555"), "RA 5555555")
        self.assertFalse(self.banco.dados["itens"])
        self.assertFalse(self.banco.dados["devolucoes"])

    def test_interface_historico_antigo_sem_copias(self):
        par = self.cadastrar_par()
        self.banco.dados["devolucoes"]["antiga"] = dict(
            perdido_id=par[0], encontrado_id=par[1], recebedor_uid=self.dono["uid"],
            encontrado_por_uid=self.finder["uid"], confirmado_por_uid=self.admin["uid"],
        )
        app = self.tela(self.finder)
        self.assertEqual(len(app.expander), 1)
        texto = "\n".join(m.value for m in app.markdown)
        self.assertIn("RA 2222222", texto)
        self.assertIn("RA 3333333", texto)
        self.assertIn("RA 1111111", texto)
        self.assertNotIn("RA não localizado", texto)
        self.assertNotIn("Não informado (cadastro antigo)", texto)


if __name__ == "__main__":
    unittest.main()
