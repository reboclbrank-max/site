# Autonomia de marketing — R$ 0, mensurável e com freios

> Estado operacional em 2026-10-21. Esta política registra a autorização expressa do dono para a casa pesquisar, criar, administrar, publicar e melhorar o marketing continuamente nos canais já configurados. Ela preserva as regras de marca e a memória privada `reboclbrank-max/base` como fontes prioritárias.

## Missão

O marketing da Rebocl Brank pode operar de forma autônoma em torno dos jogos e apps existentes: descobrir oportunidades públicas, criar conteúdo, publicar nos canais já configurados, responder/interagir dentro dos limites do postador, acompanhar métricas e transformar resultado em melhoria da fila editorial.

A meta é melhorar alcance, testes, retenção e aprendizado com custo adicional de **R$ 0**. Não é uma promessa de crescimento, alcance garantido, postagem instantânea, acesso a toda plataforma ou funcionamento sem interrupção: APIs, redes sociais, Actions e motores gratuitos podem limitar, atrasar ou falhar.

## Medição de resultado por post — 2026-10-24

Antes desta data a casa publicava sem saber o que voltava: o registro diário repetia
`engajamento=NAO_OBSERVAVEL` e só contava seguidores e número de posts. Agora existe
`tools/metricas.py`, executado a cada ciclo depois da postagem:

- lê o **Bluesky pela API pública** (sem token, funciona mesmo sem credencial) e, quando o
  runtime tem `IG_TOKEN`/`IG_USER_ID`, lê apenas os contadores públicos do Instagram; sem
  eles a linha é `NAO_OBSERVAVEL`, nunca zero;
- separa **conteúdo dos jogos** de **comentário em post alheio** e mede o retorno de cada tipo;
- conta engajamento por post (curtidas + reposts + respostas), taxa de posts sem retorno e posts por seguidor;
- grava `posts/desempenho.md`, com o bloco do dia reescrito (não duplicado) e histórico preservado;
- fonte fora do ar entra como `NAO_OBSERVAVEL` — **nunca** vira zero;
- horário só é lido quando há amostra suficiente; com amostra pequena o arquivo diz, com todas as letras, que a diferença é ruído.

Primeira medição (24/10/2026, 300 posts próprios): conteúdo dos jogos n=80, média **2,06**,
11,2% sem retorno; comentário em post alheio n=220, média **0,85**, 42,3% sem retorno. A conta
tem 34 seguidores com 338 posts publicados. Esse contraste é o dado que faltava para decidir
o que continuar fazendo — e o que parar de fazer. Não é prova de alcance, download ou conversão.

### Interação: o que foi medido e o que isso obriga

O postador nunca leu notificação. A primeira leitura de thread (24/10/2026, 40 conversas)
mostrou três coisas separadas, que antes estavam misturadas:

| origem | conversas | respostas de terceiros | pendentes de resposta |
|---|---|---|---|
| conteúdo dos jogos (promo) | 0 | **0** | **0** |
| post alheio que a casa comentou | 38 | 40 | não se aplica |

Leitura honesta: **o conteúdo dos jogos não gerou nenhuma resposta** nesta amostra. O que
existe é o autor do post comentado agradecendo o comentário ("Thanks!", "Obrigado!") —
retribuição educada, não jogador pedindo atenção nem conversa sobre o jogo. Portanto:

- responder o agradecimento não é prioridade; **gerar assunto** é o problema real;
- o medidor passou a separar as duas coisas e a marcar `interacao=NAO_OBSERVAVEL` quando
  a thread não pode ser lida — nunca zero;
- enquanto o conteúdo não gerar resposta, "responder mais rápido" não resolve nada. A
  ordem correta é: mudar o que é postado, depois medir de novo.

### Horário: por que ainda não foi mudado

Os 8 ciclos caem às 00, 03, 06, 09, 12, 15, 18 e 21h de Brasília. Parece óbvio cortar a
madrugada, mas a conta é global e a amostra por hora (n≈2 a 28) está dentro do ruído — o
próprio medidor registra isso. Mudar cron agora seria escolher por intuição e chamar de
dado. Falta o insumo que a API pública não dá: de onde vêm os seguidores. Com isso na mão,
o horário passa a ter base. Até então: nada de mexer no cron e chamar de otimização.

### Interação: a casa passou a escutar — 2026-10-24

Duas correções, ambas tiradas de fato medido:

1. **Cadência desrespeitada.** `mestria.json` está escrito "3 devs/dia" desde 15/10/2026, mas
   o caçador tratava o número como "3 por ciclo". Com oito ciclos, eram até **24 comentários
   por dia** — e o medidor mostrou o preço: 0,85 de engajamento por comentário e 42% sem
   retorno nenhum. Agora o teto é lido do próprio `mestria.json` e vale **por dia**; ciclo
   posterior no mesmo dia devolve `PULADO` com o motivo, que é comportamento saudável.
