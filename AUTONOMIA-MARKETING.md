# Autonomia de marketing — R$ 0, mensurável e com freios

> Estado operacional em 2026-10-17. Esta política registra a autorização expressa do dono para a casa pesquisar, criar, administrar, publicar e melhorar o marketing continuamente nos canais já configurados. Ela preserva as regras de marca e a memória privada `reboclbrank-max/base` como fontes prioritárias.

## Missão

O marketing da Rebocl Brank pode operar de forma autônoma em torno dos jogos e apps existentes: descobrir oportunidades públicas, criar conteúdo, publicar nos canais já configurados, responder/interagir dentro dos limites do postador, acompanhar métricas e transformar resultado em melhoria da fila editorial.

A meta é melhorar alcance, testes, retenção e aprendizado com custo adicional de **R$ 0**. Não é uma promessa de crescimento, alcance garantido, postagem instantânea, acesso a toda plataforma ou funcionamento sem interrupção: APIs, redes sociais, Actions e motores gratuitos podem limitar, atrasar ou falhar.

## Fonte de verdade e operação atual

| Componente | Responsabilidade |
|---|---|
| `tools/postador.py` | Escolhe tema, gera/valida texto, usa fila de reserva, publica nos canais configurados, procura oportunidades públicas, registra lições e métricas. |
| `posts/fila.json` | Reserva editorial factual quando o motor estiver indisponível ou a sugestão não passar no freio. |
| `posts/aulas.md`, `posts/descobertas.md`, `posts/interacoes.md`, `posts/progresso-metas.md` | Memória pública sanitizada de estudo, oportunidades, deduplicação e resultados. |
| `posts/mestria.json` e `posts/metas.json` | Cadência e metas já aprovadas; não aumentar por impulso. |
| `.github/workflows/postagem-diaria.yml` | Executa 8 ciclos diários no minuto 17 (fora do congestionamento do início da hora), com concorrência única e commita somente o estado público em `posts/`. |
| `reboclbrank-max/agente` (privado) | Complementa a operação com piloto, menções, métricas, estudo e propostas; respeita a cota gratuita já calculada. |

Antes de mexer em discurso, fatos, ativos, públicos ou metas, consulte na Base: `empresa/ficha-da-marca.md`, `empresa/atlas-marketing.md`, `projetos/01-ceifalume/marketing/PLANO-MARKETING.md` e registros de decisão pertinentes.

## Autonomia permitida

Sem novo comando por post, a casa pode:

- rodar os horários já configurados e publicar apenas nos canais com conta/segredo previamente configurados;
- escolher temas da fila, criar variações em português/inglês quando o próprio canal exigir e usar links oficiais já definidos;
- pesquisar oportunidades e fazer interação limitada, genuína, sem link e com deduplicação onde o postador já suporta isso;
- registrar métricas públicas agregadas, lições e hipóteses de melhoria;
- usar uma fila de reserva caso motor/API falhe;
- propor ferramenta, experimento ou melhoria pequena e promover apenas aquilo que passou por testes, registro e rollback.

A autonomia começa na estratégia e execução cotidiana; ela não permite criar contas novas, comprar anúncios, contratar serviço, habilitar cobrança, inventar produto/fato, coletar dados pessoais ou burlar APIs/limites.

## Guardas obrigatórios

1. **Marca e fatos:** usar somente informações confirmadas na Base e nos fatos/fila do postador. Ceifalume permanece “em desenvolvimento”; Prancheta é o jogo já disponível. Dúvida factual vira fila segura ou rascunho, não alegação pública.
2. **Texto externo:** saída de motor é sugestão não confiável. `texto_gerado_seguro()` rejeita URL inesperada, possível segredo, prompt injection, duplicata, excesso de hashtags e promessas contraditórias antes de qualquer publicação; a fila é o fallback.
3. **Mídia resiliente:** antes de publicar, o postador espera o container da Meta ficar pronto; se a URL da arte primária for recusada, `cria_container_com_reserva()` tenta uma única arte pública estável do próprio repositório. Se nenhum container ficar pronto, não publica nada; a falha fica para o próximo ciclo. Isso evita o 400 de mídia prematura/indisponível, duplicata e mudança de cadência.
4. **Cadência e anti-spam:** preservar janelas, máximo por canal, deduplicação e travas existentes. Resultados `PULADO` por janela/trava são comportamento saudável, não erro a “consertar” aumentando frequência.
5. **Segredos:** credenciais ficam somente em Secrets/cofre já autorizado. Nunca entram em conteúdo, URL, commit, log, issue ou documentação. Não rotacionar/revogar nem criar chaves por iniciativa própria.
6. **Legalidade e plataformas:** não burlar login, CAPTCHA, rate limit, paywall, termos, robots ou controles de conta. Não publicar material de terceiros sem licença/uso permitido.
7. **Privacidade:** não publicar conversa, dados pessoais, memória privada, identificadores de usuário ou métricas individuais. O repositório público só recebe estado agregado e sanitizado.
8. **Reversibilidade:** mudanças em código, cadência, canais, dependências ou fatos exigem teste e documentação. Segredos, permissões, contas, infraestrutura, gastos e ações irreversíveis exigem revisão humana explícita.

## Porta de qualidade e melhoria contínua

`tools/testes-autonomia-marketing.py` roda antes de cada ciclo de postagem. É um teste offline: não chama rede, não carrega segredo e não publica. Ele prova as propriedades básicas do freio de texto, da troca segura de arte de Instagram, a presença desta política e o pin da Action de checkout.

O ciclo correto é: **medir → formular hipótese → mudança pequena → teste → publicar/reverter → medir de novo**. Métrica ruim não autoriza spam; ela orienta melhoria de tema, formato, horário ou fila dentro dos limites existentes.

## Custo e continuidade

Esta política não adiciona execução agendada nem serviço pago: aproveita o postador e a cadência já existentes. Para preservar R$ 0, qualquer ideia que necessite cartão, plano, cobrança, compra de anúncio, API paga ou aumento não analisado de minutos fica fora da promoção autônoma.

A próxima pessoa/agente deve atualizar este arquivo, o README, a continuidade da Base e o registro de decisão quando alterar esse contrato operacional. Nunca registrar valores de credenciais.
