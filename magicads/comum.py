# -*- coding: utf-8 -*-
"""Peças compartilhadas: segredo, saída limpa e HTTP com retry.

Tudo que fala com rede ou com segredo passa por aqui, pra que a regra de
"nenhum segredo sai em print" exista num lugar so e nao em cinco copias.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

META_VER = os.environ.get("MAGICADS_API_VERSION", "v25.0")
GRAPH = "https://graph.facebook.com/" + META_VER

SEGREDOS = []


def guarda_segredo(valor):
    """Registra um valor pra que `limpa()` nunca deixe ele sair em print."""
    if valor and len(valor) > 8 and valor not in SEGREDOS:
        SEGREDOS.append(valor)
    return valor


def env(nome, obrigatorio=False, segredo=True):
    v = os.environ.get(nome, "")
    if obrigatorio and not v:
        sys.exit("falta a variavel de ambiente %s" % nome)
    if segredo:
        guarda_segredo(v)
    return v


def limpa(s):
    """Ultima linha de defesa. Nenhum segredo sai daqui, nem dentro de erro."""
    s = str(s)
    for v in SEGREDOS:
        if v and v in s:
            s = s.replace(v, "<SEGREDO>")
    return s


def diz(*partes):
    print(limpa(" ".join(str(p) for p in partes)))


def http(url, data=None, headers=None, method=None, tentativas=3, form=None):
    """GET/POST com retry. API de anuncio cai sozinha o tempo todo.

    `form` manda como formulario (o que a Graph API espera em POST);
    `data` manda como JSON (o que Supabase e Google Ads esperam).
    """
    corpo = None
    cab = dict(headers or {})
    if form is not None:
        corpo = urllib.parse.urlencode(form).encode("utf-8")
        cab.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif data is not None:
        corpo = json.dumps(data).encode("utf-8")
        cab.setdefault("Content-Type", "application/json")

    for n in range(tentativas):
        try:
            req = urllib.request.Request(url, data=corpo, headers=cab, method=method)
            with urllib.request.urlopen(req, timeout=90) as r:
                bruto = r.read()
                return json.loads(bruto) if bruto else {}
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")[:400]
            if e.code in (429, 500, 503) and n < tentativas - 1:
                time.sleep(3 * (n + 1))
                continue
            raise RuntimeError(limpa("HTTP %s: %s" % (e.code, texto)))
        except RuntimeError:
            raise
        except Exception as e:
            if n < tentativas - 1:
                time.sleep(3 * (n + 1))
                continue
            raise RuntimeError(limpa(str(e)[:200]))


def erro_da_meta(texto):
    """Extrai (code, subcode, mensagem) de um erro da Graph pra decidir em cima."""
    try:
        inicio = texto.index("{")
        dado = json.loads(texto[inicio:]).get("error", {})
        return dado.get("code"), dado.get("error_subcode"), dado.get("error_user_title") \
            or dado.get("message")
    except Exception:
        return None, None, texto[:160]
