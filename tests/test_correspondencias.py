import copy
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from caracteristicas import canonico, comparar_caracteristicas, extrair_caracteristicas
from correspondencias import classificar_candidatos, mostrar_avaliacao, pontuar_objetos
import test_fluxo as fluxo


def item(categoria="Garrafas e recipientes", **campos):
    dados = dict(nome="Objeto", descricao="Objeto com adesivo e sinais de uso",
                 categoria=categoria, cor="Azul", local="Biblioteca",
                 data_ocorrido="2026-10-05", tipo="Encontrado", status="aberto")
    dados.update(campos)
    return dados


class CorrespondenciasTest(unittest.TestCase):
    def test_capacidade_com_negacao_sobre_adesivo_e_ranking(self):
        descricao = "Garrafa térmica Stanley azul de 500 ml, adesivo de coração rosa, base lisa sem amassados; não tem estrela amarela"
        origem = item(nome="Garrafa térmica", descricao=descricao.replace("500 ml", "750 ml"))
        errado = item(nome="Garrafa térmica", descricao=descricao)
        certo = item(nome="Recipiente encontrado", descricao="Garrafa de 750 ml")
        antes = copy.deepcopy((origem, errado, certo))
        self.assertEqual(extrair_caracteristicas(errado)["capacidade"], "500 ml")
        avaliacao = comparar_caracteristicas(origem, errado)
        capacidade = next(d for d in avaliacao["detalhes"] if d["Característica"] == "Capacidade (ml ou L)")
        self.assertEqual(capacidade["Resultado"], "Divergente")
        self.assertEqual(f"Divergência: {capacidade['Origem']} × {capacidade['Candidato']}",
                         "Divergência: 750 ml × 500 ml")
        self.assertGreater(pontuar_objetos(origem, errado)[0], pontuar_objetos(origem, certo)[0])
        ranking = classificar_candidatos(origem, [("500", errado), ("750", certo)])
        self.assertEqual([r["id"] for r in ranking], ["750", "500"])
        with patch("correspondencias.st") as interface:
            mostrar_avaliacao(ranking[1])
            interface.warning.assert_any_call("Capacidade (ml ou L) — Divergência: 750 ml × 500 ml.")
        self.assertEqual((origem, errado, certo), antes)

    def test_capacidade_ausente_ambigua_ou_negada_permanece_desconhecida(self):
        for descricao in (
            "Garrafa sem capacidade informada; não tem estrela amarela",
            "Garrafa de 500 ml ou 750 ml; não tem adesivo",
            "Talvez seja uma garrafa de 500 ml; base lisa",
            "Garrafa que não é de 500 ml; adesivo rosa",
            "Não sei se tem 500 ml; sem amassados",
            "Garrafa de 500 ml; capacidade de 750 ml",
            "Garrafa de aproximadamente 500 ml",
        ):
            with self.subTest(descricao=descricao):
                candidato = item(descricao=descricao)
                self.assertNotIn("capacidade", extrair_caracteristicas(candidato))
                avaliacao = comparar_caracteristicas(item(caracteristicas={"capacidade": "750 ml"}), candidato)
                capacidade = next(d for d in avaliacao["detalhes"] if d["Característica"] == "Capacidade (ml ou L)")
                self.assertEqual(capacidade["Resultado"], "Não informado")

    def test_negacao_em_outra_oracao_preserva_medidas_e_unidades(self):
        for descricao, esperado in (
            ("Garrafa 1,2 L, não tem adesivo", "1200 ml"),
            ("Sem adesivo; garrafa 1.000 ml", "1000 ml"),
            ("Garrafa 500 ml e não tem estrela", "500 ml"),
            ("Garrafa 0,5 L; capacidade 500 ml; não tem adesivo", "500 ml"),
        ):
            with self.subTest(descricao=descricao):
                self.assertEqual(extrair_caracteristicas(item(descricao=descricao))["capacidade"], esperado)

    def cenarios(self):
        return [
            ("Garrafas e recipientes", "Garrafa Stanley", {"marca": "Stanley", "capacidade": "1 L"},
             {"marca": "Outra marca", "capacidade": "500 ml"}),
            ("Roupas e acessórios", "Mochila Jansport", {"marca": "Jansport", "rodinhas": "Não"},
             {"marca": "Kipling", "rodinhas": "Sim"}),
            ("Eletrônicos", "Fone JBL", {"marca": "JBL", "conexao": "Bluetooth", "modelo": "Tune 520"},
             {"marca": "Sony", "conexao": "Com fio", "modelo": "WH 1000"}),
        ]

    def test_divergente_com_texto_identico_sempre_fica_abaixo(self):
        for categoria, nome, atributos, errados in self.cenarios():
            with self.subTest(categoria=categoria):
                origem = item(categoria, nome=nome, caracteristicas=atributos)
                errado = dict(origem, caracteristicas=errados)
                certo = dict(origem, nome="Objeto encontrado", descricao="Marcas de uso visíveis")
                self.assertGreater(pontuar_objetos(origem, errado)[0], 99)
                self.assertGreater(pontuar_objetos(origem, errado)[0], pontuar_objetos(origem, certo)[0])
                ranking = classificar_candidatos(origem, [("errado", errado), ("certo", certo)])
                self.assertEqual([r["id"] for r in ranking], ["certo", "errado"])
                self.assertTrue(ranking[1]["avaliacao"]["divergencias"])

    def test_ausencia_nao_e_divergencia_nem_acordo(self):
        origem = item(caracteristicas={"marca": "Stanley", "capacidade": "1 L"})
        ausente = item(nome="Sem detalhes", cor="", descricao="")
        avaliacao = comparar_caracteristicas(origem, ausente)
        self.assertFalse(avaliacao["divergencias"])
        self.assertEqual(avaliacao["compativeis"], 0)
        self.assertEqual(avaliacao["situacao"], "Dados insuficientes")
        errado = item(caracteristicas={"marca": "Contigo"})
        ranking = classificar_candidatos(origem, [("errado", errado), ("ausente", ausente)])
        self.assertEqual(ranking[0]["id"], "ausente")

    def test_normalizacao_e_unidades(self):
        self.assertEqual(canonico("capacidade", "1,2 L"), canonico("capacidade", "1200 ml"))
        self.assertEqual(canonico("capacidade", "1 L"), canonico("capacidade", "1.000 ml"))
        self.assertEqual(canonico("cor", "Preta"), canonico("cor", "preto"))
        self.assertEqual(canonico("conexao", "sem fio"), canonico("conexao", "Bluetooth"))
        for invalido in ("grande", "0 ml", "-1 L", "1", "talvez 1 L"):
            self.assertEqual(canonico("capacidade", invalido), "")
        self.assertEqual(canonico("modelo", "Preta"), "preta")
        self.assertEqual(canonico("cor", "Azul escuro"), "azul")
        self.assertEqual(canonico("cor", "Azul com tampa preta"), "")

    def test_legados_claros_ambiguos_e_precedencia_dos_campos(self):
        antigo = item(nome="Garrafa Stanley 1,2 L", descricao="Garrafa de aço inox")
        valores = extrair_caracteristicas(antigo)
        self.assertEqual(valores["marca"], "stanley")
        self.assertEqual(valores["capacidade"], "1200 ml")
        self.assertEqual(valores["material"], "aco inox")
        self.assertNotIn("modelo", valores)
        for texto in ("Talvez Stanley ou Contigo 1 L", "Não é Stanley", "Parece uma garrafa 500 ml"):
            self.assertNotIn("marca", extrair_caracteristicas(item(nome=texto)))
            self.assertNotIn("capacidade", extrair_caracteristicas(item(nome=texto)))
        self.assertNotIn("marca", extrair_caracteristicas(item(nome="Garrafa com adesivo Stanley")))
        self.assertNotIn("capacidade", extrair_caracteristicas(item(nome="Garrafa 500 ml", descricao="Garrafa 1 L")))
        self.assertEqual(extrair_caracteristicas(dict(antigo, caracteristicas={"capacidade": "750 ml"}))["capacidade"], "750 ml")
        self.assertEqual(extrair_caracteristicas(item(nome="Garrafa", descricao="Marca: Acme; Modelo: X-10"))["marca"], "acme")
        mochila = extrair_caracteristicas(item("Roupas e acessórios", nome="Mochila sem rodinhas"))
        self.assertEqual(mochila["rodinhas"], "nao")
        fone = extrair_caracteristicas(item("Eletrônicos", nome="Fone Sony com fio"))
        self.assertEqual(fone["conexao"], "com fio")

    def test_filtros_desempate_e_preservacao(self):
        origem = item()
        candidatos = [("z", item()), ("a", item()), ("resolvido", item(status="resolvido")),
                      ("categoria", item("Chaves"))]
        antes = copy.deepcopy((origem, candidatos))
        self.assertEqual([r["id"] for r in classificar_candidatos(origem, candidatos)], ["a", "z"])
        self.assertEqual((origem, candidatos), antes)

    def test_mesmo_ranking_e_motivos_nas_duas_interfaces_sem_escritas(self):
        for categoria, nome, atributos, errados in self.cenarios():
            with self.subTest(categoria=categoria):
                banco = fluxo.Banco()
                dono = fluxo.usuario("aluno", "2222222")
                origem = item(categoria, nome=nome, tipo="Perdido", autor_uid=dono["uid"], caracteristicas=atributos)
                banco.dados["itens"] = {
                    "perdido": origem,
                    "errado": dict(origem, tipo="Encontrado", autor_uid="admin", caracteristicas=errados),
                    "certo": dict(origem, tipo="Encontrado", autor_uid="admin", nome="Objeto recuperado", descricao="Sinais visíveis"),
                }
                # Garante que a busca do aluno não corta os candidatos antes de ordenar.
                for numero in range(101):
                    banco.dados["itens"][f"outro-{numero}"] = item(categoria, caracteristicas=errados)
                banco.dados["itens"]["certo"] = banco.dados["itens"].pop("certo")
                antes = copy.deepcopy(banco.dados)
                app = AppTest.from_string('''
import streamlit as st
from correspondencias import mostrar_correspondencias
from devolucoes import mostrar_devolucoes
mostrar_correspondencias(st.session_state['banco'], st.session_state['dono'])
mostrar_devolucoes(st.session_state['banco'], {'permissao': 'admin'})
''', default_timeout=15)
                app.session_state["banco"] = banco
                app.session_state["dono"] = dono
                app.run()
                next(b for b in app.button if b.label == "Buscar correspondências").click().run()
                self.assertFalse(app.exception)
                self.assertIn("Objeto recuperado", app.expander[0].label)
                next(t for t in app.text_input if t.label == "Código do cadastro perdido").set_value("perdido")
                next(b for b in app.button if b.label == "Buscar objetos encontrados").click().run()
                self.assertFalse(app.exception)
                ranking = app.session_state["ranking_admin"]["resultados"]
                self.assertEqual(ranking[0]["id"], "certo")
                seletor = next(s for s in app.selectbox if s.label == "Objeto encontrado para conferir")
                seletor.set_value("errado").run()
                self.assertFalse(app.exception)
                self.assertTrue(app.warning)
                self.assertIn("×", app.warning[0].value)
                self.assertEqual(banco.dados, antes)


if __name__ == "__main__":
    unittest.main()
