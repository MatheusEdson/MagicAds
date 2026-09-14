#!/usr/bin/env bash
# Scrub: nada de segredo nem de dado de cliente entra neste repo.
#
# Rode ANTES de todo push. Sai 0 quando esta limpo, 1 quando achou algo.
#   ./scripts/scrub.sh
#
# DUAS COISAS QUE ESTE SCRIPT APRENDEU APANHANDO:
#
# 1. `git grep --untracked` nao e detalhe. SEM essa flag o scrub le so o que ja
#    esta rastreado, ou seja, aprova exatamente o arquivo NOVO que voce esta
#    prestes a adicionar -- que e o caso mais provavel de vazamento. Ele continua
#    respeitando o .gitignore, entao o cofre e os .env de verdade seguem de fora.
#
# 2. A lista de excecoes vale pro TRECHO QUE CASOU, nunca pra linha inteira.
#    A versao anterior descartava a linha toda se ela contivesse "exemplo" em
#    qualquer posicao. Num repo escrito em portugues, inteiro construido em cima
#    de `exemplos/`, essa e a palavra mais comum que existe. Efeito medido:
#
#        # exemplo de configuracao
#        TOKEN=EAA<token de verdade>        ->  scrub dizia "limpo. pode empurrar."
#
#    Um token real passava por escrever "exemplo" na linha de cima. Agora a
#    excecao olha o trecho casado: `EAAxxxxxxxx` e placeholder, `EAA<real>` nao,
#    e o comentario em volta nao muda nada.

set -uo pipefail
cd "$(dirname "$0")/.."

falhou=0

permitido() {   # <trecho casado> -> 0 quando e placeholder declarado
    case "$1" in
        *xxxxxxxx*|*XXXXXXXX*)         return 0 ;;
        *00000000*)                    return 0 ;;
        *exemplo*|*EXEMPLO*|*Exemplo*) return 0 ;;
        *placeholder*|*PLACEHOLDER*)   return 0 ;;
        127.0.0.1|0.0.0.0|1.2.3.4)     return 0 ;;
        *1234567890*|*0123456789*)     return 0 ;;
    esac
    return 1
}

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
    done <<< "$(git grep --untracked -nIiE "$regex" -- . ':!scripts/scrub.sh' 2>/dev/null)"

    if [ -n "$hits" ]; then
        echo "FALHOU: $titulo"
        printf '%s' "$hits" | sed 's/^/    /'
        falhou=1
    else
        echo "ok: $titulo"
    fi
}

# 1. segredo
achou "token da Meta"            'EAA[A-Za-z0-9]{20,}'
# \b nas duas pontas: sem isso, qualquer SHA de git de 40 caracteres citado num
# CHANGELOG vira alarme falso, e alarme falso e como scrub morre.
achou "app secret / chave longa" '\b[a-f0-9]{32}\b'
achou "chave de servico"         '(service_role|secret_key|sk_live|refresh_token)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{20,}'
achou "chave privada"            'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'
achou "senha em DSN"             '(postgres|postgresql|mysql|mongodb)(\+srv)?://[^:/@[:space:]]+:[^@[:space:]]{4,}@'

# 2. identificador real
achou "conta de anuncio"         'act_[0-9]{6,}'
achou "id longo da Meta"         '\b[0-9]{15,17}\b'
achou "MCC do Google Ads"        '\b[0-9]{3}-[0-9]{3}-[0-9]{4}\b'
# O customer id do Google tambem circula CRU, sem hifen. A regra de telefone
# pegava por coincidencia de formato, e regra de telefone e a primeira a ser
# afrouxada no primeiro falso positivo chato.
achou "customer id cru"          '\b[0-9]{10}\b'

# 3. dado de cliente
# A lista de nomes NAO mora neste arquivo: num repo publico, escrever os nomes
# dos seus clientes dentro do scrub e vazar exatamente o que ele existe pra
# proteger. Ela mora num arquivo local, que esta no .gitignore.
LISTA="${MAGICADS_SCRUB_CLIENTES:-.scrub-clientes.local}"
if [ -f "$LISTA" ]; then
    CLIENTES=$(grep -vE '^[[:space:]]*(#|$)' "$LISTA" | tr '\n' '|' | sed 's/|$//')
    # \b nas duas pontas. Sem isso um nome curto vira alarme em palavra
    # comum: "Sabia" na lista reprovava a frase "Sabiam o que aconselhar" do
    # CHANGELOG. Alarme falso e como scrub morre -- primeiro irrita, depois
    # ninguem le a saida, e ai ele nao protege mais nada.
    [ -n "$CLIENTES" ] && CLIENTES="\\b($CLIENTES)\\b"
else
    CLIENTES=""
fi
if [ -n "$CLIENTES" ]; then
    achou "nome de cliente"      "$CLIENTES"
else
    # Dois motivos diferentes, e confundi-los custa caro: arquivo ausente e
    # esperado no primeiro clone; arquivo presente e sem nome nenhum quer dizer
    # que alguem editou e o esvaziou sem perceber.
    if [ -f "$LISTA" ]; then
        echo "AVISO: nome de cliente NAO checado. $LISTA existe mas nao tem"
        echo "       nome nenhum (so comentario ou linha em branco)."
    else
        echo "AVISO: nome de cliente NAO checado: $LISTA nao existe."
    fi
    echo "       Um nome por linha nesse arquivo. Ele e ignorado pelo git, entao"
    echo "       os nomes ficam na sua maquina. Regex generico nao sabe que"
    echo "       \"Acme Pneus\" e cliente seu -- so essa lista sabe."
fi
achou "telefone BR"              '\b(\+?55)?[[:space:]]?\(?[1-9]{2}\)?[[:space:]]?9?[0-9]{4}-?[0-9]{4}\b'

# 4. infra interna
# Classe inteira que faltava. Caminho de maquina e IP nao sao segredo, mas
# desenham onde voce opera, e e o tipo de linha que entra num comentario de
# debug e nunca mais sai.
achou "IP"                       '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'
achou "caminho de maquina"       '(/root/|/home/[a-z]|[A-Za-z]:\\\\Users\\\\|/var/www/)'

# 5. autoteste: planta uma isca de CADA classe num arquivo NOVO e exige que o
# scrub encontre todas. Sem isto, uma regressao no comando de busca transforma
# este script num carimbo de "limpo" que nao olhou nada -- e carimbo falso e
# pior que nao ter script. Uma isca so provaria uma regra so.
isca=".scrub-autoteste.tmp"
trap 'rm -f "$isca"' EXIT INT TERM   # Ctrl-C no meio nao pode deixar a isca em disco
{
    printf 'EAA%s\n' 'AUTOTESTEDOSCRUBISTONAOEUMTOKEN123456'
    printf '# exemplo: act_%s\n' '778899112233'
    printf 'ip %s\n' '203.0.113.7'
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
# vazia: lista so com comentarios, encoding errado, um "|" sobrando. Aqui ela e
# obrigada a disparar com o primeiro nome da propria lista.
if [ -n "$CLIENTES" ]; then
    primeiro=$(grep -vE '^[[:space:]]*(#|$)' "$LISTA" | head -1)
    isca2=".scrub-autoteste-cliente.tmp"
    trap 'rm -f "$isca" "$isca2"' EXIT INT TERM
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