2. **A casa falava e não ouvia.** Nenhuma linha do postador lia notificação. Agora existe o
   canal `respondedor de conversa`: lê as notificações do Bluesky e responde **apenas** quando
   alguém respondeu a um post da casa — uma vez por conversa, dentro da mesma cota diária,
   sem link, sem promessa de data, passando pelo freio `texto_gerado_seguro()`.

O que fica **de fora**, de propósito: o agradecimento do autor de post alheio ("Thanks!",
"Obrigado!") não é respondido. Medido em 24/10/2026, eram 40 de 40 notificações e nenhuma
pedia resposta — responder aquilo é ruído, não conversa.

### Placar de metas — 2026-10-24

`tools/metricas.py` grava também `posts/placar-metas.md`: cada meta aprovada em 15/10 ao lado
do valor observado, quanto falta, dias restantes e quanto seria necessário por dia. Meta sem
leitura automática aparece como `SEM_LEITURA` — não como zero, não como "quase lá". Hoje só
Bluesky tem leitura; YouTube e itch seguem sem API e isso está escrito na tabela, não escondido.

## Fonte de verdade e operação atual

| Componente | Responsabilidade |
|---|---|
| `tools/postador.py` | Escolhe tema, gera/valida texto, usa fila de reserva, publica nos canais configurados, procura oportunidades públicas, registra lições e métricas. |
| `posts/fila.json` | Reserva editorial factual quando o motor estiver indisponível ou a sugestão não passar no freio. Cada item traz somente um destino público da lista fechada do postador. |
| `canais.html` e páginas `jogos/*` | Malha pública de descoberta: páginas canônicas dos jogos levam aos canais oficiais já existentes, sem rastreador, encurtador, conta ou mensagem nova. |
| `posts/aulas.md`, `posts/descobertas.md`, `posts/interacoes.md`, `posts/progresso-metas.md` | Memória pública sanitizada de estudo, oportunidades, deduplicação e resultados. |
| `posts/mestria.json` e `posts/metas.json` | Cadência e metas já aprovadas; não aumentar por impulso. |
| `.github/workflows/postagem-diaria.yml` | Executa os 8 ciclos planejados no minuto 17 (fora do congestionamento do início da hora), serializa somente os ciclos de publicação e commita apenas estado público em `posts/`. O pulso técnico já existente fica em grupo próprio e só pode solicitar o mesmo ciclo se uma lacuna for confirmada. |
| `reboclbrank-max/agente` (privado) | Complementa a operação com piloto, menções, métricas, estudo e propostas; respeita a cota gratuita já calculada. |

Antes de mexer em discurso, fatos, ativos, públicos ou metas, consulte na Base: `empresa/ficha-da-marca.md`, `empresa/atlas-marketing.md`, `projetos/01-ceifalume/marketing/PLANO-MARKETING.md` e registros de decisão pertinentes.

## Autonomia permitida

Sem novo comando por post, a casa pode:

- rodar os horários já configurados e publicar apenas nos canais com conta/segredo previamente configurados;
- escolher temas da fila, criar variações em português/inglês quando o próprio canal exigir e usar somente os destinos oficiais fechados em `tools/postador.py`;
- pesquisar oportunidades e fazer interação limitada, genuína, sem link e com deduplicação onde o postador já suporta isso;
- registrar métricas públicas agregadas, lições e hipóteses de melhoria;
- usar uma fila de reserva caso motor/API falhe;
- propor ferramenta, experimento ou melhoria pequena e promover apenas aquilo que passou por testes, registro e rollback.

A autonomia começa na estratégia e execução cotidiana; ela não permite criar contas novas, comprar anúncios, contratar serviço, habilitar cobrança, inventar produto/fato, coletar dados pessoais ou burlar APIs/limites.

## Guardas obrigatórios

