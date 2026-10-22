# Roteamento editorial e malha pública de marketing

**Estado:** 22/10/2026 · **Escopo:** canais já públicos/configurados · **Custo adicional:** R$ 0

## Problema corrigido

A automação tinha uma URL fixa do Prancheta no fim de toda mensagem. Assim, uma publicação de Ceifalume podia levar à página do outro jogo, e o estado factual antigo ainda descrevia Ceifalume inteiro como “em desenvolvimento”, apesar do lançamento público da versão 0.1 registrado na Base. A fila já guardava URLs por item, mas o postador não as aplicava.

A correção entrega uma malha de descoberta pequena e verificável: cada post escolhe uma página pública canônica do assunto; essa página reúne os links oficiais que já existem. Não há promessa de tráfego ou crescimento.

## Destinos fechados

| Chave | Destino | Quando usar |
|---|---|---|
| `prancheta` | `https://reboclbrank-max.github.io/site/jogos/prancheta/` | futebol, técnico, tática, manager ou Prancheta |
| `ceifalume` | `https://reboclbrank-max.github.io/site/jogos/ceifalume/` | fazenda, lanterna, colheita ou Ceifalume |
| `catalogo` | `https://reboclbrank-max.github.io/site/jogos.html` | assunto misto ou genérico sobre os jogos |
| `canais` | `https://reboclbrank-max.github.io/site/canais.html` | convite genérico para acompanhar a casa |

`tools/postador.py` aceita apenas essas URLs exatas. Texto produzido por motor não pode carregar URL; sugestão fora da lista cai no destino inferido de forma determinística. O hub `canais.html` lista somente URLs públicas já usadas nas páginas oficiais: jogos, itch.io, Bluesky, Mastodon, YouTube, Telegram, Discord, newsletter, blog, GitHub e e-mail público.

## Freios e privacidade

- Limite do texto editorial: **220** caracteres; texto + quebra + destino têm de caber em **300** caracteres, o menor adaptador textual. O código recusa uma composição que possa truncar o link final.
- Sem UTM, pixel, encurtador, redirecionamento, cookie novo, coleta de e-mail, telemetria individual ou atribuição causal.
- Sem nova conta, canal, segredo, permissão, publicação extra, follow, comentário em massa, tráfego fabricado ou aumento de cadência. Os oito ciclos e guardas existentes permanecem inalterados.
- A reserva factual tem o mesmo repertório de Prancheta e Ceifalume, alternado na lista. Se os dois últimos blocos bem formados do histórico forem do mesmo jogo, a seleção prioriza uma reserva existente do outro; histórico ausente/ambíguo não é convertido em dado inventado. A regra não mede preferência, alcance ou conversão e não cria postagem extra.
- Publicar em canal já configurado não autoriza recuperação de conta: o postador não abre caixa, segue link de senha, redefine credencial, renova/obtém token nem grava no cofre privado. Configuração ausente fica explícita e requer revisão humana.
- A mudança usa fatos lançados: Ceifalume 0.1 e Prancheta 0.1 estão disponíveis. Não anuncia versão futura nem atribui resultado a essa troca.

## Alternativas recusadas

1. **Manter uma única URL do Prancheta:** recusada porque desvia conteúdo de Ceifalume e não aproveita as páginas oficiais já existentes.
2. **Links com rastreador, parâmetros ou encurtador:** recusados por privacidade, dependência de terceiro e por não serem necessários para corrigir a rota.
3. **Aumentar posts, criar novos perfis ou interagir automaticamente para “gerar tráfego”:** recusado neste corte por anti-spam, termos, falta de identidade/conta operacional para novas plataformas e porque frequência não prova conversão.
4. **Deixar o motor escolher qualquer URL:** recusado por risco de link inesperado, phishing, fato errado e perda de reversibilidade.

## Verificação e rollback

`python3 tools/testes-autonomia-marketing.py` é offline e verifica: fatos de lançamento, rejeição de texto vencido, rota por assunto, lista fechada, link íntegro no limite do menor canal, fila factual equilibrada, guarda de diversidade, hub público, links internos e sitemap. Ele não abre rede, não lê segredo e não publica.

Para reverter, restaurar em um commit `tools/postador.py`, `posts/fila.json`, `canais.html`, os links HTML, `sitemap.xml` e esta documentação para o commit anterior. Isso não apaga post, conta, segredo, métrica, histórico, arquivo de usuário ou dado externo; apenas volta a lista/rotas locais.
