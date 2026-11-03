# Imutabilidade de Actions — 2026-11-03

## Motivo
A auditoria da Rebocl Brank encontrou referências a tags móveis de `actions/setup-node@v4` e `actions/upload-artifact@v4` em workflows de captura e de apoio do Site. A referência móvel permite que uma execução futura use código diferente do que foi revisado, mesmo sem alteração do YAML.

## Mudança isolada
- Fixadas as referências de `setup-node` ao commit oficial de `v4`: `49933ea5288caeca8642d1e84afbd3f7d6820020`.
- Fixadas as referências de `upload-artifact` ao commit oficial de `v4`: `ea165f8d65b6e75b540449e92b4886f43607fa02`.
- `tools/testes-workflows.py` agora reprova novas `uses:` externas sem commit SHA de 40 dígitos; ações locais `./` e imagens `docker://` fixadas por digest são exceções explícitas.
- A barreira `.github/workflows/barreira-offline.yml` já executa essa suíte em toda PR que modifica workflows ou ferramentas. Nenhuma cadência, permissão, segredo, gatilho, confirmação de publicação, código de jogo ou rotina de marketing foi modificada.

## Validação e riscos restantes
A mudança deve entrar por PR, após o check remoto `Barreira offline de operação` aprovado no SHA da proposta. Essa barreira valida referências, YAML, blocos de shell, concorrência e outros contratos sem executar publicação. Os workflows de captura de gameplay continuam com validação própria quando forem executados naturalmente. Nada aqui prova funcionamento externo, entrega, disponibilidade, desempenho nem segurança absoluta da cadeia de suprimentos.

## Reversão
Reverter a PR pelo fluxo normal, após revisão. Não alterar estados, registros de postagem ou arquivos de mídia para executar a reversão.