1. **Marca e fatos:** usar somente informações confirmadas na Base e nos fatos/fila do postador. **Ceifalume 0.1 e Prancheta 0.1 estão lançados**; uma versão futura sem data não autoriza chamar o jogo inteiro de “em breve” ou “em desenvolvimento”. Dúvida factual vira fila segura ou rascunho, não alegação pública.
2. **Texto externo:** saída de motor é sugestão não confiável. `texto_gerado_seguro()` rejeita URL inesperada, possível segredo, prompt injection, duplicata, excesso de hashtags e promessas contraditórias antes de qualquer publicação; a fila é o fallback.
3. **Mídia resiliente:** antes de publicar, o postador espera o container da Meta ficar pronto; se a URL da arte primária for recusada, `cria_container_com_reserva()` tenta uma única arte pública estável do próprio repositório. Se nenhum container ficar pronto, não publica nada; a falha fica para o próximo ciclo. Isso evita o 400 de mídia prematura/indisponível, duplicata e mudança de cadência.
4. **Cadência e anti-spam:** preservar janelas, máximo por canal, deduplicação e travas existentes. Os oito horários continuam iguais. O pulso técnico não publica diretamente: depois de quatro horas sem ciclo registrado, sem outra execução em curso e somente com fotografia de API/log bem formada, ele pode solicitar o workflow já existente. Qualquer incerteza não despacha; uma trava local de duas horas impede que cron atrasado e retaguarda gerem dois ciclos próximos. Resultados `PULADO` por janela/trava são comportamento saudável, não erro a “consertar” aumentando frequência.
5. **Cobertura honesta:** `OK` significa somente que a operação técnica daquele canal retornou aceitação; `PULADO` é guarda normal de janela/cadência; `INDISPONIVEL` é configuração de publicação ausente no runtime; `FALHOU` é tentativa que retornou erro. Nenhum desses rótulos prova exibição, entrega independente, alcance, engajamento, download, conversão ou satisfação. Não manter lista estática de canais “verdes”: a classificação vem do ciclo que efetivamente rodou.
6. **Métricas:** `posts/progresso-metas.md` registra apenas sinais externos que a leitura atual consegue observar. `NAO_OBSERVAVEL` e `NAO_CONFIGURADO` nunca significam zero, mau resultado ou ausência de público; `VARIACAO_OBSERVADA` não atribui causa aos posts. Alcance, engajamento, downloads e conversão permanecem lacunas até existir leitura independente autorizada. `estado-ia.json` conserva histórico próprio e só pode ser usado com seu carimbo de atualização, não como painel atual por padrão.
7. **Segredos:** credenciais ficam somente em Secrets/cofre já autorizado. Nunca entram em conteúdo, URL, commit, log, issue ou documentação. Não rotacionar/revogar nem criar chaves por iniciativa própria.
8. **Legalidade e plataformas:** não burlar login, CAPTCHA, rate limit, paywall, termos, robots ou controles de conta. Não publicar material de terceiros sem licença/uso permitido.
9. **Privacidade:** não publicar conversa, dados pessoais, memória privada, identificadores de usuário ou métricas individuais. O repositório público só recebe estado agregado e sanitizado.
10. **Reversibilidade:** mudanças em código, cadência, canais, dependências ou fatos exigem teste e documentação. O roteamento editorial aceita uma lista pequena de URLs canônicas, sem UTM/encurtador/redirecionamento, e pode voltar à lista anterior num único commit. Segredos, permissões, contas, infraestrutura, gastos e ações irreversíveis exigem revisão humana explícita.

## Porta de qualidade e melhoria contínua

`tools/testes-autonomia-marketing.py` roda antes de cada ciclo de postagem. É um teste offline: não chama rede, não carrega segredo e não publica. Ele prova as propriedades básicas do freio de texto, da troca segura de arte de Instagram, das decisões fail-closed da retaguarda, da trava contra ciclos próximos, da presença desta política e do pin da Action de checkout.

O ciclo correto é: **medir → formular hipótese → mudança pequena → teste → publicar/reverter → medir de novo**. Medição ausente ou ruim não autoriza spam; ela orienta melhoria de tema, formato, horário ou fila dentro dos limites existentes.

## Roteamento editorial e malha pública

- O postador não aceita URLs vindas do motor nem de texto livre. `DESTINOS_EDITORIAIS` fixa as páginas públicas do Prancheta, Ceifalume, catálogo e hub de canais; URL ausente ou fora da lista cai numa rota local escolhida pelo assunto, nunca em um endereço externo arbitrário.
- O limite editorial é 220 caracteres e a mensagem completa precisa caber no menor canal textual (300 caracteres). Assim o adaptador não corta o link no fim da publicação.
- Tema exclusivo de futebol/Prancheta vai para a página do Prancheta; tema exclusivo de fazenda/Ceifalume vai para a página do Ceifalume; tema misto vai para o catálogo; convite genérico para acompanhar a casa pode ir ao hub `canais.html`. As páginas de destino expõem somente links públicos já confirmados.
- A malha não mede clique, não atribui causa, não adiciona post, seguidor, interação, canal, conta, segredo, redirecionamento, pixel ou custo. Ela melhora coerência e descoberta; não prova alcance, conversão, tráfego humano ou crescimento.
- Contrato, alternativas recusadas, rollback e testes estão em `MARKETING-ROTEAMENTO.md`.

## Custo e continuidade

Esta política não adiciona execução agendada, canal, conta, serviço pago ou frequência de publicação: a retaguarda aproveita somente o pulso e o workflow já existentes e pode, no máximo, recuperar uma lacuna confirmada. Para preservar R$ 0, qualquer ideia que necessite cartão, plano, cobrança, compra de anúncio, API paga ou aumento não analisado de minutos fica fora da promoção autônoma.

A próxima pessoa/agente deve atualizar este arquivo, o README, a continuidade da Base e o registro de decisão quando alterar esse contrato operacional. Nunca registrar valores de credenciais.
