#!/usr/bin/env bash
# entrar-no-main.sh — põe o commit local no main sem depender de rebase limpo.
#
# POR QUE EXISTE (medido em 31/10/2026): sete workflows escrevem no main, cada um com o seu
# laço "rebase e tenta de novo". Rebase é a ferramenta errada quando os dois lados REGERAM o
# mesmo arquivo: marketing.html, publicacoes.json, posts/log.md saem diferentes a cada run, e o
# rebase para em conflito todas as vezes. Foi assim que o ciclo das 21h ficou vermelho duas
# vezes seguidas (runs 41128039668 e 41128399021 — "3 tentativas e o ciclo não entrou no main"),
# com o log do ciclo preso dentro do run.
#
# O que ele faz, em ordem, por tentativa:
#   1. fetch origin main;
#   2. tenta rebase — caminho barato, quando não há conflito;
#   3. se o rebase parar em conflito, desfaz e faz MERGE. Conflito em arquivo GERADO é resolvido
#      pelo próprio gerador: fica a versão do main e, logo depois, $GERAR reescreve o arquivo a
#      partir da fonte (posts/, docs/). Arquivo gerado não tem informação própria — quem tem é a
#      fonte dele;
#   4. conflito em arquivo que NÃO é gerado (código, workflow, documento escrito à mão) NÃO é
#      resolvido no chute: o merge é desfeito e o script sai com 1 dizendo qual arquivo é.
#
# Uso:
#   tools/entrar-no-main.sh "motivo do commit"
# Variáveis:
#   GERAR="python3 tools/melhorias.py && python3 tools/publicacoes.py"   (opcional)
#   TENTATIVAS=6                                                         (opcional)
set -uo pipefail

MOTIVO="${1:-artefatos da casa}"
TENTATIVAS="${TENTATIVAS:-6}"
: "${GERAR:=}"

# Só estes caminhos podem ser resolvidos automaticamente, porque são SAÍDA de gerador.
GERADOS='^(marketing\.html|melhorias\.html|publicacoes\.html|posts/publicacoes\.json|docs/PUBLICACOES\.md)$'
DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "  [$MOTIVO] $*"; }

# O motivo do push recusado precisa APARECER. Sem isto o script dizia "push recusado" seis
# vezes e escondia a causa (credencial, proteção de branch, rede) — que é o mesmo falso-verde
# que a rodada 122 caçou no `| tee`. Não reproduzimos stderr: pode conter URL autenticada.
empurrar() {
  local saida
  saida=$(git push -q origin HEAD:main 2>&1) && return 0
  local motivo="transporte/servidor"
  if printf '%s' "$saida" | grep -Eqi 'authentication|permission|denied|403|401'; then motivo="autenticação/permissão";
  elif printf '%s' "$saida" | grep -Eqi 'non-fast-forward|fetch first|rejected'; then motivo="concorrência/rejeição"; fi
  log "push recusado: $motivo; detalhes sensíveis omitidos"
  return 1
}

# DEFEITO CONHECIDO DA CASA: sem user.name/user.email o `git commit` morre com "empty ident
# name" — e aqui isso apareceria como "push recusado", escondendo a causa. Se o workflow não
# configurou identidade, o script configura uma, em vez de falhar por motivo invisível.
[ -n "$(git config user.name || true)" ] || git config user.name "casa-rebocl"
[ -n "$(git config user.email || true)" ] || git config user.email "casa@rebocl.local"

regerar() {
  [ -z "$GERAR" ] && return 0
  log "regerando saídas"
  bash -c "$GERAR" >/dev/null 2>&1 || { log "gerador falhou; não publico como sucesso"; return 1; }
  git add -u >/dev/null 2>&1
}

commit_do_merge() {
  if git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
    git commit -q --no-edit >/dev/null 2>&1
  elif ! git diff --cached --quiet; then
    git commit -q -m "$MOTIVO: estado conciliado" >/dev/null 2>&1
  else
    return 0
  fi
}

resolver_conflitos() {
  local sobra="" f
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if printf '%s' "$f" | grep -Eq "$GERADOS" && [ -n "$GERAR" ]; then
      git checkout --theirs -- "$f" >/dev/null 2>&1 && git add -- "$f" || return 1
      log "saída regenerável: $f; gerador obrigatório antes do push"
    elif python3 "$DIR_SCRIPT/conciliar-estado.py" "$f" >/dev/null 2>&1; then
      git add -- "$f" || return 1
      log "estado conciliado sem descartar alterações: $f"
    else
      sobra="$sobra $f"
    fi
  done < <(git diff --name-only --diff-filter=U)
  SOBRA="$sobra"
  [ -z "$sobra" ]
}

SOBRA=""
for n in $(seq 1 "$TENTATIVAS"); do
  if ! git fetch -q origin main; then
    log "fetch falhou (tentativa $n)"; sleep $((n * 3)); continue
  fi

  # 1. caminho barato: rebase sem conflito
  if git rebase -q origin/main >/dev/null 2>&1; then
    regerar || { git merge --abort >/dev/null 2>&1 || true; exit 1; }
    git commit -q --amend --no-edit >/dev/null 2>&1 || exit 1
    if empurrar; then
      log "no main por rebase (tentativa $n)"; exit 0
    fi
    log "push recusado depois do rebase (tentativa $n)"
    sleep $((n * 3)); continue
  fi
  git rebase --abort >/dev/null 2>&1 || true

  # 2. merge: resolve gerado, reescreve pela fonte, recusa o resto
  if git merge --no-edit origin/main >/dev/null 2>&1; then
    regerar || { git merge --abort >/dev/null 2>&1 || true; exit 1; }
    commit_do_merge || { git merge --abort >/dev/null 2>&1 || true; exit 1; }
    if empurrar; then
      log "no main por merge (tentativa $n)"; exit 0
    fi
    log "push recusado depois do merge (tentativa $n)"
  elif resolver_conflitos; then
    regerar || { git merge --abort >/dev/null 2>&1 || true; exit 1; }
    commit_do_merge || { git merge --abort >/dev/null 2>&1 || true; exit 1; }
    if empurrar; then
      log "no main por merge resolvido nos gerados (tentativa $n)"; exit 0
    fi
    log "push recusado depois do merge resolvido (tentativa $n)"
  else
    log "conflito em arquivo que NÃO é gerado:$SOBRA — não sobrescrevo; desfaço o merge"
    git merge --abort >/dev/null 2>&1 || true
    exit 1
  fi
  sleep $((n * 3))
done

log "não entrou no main em $TENTATIVAS tentativas"
exit 1
