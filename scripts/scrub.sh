#!/usr/bin/env bash
# Scrub: nada de segredo nem de dado de cliente entra neste repo.
#
# Rode ANTES de todo push. Sai 0 quando esta limpo, 1 quando achou algo.
#   ./scripts/scrub.sh
#
# Le a ARVORE DE TRABALHO. Pro historico inteiro: ./scripts/historico.sh
# As regras dos dois moram em scripts/regras.sh -- uma lista so, de proposito.
#
# A COISA QUE ESTE SCRIPT APRENDEU APANHANDO:
#
#   `git grep --untracked` nao e detalhe. SEM essa flag o scrub le so o que ja
#   esta rastreado, ou seja, aprova exatamente o arquivo NOVO que voce esta
#   prestes a adicionar -- que e o caso mais provavel de vazamento. Ele continua
#   respeitando o .gitignore, entao o cofre e os .env de verdade seguem de fora.

set -uo pipefail
cd "$(dirname "$0")/.."
. "$(dirname "$0")/regras.sh"

falhou=0

achou() {   # <titulo> <regex>
    local titulo="$1" regex="$2" hits="" linha conteudo trecho viva
    while IFS= read -r linha; do
        [ -n "$linha" ] || continue
        # tira `arquivo:numero:` para que o CAMINHO nao sirva de excecao:
        # `exemplos/acme.env` nao pode absolver o que esta dentro da linha.
        conteudo=${linha#*:}
        conteudo=${conteudo#*:}
        viva=0
        while IFS= read -r trecho; do
            [ -n "$trecho" ] || continue
            if ! permitido "$trecho"; then
                viva=1
                break
            fi
        done <<< "$(printf '%s\n' "$conteudo" | grep -oiE "$regex" 2>/dev/null)"
        if [ "$viva" -eq 1 ]; then
            hits="$hits$linha
"
        fi
    # A unica exclusao e o arquivo DE REGRAS, cujo conteudo e, por definicao,
    # os proprios padroes (a regra de caminho contem os caminhos). Este
    # script aqui NAO se exclui: as iscas dele tem o literal partido de
    # proposito (`'9.8' '7.6'`) justamente pra ele poder se ler.
    # O buraco que sobra: segredo colado dentro de regras.sh passaria. Se um
    # dia precisar, e nele que se olha primeiro.
    done <<< "$(git grep --untracked -nIiE "$regex" -- . ':!scripts/regras.sh' 2>/dev/null)"

    if [ -n "$hits" ]; then
        echo "FALHOU: $titulo"
        printf '%s' "$hits" | sed 's/^/    /'
        falhou=1
    else
        echo "ok: $titulo"
    fi
}

for regra in "${REGRAS[@]}"; do
    achou "${regra%%|*}" "${regra#*|}"
done
[ -n "$CLIENTES" ] || aviso_sem_lista

# --- autoteste -------------------------------------------------------------
# Planta uma isca de CADA classe num arquivo NOVO e exige que o scrub encontre
# todas. Sem isto, uma regressao no comando de busca transforma este script num
# carimbo de "limpo" que nao olhou nada -- e carimbo falso e pior que nao ter
# script. Uma isca so provaria uma regra so.
isca=".scrub-autoteste.tmp"
trap 'rm -f "$isca" "${isca2:-}"' EXIT INT TERM   # Ctrl-C nao pode deixar isca em disco
{
    printf 'EAA%s\n' 'AUTOTESTEDOSCRUBISTONAOEUMTOKEN123456'
    printf '# exemplo: act_%s\n' '778899112233'
    printf 'ip %s.%s\n' '9.8' '7.6'   # partido: senao a isca reprova o proprio scrub
} > "$isca"
faltou=""
for par in 'token:EAA[A-Za-z0-9]{20,}' 'conta:act_[0-9]{6,}' 'ip:\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'; do
    nome=${par%%:*}; rx=${par#*:}
    git grep --untracked -qIiE "$rx" -- "$isca" 2>/dev/null || faltou="$faltou $nome"
done
# a isca de conta esta numa linha com a palavra "exemplo" DE PROPOSITO: e o furo
# que existia, e ele nao pode voltar calado.
if [ -z "$faltou" ]; then
    echo "ok: autoteste (3 iscas, arquivo novo, uma delas na linha com \"exemplo\")"
else
    echo "FALHOU: autoteste -- o scrub NAO enxerga:$faltou. Nao confie nele."
    falhou=1
fi

# 4a isca, so quando a lista existe. A regra de nome de cliente e a UNICA que
# depende de um arquivo de fora, entao e a unica que pode ficar silenciosamente
# vazia: lista so com comentario, encoding errado, um "|" sobrando. Aqui ela e
# obrigada a disparar com o primeiro nome da propria lista.
if [ -n "$CLIENTES" ]; then
    primeiro=$(grep -vE '^[[:space:]]*(#|$)' "$LISTA" | head -1)
    isca2=".scrub-autoteste-cliente.tmp"
    printf '%s\n' "conta do $primeiro" > "$isca2"
    if git grep --untracked -qIiE "$CLIENTES" -- "$isca2" 2>/dev/null; then
        echo "ok: autoteste da lista (isca com o 1o nome do proprio arquivo)"
    else
        echo "FALHOU: autoteste -- a lista de clientes nao pega nem o proprio"
        echo "        primeiro nome dela. A regra esta morta; nao confie nela."
        falhou=1
    fi
    rm -f "$isca2"
fi
rm -f "$isca"

echo
if [ "$falhou" -eq 0 ]; then
    echo "limpo. pode empurrar."
else
    echo "NAO EMPURRE. Resolva os itens acima."
fi
exit "$falhou"
