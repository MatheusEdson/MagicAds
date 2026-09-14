# -*- coding: utf-8 -*-
"""A receita de Search do Google.

Os testes aqui sao quase todos sobre RECUSA. E de proposito: a razao de este
modulo nao ter existido antes nao foi falta de API, foi o risco de gerar Search
sem negativa em dois comandos. O valor dele esta no que ele se nega a montar.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from magicads import subir_google as g  # noqa: E402

RECEITA = json.loads((RAIZ / "receitas" / "google-search-local.json")
                     .read_text(encoding="utf-8"))


def receita(**mudancas):
    r = copy.deepcopy(RECEITA)
    for caminho, valor in mudancas.items():
        alvo = r
        partes = caminho.split("__")
        for p in partes[:-1]:
            alvo = alvo[p]
        if valor is None:
            alvo.pop(partes[-1], None)
        else:
            alvo[partes[-1]] = valor
    return r


class ANegativaEObrigatoria(unittest.TestCase):
    """A regra que faz este modulo valer a pena existir.

    Search sem lista de negativas compra "gratis", "como fazer", "vaga de
    emprego", "curso" e o nome dos concorrentes. Uma receita que gera isso em
    dois comandos e pior que nao ter receita nenhuma.
    """

    def test_sem_negativas_recusa(self):
        with self.assertRaises(g.Recusa) as e:
            g.valida(receita(grupo__negativas=None))
        self.assertIn("negativas", str(e.exception))

    def test_lista_vazia_tambem_recusa(self):
        # o jeito obvio de driblar a regra e escrever []. Nao dribla.
        with self.assertRaises(g.Recusa):
            g.valida(receita(grupo__negativas=[]))

    def test_a_recusa_ensina_por_onde_comecar(self):
        with self.assertRaises(g.Recusa) as e:
            g.valida(receita(grupo__negativas=None))
        # recusa que so diz "faltou X" empurra a pessoa pro caminho errado;
        # aqui ela sai com as quatro primeiras ja escritas.
        for palavra in g.NEGATIVAS_MINIMAS:
            self.assertIn(palavra, str(e.exception))

    def test_negativa_em_branco_recusa(self):
        with self.assertRaises(g.Recusa):
            g.valida(receita(grupo__negativas=["gratis", "   "]))


class OGeoTambemEObrigatorio(unittest.TestCase):
    """Search sem geo entrega no mundo inteiro, e queima verba tao rapido
    quanto falta de negativa. So que mais silenciosamente: a metrica parece
    "so" ruim, em vez de errada."""

    def test_sem_geo_recusa(self):
        with self.assertRaises(g.Recusa) as e:
            g.valida(receita(campanha__geo=None))
        self.assertIn("mundo inteiro", str(e.exception))

    def test_pais_fora_do_mapa_manda_usar_id_cru(self):
        with self.assertRaises(g.Recusa) as e:
            g.valida(receita(campanha__geo={"paises": ["ZZ"]}))
        self.assertIn("ids", str(e.exception))

    def test_id_cru_passa_sem_pais(self):
        g.valida(receita(campanha__geo={"ids": [1001773]}))


class OsLimitesQueOGoogleRecusaSemDizerQual(unittest.TestCase):
    def test_menos_de_tres_titulos(self):
        with self.assertRaises(g.Recusa):
            g.valida(receita(anuncio__titulos=["um", "dois"]))

    def test_menos_de_duas_descricoes(self):
        with self.assertRaises(g.Recusa):
            g.valida(receita(anuncio__descricoes=["uma so"]))

    def test_titulo_com_31_caracteres(self):
        r = receita()
        r["anuncio"]["titulos"].append("x" * 31)
        with self.assertRaises(g.Recusa) as e:
            g.valida(r)
        self.assertIn("31", str(e.exception))

    def test_descricao_com_91_caracteres(self):
        r = receita()
        r["anuncio"]["descricoes"].append("y" * 91)
        with self.assertRaises(g.Recusa):
            g.valida(r)

    def test_titulo_com_30_passa(self):
        # o limite e inclusivo: reprovar em 30 seria inventar regra.
        r = receita()
        r["anuncio"]["titulos"].append("z" * 30)
        g.valida(r)


class AContaEAVerba(unittest.TestCase):
    def test_customer_id_aceita_com_e_sem_traco(self):
        self.assertEqual(g.valida(receita(conta="123-456-7890")), "1234567890")
        self.assertEqual(g.valida(receita(conta="1234567890")), "1234567890")

    def test_customer_id_curto_recusa(self):
        with self.assertRaises(g.Recusa):
            g.valida(receita(conta="123-456-789"))

    def test_verba_zero_recusa(self):
        with self.assertRaises(g.Recusa) as e:
            g.valida(receita(campanha__verba_diaria=0))
        # a recusa tem que lembrar que o numero e em MICROS: errar a casa aqui
        # e gastar mil vezes mais.
        self.assertIn("micros", str(e.exception).lower())


class OQueOPayloadPrecisaTer(unittest.TestCase):
    def setUp(self):
        self.p = g.monta(receita(conta="1234567890"))
        self.ops = self.p["mutateOperations"]

    def _create(self, chave):
        for op in self.ops:
            if chave in op:
                return op[chave]["create"]
        return None

    def test_tudo_nasce_paused(self):
        for chave in ("campaignOperation", "adGroupOperation", "adGroupAdOperation"):
            self.assertEqual(self._create(chave)["status"], "PAUSED")

    def test_display_e_parceiros_desligados(self):
        # vem LIGADOS por padrao na interface, e e assim que Search vira Display
        # sem ninguem ter decidido isso.
        rede = self._create("campaignOperation")["networkSettings"]
        self.assertTrue(rede["targetGoogleSearch"])
        self.assertFalse(rede["targetContentNetwork"])
        self.assertFalse(rede["targetSearchNetwork"])
        self.assertFalse(rede["targetPartnerSearchNetwork"])

    def test_o_campo_da_ue_vai_junto(self):
        # obrigatorio na v25, e o erro de quando falta nao diz o nome do campo:
        # so aparece dentro de location.fieldPathElements.
        self.assertIn("containsEuPoliticalAdvertising",
                      self._create("campaignOperation"))

    def test_orcamento_nao_e_compartilhado(self):
        # compartilhado e uma campanha comendo a verba da outra sem aparecer em
        # lugar nenhum do relatorio.
        self.assertFalse(self._create("campaignBudgetOperation")["explicitlyShared"])

    def test_a_campanha_referencia_o_orcamento_por_id_temporario(self):
        orc = self._create("campaignBudgetOperation")["resourceName"]
        self.assertEqual(self._create("campaignOperation")["campaignBudget"], orc)
        self.assertIn("/-1", orc)

    def test_as_negativas_entram_como_negativas(self):
        criterios = [op["adGroupCriterionOperation"]["create"]
                     for op in self.ops if "adGroupCriterionOperation" in op]
        neg = [c for c in criterios if c.get("negative")]
        pos = [c for c in criterios if not c.get("negative")]
        self.assertEqual(len(neg), len(RECEITA["grupo"]["negativas"]))
        self.assertEqual(len(pos), len(RECEITA["grupo"]["palavras"]))

    def test_negativa_vai_em_broad(self):
        # negativa de frase deixa passar a variacao, e a variacao e justamente
        # o que voce nao quer comprar.
        for op in self.ops:
            c = op.get("adGroupCriterionOperation", {}).get("create", {})
            if c.get("negative"):
                self.assertEqual(c["keyword"]["matchType"], "BROAD")

    def test_e_uma_transacao_so(self):
        # atomica: ou entra tudo, ou nao entra nada. E por isso que aqui nao
        # existe orfao, nem o "olha o que ja foi criado" que a Meta precisa ter.
        self.assertEqual(list(self.p.keys()), ["mutateOperations"])


class OErroDoGoogleTemQueSerTraduzido(unittest.TestCase):
    """A mensagem de topo e sempre "Request contains an invalid argument.". O
    nome do campo mora no fim, em location.fieldPathElements -- que e
    exatamente o que some quando voce trunca o erro pra caber na tela."""

    BRUTO = ('HTTP 400: {"error": {"code": 400, "message": "Request contains an '
             'invalid argument.", "details": [{"errors": [{"errorCode": '
             '{"fieldError": "REQUIRED"}, "message": "The required field was not '
             'present.", "location": {"fieldPathElements": [{"fieldName": '
             '"operations"}, {"fieldName": "create"}, {"fieldName": '
             '"campaign_budget"}]}}]}]}}')

    def test_extrai_o_campo_que_faltou(self):
        linhas = g.explica_erro(self.BRUTO)
        self.assertEqual(len(linhas), 1)
        self.assertIn("campaign_budget", linhas[0])
        self.assertIn("REQUIRED", linhas[0])

    def test_erro_que_nao_e_json_nao_explode(self):
        linhas = g.explica_erro("timeout lendo o socket")
        self.assertEqual(len(linhas), 1)


class ORecusaAcontecemAntesDeFalarComOGoogle(unittest.TestCase):
    def test_a_receita_de_exemplo_do_repo_passa(self):
        # exemplo quebrado e pior que exemplo ausente, porque quem copia nao
        # desconfia. A CI roda o ensaio de toda receita por isso.
        self.assertEqual(g.valida(copy.deepcopy(RECEITA)), "0000000000")

    def test_o_exemplo_tem_negativa_de_verdade(self):
        self.assertGreaterEqual(len(RECEITA["grupo"]["negativas"]), 4)


if __name__ == "__main__":
    unittest.main()
