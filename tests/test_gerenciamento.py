import copy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import test_fluxo as fluxo
from gerenciamento import alterar_objeto, carregar_objetos_admin, filtrar_objetos
from objetos import registrar_objeto, validar_dados_objeto
from correspondencias import classificar_candidatos


class GerenciamentoTest(unittest.TestCase):
    def test_importacao_com_objetos_antigo_em_cache(self):
        # Reproduz um processo do Streamlit que ainda tem o módulo anterior.
        resultado = subprocess.run(
            [sys.executable, "-c", """
import sys
from types import ModuleType
antigo = ModuleType('objetos')
antigo.link_foto_valido = lambda link: True
sys.modules['objetos'] = antigo
from gerenciamento import mostrar_gerenciamento
assert callable(mostrar_gerenciamento)
"""], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def setUp(self):
        self.banco = fluxo.Banco()
        self.admin = fluxo.usuario("admin", "1111111", True)
        self.aluno = fluxo.usuario("aluno", "2222222")
        self.outro = fluxo.usuario("outro", "3333333")
        for pessoa in (self.admin, self.aluno, self.outro):
            self.banco.dados["usuarios"][pessoa["ra"]] = pessoa
        remendo = patch("gerenciamento.firestore.transactional", side_effect=lambda f: f)
        remendo.start()
        self.addCleanup(remendo.stop)
        self.dados = dict(nome="Garrafa azul", tipo="Perdido", categoria="Garrafas e recipientes",
                          cor="Azul", local="Biblioteca", descricao="Garrafa de 750 ml com adesivo",
                          data_ocorrido="2026-10-05", foto_url="", caracteristicas={"capacidade": "750 ml"})
        self.item = dict(self.dados, status="aberto", autor_uid=self.aluno["uid"],
                         autor_nome=self.aluno["nome"], autor_ra=self.aluno["ra"],
                         cadastrado_por_uid=self.aluno["uid"], cadastrado_por_ra=self.aluno["ra"],
                         criado_em="data original", campo_legado="preservar")
        self.banco.dados["itens"]["perdido"] = copy.deepcopy(self.item)
        self.banco.dados["itens"]["encontrado"] = dict(self.item, tipo="Encontrado", autor_uid=self.outro["uid"],
                                                     autor_ra=self.outro["ra"], encontrado_por_ra=self.outro["ra"])

    def alterar(self, acao, codigo="perdido", dados=None, **kwargs):
        alterar_objeto(self.banco, codigo, fluxo.acesso(self.admin), acao, dados, **kwargs)

    def tela(self, usuario=None):
        pessoa = usuario or self.admin
        app = AppTest.from_string('''
import streamlit as st
from gerenciamento import mostrar_gerenciamento
mostrar_gerenciamento(st.session_state['banco'], st.session_state['usuario'])
''', default_timeout=15)
        app.session_state["banco"] = self.banco
        app.session_state["usuario"] = pessoa
        app.session_state["acesso"] = fluxo.acesso(pessoa)
        app.run()
        self.assertFalse(app.exception)
        return app

    def selecionar(self, app, codigo="perdido"):
        next(s for s in app.selectbox if s.label == "Objeto para gerenciar").set_value(codigo).run()
        self.assertFalse(app.exception)

    def test_edicao_preserva_codigo_tipo_autoria_e_metadados(self):
        for codigo in ("perdido", "encontrado"):
            with self.subTest(codigo=codigo):
                antes = copy.deepcopy(self.banco.dados["itens"][codigo])
                self.alterar("editar", codigo, dict(self.dados, nome="Garrafa corrigida", autor_uid="invasor",
                                                   status="resolvido", tipo="invalido", criado_em="alterado"))
                atual = self.banco.dados["itens"][codigo]
                self.assertEqual(atual["nome"], "Garrafa corrigida")
                for campo in ("tipo", "status", "autor_uid", "autor_ra", "cadastrado_por_uid", "criado_em", "campo_legado"):
                    self.assertEqual(atual[campo], antes[campo])
                self.assertEqual(atual["atualizado_por_uid"], self.admin["uid"])
        self.assertEqual(set(self.banco.dados["itens"]), {"perdido", "encontrado"})

    def test_arquivar_e_restaurar_sem_excluir_dados(self):
        self.alterar("arquivar")
        arquivado = self.banco.dados["itens"]["perdido"]
        self.assertEqual(arquivado["status"], "arquivado")
        for campo, valor in self.item.items():
            if campo != "status":
                self.assertEqual(arquivado[campo], valor)
        self.assertEqual(arquivado["arquivado_por_ra"], self.admin["ra"])
        self.alterar("restaurar")
        self.assertEqual(self.banco.dados["itens"]["perdido"]["status"], "aberto")
        self.assertEqual(self.banco.dados["itens"]["perdido"]["restaurado_por_uid"], self.admin["uid"])

    def test_nao_admin_expirado_inativo_ou_revogado_nao_le_nem_altera(self):
        sessoes = [fluxo.acesso(self.aluno), {}, dict(fluxo.acesso(self.admin), expira_em=0),
                   dict(fluxo.acesso(self.admin), hash="incorreto")]
        for sessao in sessoes:
            for acao in ("editar", "arquivar", "restaurar"):
                antes = copy.deepcopy(self.banco.dados)
                with self.assertRaises(PermissionError):
                    alterar_objeto(self.banco, "perdido", sessao, acao, self.dados)
                self.assertEqual(self.banco.dados, antes)
            with self.assertRaises(PermissionError):
                carregar_objetos_admin(self.banco, sessao)
        sessao = fluxo.acesso(self.admin)
        for campo, valor in (("permissao", "usuario"), ("ativo", False)):
            with self.subTest(campo=campo):
                original = self.admin[campo]
                self.admin[campo] = valor
                with self.assertRaises(PermissionError):
                    alterar_objeto(self.banco, "perdido", sessao, "editar", self.dados)
                self.admin[campo] = original

    def test_devolvidos_e_vinculados_sao_imutaveis(self):
        for vinculo in ({"status": "resolvido"}, {"devolucao_id": "devolucao"}, {"correspondencia_id": "outro"}):
            self.banco.dados["itens"]["perdido"] = dict(self.item, **vinculo)
            for acao in ("editar", "arquivar", "restaurar"):
                antes = copy.deepcopy(self.banco.dados)
                with self.assertRaisesRegex(ValueError, "apenas para consulta"):
                    self.alterar(acao, dados=self.dados)
                self.assertEqual(self.banco.dados, antes)

    def test_estado_e_confirmacao_desatualizados_nao_sobrescrevem(self):
        esperado = copy.deepcopy(self.item)
        self.banco.dados["itens"]["perdido"]["nome"] = "Alterado em outra sessão"
        for acao in ("editar", "arquivar"):
            with self.assertRaisesRegex(ValueError, "cadastro mudou"):
                self.alterar(acao, dados=self.dados, esperado=esperado)
        self.alterar("arquivar")
        for acao in ("editar", "arquivar"):
            with self.assertRaises(ValueError):
                self.alterar(acao, dados=self.dados)
        with self.assertRaises(ValueError):
            self.alterar("editar", codigo="inexistente", dados=self.dados)

    def test_validacoes_compartilhadas_sem_escrita_em_dados_invalidos(self):
        for campos in ({"nome": "X"}, {"categoria": "inexistente"}, {"descricao": "curta"},
                       {"cor": ""}, {"local": ""}, {"data_ocorrido": "2099-01-01"},
                       {"foto_url": "https://example.com/foto"}, {"caracteristicas": {"capacidade": "grande"}},
                       {"caracteristicas": {"rodinhas": "Sim"}}):
            dados = dict(self.dados, **campos)
            antes = copy.deepcopy(self.banco.dados)
            for executar in (
                lambda: validar_dados_objeto(dados),
                lambda: self.alterar("editar", dados=dados),
                lambda: registrar_objeto(self.banco, dados, fluxo.acesso(self.aluno)),
            ):
                with self.assertRaises(ValueError):
                    executar()
                self.assertEqual(self.banco.dados, antes)

    def test_filtros_busca_global_e_ra_de_legado(self):
        self.banco.dados["itens"]["antigo"] = dict(self.item)
        self.banco.dados["itens"]["antigo"].pop("autor_ra")
        self.banco.dados["itens"]["antigo"].pop("cadastrado_por_ra")
        self.alterar("arquivar", "encontrado")
        registros = carregar_objetos_admin(self.banco, fluxo.acesso(self.admin))
        for termo in ("garrafa", self.aluno["ra"], "antigo"):
            self.assertIn("antigo", dict(filtrar_objetos(registros, termo, banco=self.banco)))
        self.assertEqual([c for c, _ in filtrar_objetos(registros, tipo="Encontrado", situacao="Arquivado")], ["encontrado"])
        self.assertNotIn("encontrado", dict(filtrar_objetos(registros, situacao="Em aberto")))

    def test_arquivados_fora_das_listas_e_correspondencias_normais(self):
        self.alterar("arquivar", "encontrado")
        candidatos = list(self.banco.dados["itens"].items())
        self.assertFalse(classificar_candidatos(self.item, [("encontrado", self.banco.dados["itens"]["encontrado"])]))
        from google.cloud.firestore_v1.base_query import FieldFilter
        normais = list(self.banco.collection("itens").where(filter=FieldFilter("status", "==", "aberto")).stream())
        self.assertEqual([doc.id for doc in normais], ["perdido"])
        self.assertEqual(len(candidatos), 2)

    def test_interface_escondida_para_usuario_comum(self):
        with patch("gerenciamento.carregar_objetos_admin") as carregar:
            app = self.tela(self.aluno)
            self.assertFalse(app.subheader)
            carregar.assert_not_called()

    def test_interface_editar_confirmar_remocao_e_restaurar(self):
        app = self.tela()
        self.selecionar(app)
        app.text_input(key="nome_edicao_perdido").set_value("Garrafa corrigida")
        next(b for b in app.button if b.label == "Salvar alterações").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.banco.dados["itens"]["perdido"]["nome"], "Garrafa corrigida")
        next(b for b in app.button if b.label == "Remover item").click().run()
        self.assertTrue(app.warning)
        self.assertEqual(self.banco.dados["itens"]["perdido"]["status"], "aberto")
        confirmacao = next(c for c in app.checkbox if c.label.startswith("Confirmo remover"))
        self.assertIn("Garrafa corrigida", confirmacao.label)
        self.assertIn("perdido", confirmacao.label)
        confirmacao.check()
        app.session_state["ranking_admin"] = {"resultados": ["resultado antigo"]}
        next(b for b in app.button if b.label == "Remover item").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.banco.dados["itens"]["perdido"]["status"], "arquivado")
        self.assertNotIn("ranking_admin", app.session_state)
        self.assertFalse(any(b.label == "Salvar alterações" for b in app.button))
        next(b for b in app.button if b.label == "Restaurar item").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.banco.dados["itens"]["perdido"]["status"], "aberto")

    def test_interface_nao_sobrescreve_edicao_de_outra_sessao(self):
        app = self.tela()
        self.selecionar(app)
        app.text_input(key="nome_edicao_perdido").set_value("Minha correção")
        self.banco.dados["itens"]["perdido"]["nome"] = "Correção de outro administrador"
        next(b for b in app.button if b.label == "Salvar alterações").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.warning)
        self.assertEqual(self.banco.dados["itens"]["perdido"]["nome"], "Correção de outro administrador")
        next(b for b in app.button if b.label == "Atualizar lista").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input(key="nome_edicao_perdido").value, "Correção de outro administrador")

    def test_interface_devolvido_consulta_e_pesquisa_antes_de_paginar(self):
        for numero in range(15):
            self.banco.dados["itens"][f"objeto-{numero:02}"] = dict(self.item, nome="Objeto comum")
        self.banco.dados["itens"]["ultimo"] = dict(self.item, nome="Mochila exclusiva", status="resolvido", devolucao_id="historico")
        app = self.tela()
        next(s for s in app.selectbox if s.label == "Página de gerenciamento").set_value(2).run()
        app.text_input(key="pesquisa_gestao").set_value("mochila exclusiva").run()
        self.assertEqual(next(s for s in app.selectbox if s.label == "Página de gerenciamento").value, 1)
        self.selecionar(app, "ultimo")
        self.assertFalse(any(b.label in {"Salvar alterações", "Remover item", "Restaurar item"} for b in app.button))
        self.assertTrue(any("apenas para consulta" in i.value for i in app.info))


if __name__ == "__main__":
    unittest.main()
