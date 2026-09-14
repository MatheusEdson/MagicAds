# -*- coding: utf-8 -*-
"""A receita tem que falhar AQUI, de graca, nao la na Meta, caro.

A Meta recusa payload incompleto com mensagem que nao cita o campo que faltou.
Cada teste abaixo e um erro que ja custou uma tarde a alguem.
"""
import copy
import glob
import json
import os
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from magicads import subir  # noqa: E402

BOA = {
    "tipo": "loja",
    "cliente": "acme",
    "conta": "act_000000000000002",
    "pagina": "000000000000001",
    "pixel": "000000000000003",
    "campanha": {"nome": "[C01] teste"},
    "conjunto": {"verba_diaria": 5000, "geo": {"geo_locations": {"countries": ["BR"]}}},
    "anuncios": [{"nome": "[AD01]", "texto": "oi", "link": "https://exemplo.com.br",
                  "imagem_hash": "00000000000000000000000000000000"}],
}


def sem(caminho, receita=None):
    """Copia a receita boa tirando uma chave, pra provar que ela era obrigatoria."""
    r = copy.deepcopy(receita or BOA)
    alvo = r
    partes = caminho.split(".")
    for p in partes[:-1]:
        alvo = alvo[p]
    alvo.pop(partes[-1], None)
    return r


class ReceitaRecusa(unittest.TestCase):
    def recusa(self, receita, trecho):
        with self.assertRaises(subir.Recusa) as ctx:
            subir.valida(receita)
        self.assertIn(trecho, str(ctx.exception).lower())

    def test_a_receita_boa_passa(self):
        objetivo, otimizacao, destino, _ = subir.valida(BOA)
        self.assertEqual(objetivo, "OUTCOME_SALES")
        self.assertEqual(destino, "site")

    def test_tipo_desconhecido(self):
        r = copy.deepcopy(BOA)
        r["tipo"] = "restaurante"
        self.recusa(r, "desconhecido")

    def test_conta_sem_act(self):
        r = copy.deepcopy(BOA)
        r["conta"] = "000000000000002"
        self.recusa(r, "act_")

    def test_verba_abaixo_do_minimo(self):
        # A conta mais comum: escrever 50 achando "R$50" quando o campo e centavos.
        r = copy.deepcopy(BOA)
        r["conjunto"]["verba_diaria"] = 50
        self.recusa(r, "centavos")

    def test_sem_geo_nao_passa(self):
        self.recusa(sem("conjunto.geo"), "geografia")

    def test_sales_sem_pixel(self):
        # OUTCOME_SALES sem promoted_object sobe e nao otimiza por nada.
        self.recusa(sem("pixel"), "pixel")

    def test_site_sem_link(self):
        r = copy.deepcopy(BOA)
        r["anuncios"][0].pop("link")
        self.recusa(r, "link")

    def test_anuncio_sem_criativo(self):
        r = copy.deepcopy(BOA)
        r["anuncios"][0].pop("imagem_hash")
        self.recusa(r, "imagem_hash")

    def test_formulario_exige_pagina_e_formulario_id(self):
        r = {"tipo": "b2b", "cliente": "acme", "conta": "act_000000000000002",
             "campanha": {"nome": "x"},
             "conjunto": {"verba_diaria": 5000,
                          "geo": {"geo_locations": {"countries": ["BR"]}}},
             "anuncios": [{"nome": "a", "texto": "b",
                           "imagem_hash": "00000000000000000000000000000000"}]}
        self.recusa(r, "pagina")
        r["pagina"] = "000000000000001"
        self.recusa(r, "formulario_id")

    def test_whatsapp_exige_pagina(self):
        r = {"tipo": "local-whatsapp", "cliente": "acme", "conta": "act_000000000000002",
             "campanha": {"nome": "x"},
             "conjunto": {"verba_diaria": 5000,
                          "geo": {"geo_locations": {"countries": ["BR"]}}},
             "anuncios": [{"nome": "a", "texto": "b",
                           "imagem_hash": "00000000000000000000000000000000"}]}
        self.recusa(r, "pagina")


class Avisos(unittest.TestCase):
    """Aviso nao barra: barrar o que e escolha legitima vira gambiarra pra
    contornar o proprio aviso."""

    def test_advantage_em_b2b_avisa(self):
        r = {"tipo": "b2b", "cliente": "acme", "conta": "act_000000000000002",
             "pagina": "000000000000001", "campanha": {"nome": "x"},
             "conjunto": {"verba_diaria": 5000, "advantage_audience": 1,
                          "geo": {"geo_locations": {"countries": ["BR"]}}},
             "anuncios": [{"nome": "a", "texto": "b", "formulario_id": "000000000000004",
                           "imagem_hash": "00000000000000000000000000000000"}]}
        _, _, _, avisos = subir.valida(r)
        self.assertTrue(any("decorativa" in a for a in avisos))

    def test_cbo_avisa_sobre_minimo_por_conjunto(self):
        r = copy.deepcopy(BOA)
        r["campanha"]["verba_diaria"] = 10000
        _, _, _, avisos = subir.valida(r)
        self.assertTrue(any("CBO" in a for a in avisos))


class Montagem(unittest.TestCase):
    def monta(self, receita):
        objetivo, otimizacao, destino, _ = subir.valida(receita)
        return subir.monta(receita, objetivo, otimizacao, destino)

    def test_tudo_nasce_pausado(self):
        # A garantia mais importante do modulo: nao existe caminho que suba ligado.
        camp, conj, criativos, anuncios = self.monta(BOA)
        self.assertEqual(camp["status"], "PAUSED")
        self.assertEqual(conj["status"], "PAUSED")
        self.assertTrue(all(a["status"] == "PAUSED" for a in anuncios))

    def test_special_ad_categories_sempre_vai(self):
        # Campo obrigatorio mesmo vazio; faltando, a Meta recusa sem citar o campo.
        camp, _, _, _ = self.monta(BOA)
        self.assertEqual(json.loads(camp["special_ad_categories"]), [])

    def test_verba_no_conjunto_quando_nao_ha_cbo(self):
        _, conj, _, _ = self.monta(BOA)
        self.assertEqual(conj["daily_budget"], "5000")

    def test_abo_manda_budget_sharing_explicito(self):
        """Sem este campo a Meta RECUSA a campanha inteira, e recusa mal.

        Erro 100 / 4834011. O `message` diz so "Invalid parameter"; o motivo real
        so aparece em `error_user_title`. Foi o primeiro erro da primeira vez que
        o `subir --executar` rodou contra conta de verdade (14/09/2026), e como
        todas as receitas do repo poem a verba no CONJUNTO, isso derrubava 100%
        das subidas na primeira chamada.

        `false` de proposito: `true` faz a Meta repartir ate 20% da verba entre
        os conjuntos, acabando com a separacao por loja ou praca.
        """
        camp, _, _, _ = self.monta(BOA)
        self.assertEqual(camp["is_adset_budget_sharing_enabled"], "false")

    def test_cbo_nao_manda_budget_sharing(self):
        # Com verba na campanha o campo nao se aplica: quem reparte e o CBO.
        r = copy.deepcopy(BOA)
        r["campanha"]["verba_diaria"] = 20000
        camp, _, _, _ = self.monta(r)
        self.assertNotIn("is_adset_budget_sharing_enabled", camp)

    def test_cbo_tira_a_verba_do_conjunto(self):
        # Verba nos dois lugares e erro de conta garantido.
        r = copy.deepcopy(BOA)
        r["campanha"]["verba_diaria"] = 20000
        camp, conj, _, _ = self.monta(r)
        self.assertEqual(camp["daily_budget"], "20000")
        self.assertNotIn("daily_budget", conj)

    def test_numero_do_whatsapp_mora_no_promoted_object(self):
        # Nao no criativo. Quem poe no criativo passa a tarde procurando por que
        # o anuncio abre o Messenger.
        r = {"tipo": "local-whatsapp", "cliente": "acme", "conta": "act_000000000000002",
             "pagina": "000000000000001", "campanha": {"nome": "x"},
             "conjunto": {"verba_diaria": 5000,
                          "geo": {"geo_locations": {"countries": ["BR"]}}},
             "anuncios": [{"nome": "a", "texto": "b",
                           "imagem_hash": "00000000000000000000000000000000"}]}
        _, conj, _, _ = self.monta(r)
        self.assertEqual(conj["destination_type"], "WHATSAPP")
        self.assertEqual(json.loads(conj["promoted_object"])["page_id"], "000000000000001")

    def test_publico_excluido_entra_no_targeting(self):
        r = copy.deepcopy(BOA)
        r["conjunto"]["publicos_excluir"] = ["000000000000007"]
        _, conj, _, _ = self.monta(r)
        alvo = json.loads(conj["targeting"])
        self.assertEqual(alvo["excluded_custom_audiences"], [{"id": "000000000000007"}])

    def test_advantage_audience_sempre_explicito(self):
        # Omitir o campo nao e o mesmo que desligar: a Meta escolhe por voce.
        _, conj, _, _ = self.monta(BOA)
        alvo = json.loads(conj["targeting"])
        self.assertIn("advantage_audience", alvo["targeting_automation"])


class ReceitasDoRepo(unittest.TestCase):
    """Exemplo quebrado e pior que exemplo ausente: quem copia nao desconfia."""

    def test_todas_as_receitas_de_exemplo_validam(self):
        arquivos = sorted(glob.glob(str(RAIZ / "receitas" / "*.json")))
        self.assertTrue(arquivos, "nenhuma receita de exemplo encontrada")
        for caminho in arquivos:
            with open(caminho, encoding="utf-8") as fh:
                r = json.load(fh)
            objetivo, otimizacao, destino, _ = subir.valida(r)
            subir.monta(r, objetivo, otimizacao, destino)

    def test_existe_uma_receita_por_tipo_de_conta(self):
        # Os quatro tipos vem dos agentes Gandalf. Tipo sem receita e tipo que,
        # na pratica, ninguem consegue usar.
        tipos = set()
        for caminho in glob.glob(str(RAIZ / "receitas" / "*.json")):
            with open(caminho, encoding="utf-8") as fh:
                tipos.add(json.load(fh)["tipo"])
        self.assertEqual(tipos, {"b2b", "local-whatsapp", "loja", "balcao"})


if __name__ == "__main__":
    unittest.main()
