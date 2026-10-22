# Autonomia de marketing — R$ 0, mensurável e com freios

> Estado operacional em 2026-10-22. Esta política registra a autorização expressa do dono para a casa pesquisar, criar, administrar, publicar e melhorar o marketing continuamente nos canais já configurados. Ela preserva as regras de marca e a memória privada `reboclbrank-max/base` como fontes prioritárias.

## Missão

O marketing da Rebocl Brank pode operar de forma autônoma em torno dos jogos e apps existentes: descobrir oportunidades públicas, criar conteúdo, publicar nos canais já configurados, responder/interagir dentro dos limites do postador, acompanhar métricas e transformar resultado em melhoria da fila editorial.

A meta é melhorar alcance, testes, retenção e aprendizado com custo adicional de **R$ 0**. Não é uma promessa de crescimento, alcance garantido, postagem instantânea, acesso a toda plataforma ou funcionamento sem interrupção: APIs, redes sociais, Actions e motores gratuitos podem limitar, atrasar ou falhar.

## Fonte de verdade e operação atual

| Componente | Responsabilidade |
|---|---|
| `tools/postador.py` | Escolhe tema, gera/valida texto, usa fila de reserva, publica nos canais configurados, procura oportunidades públicas, registra lições e métricas. |
| `posts/fila.json` | Reserva editorial factual quando o motor estiver indisponível ou a sugestão não passar no freio. Cada item traz somente um destino público da lista fechada do postador. |
| `canais.html` e páginas `jogos/*` | Malha pública de descoberta: páginas canônicas dos jogos levam aos canais oficiais já existentes, sem rastreador, encurtador, conta ou mensagem nova. |
| `posts/aulas.md`, `posts/descobertas.md`, `posts/interacoes.md`, `posts/interacoes-diarias.json`, `posts/progresso-metas.md` | Memória pública sanitizada de estudo, oportunidades, deduplicação, cota agregada de interação e resultados. |
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
2. **Texto externo:** saída de motor é sugestão não confiável. `texto_gerado_seguro()` rejeita URL inesperada, possível segredo, prompt injection, duplicata, excesso de hashtags, promessa contraditória e alegação não confirmada de plataforma, modo, preço comercial/promoção, pré-lançamento ou prova social. A barreira não alega provar toda frase; na dúvida, a fila factual fechada é o fallback.
3. **Mídia resiliente:** antes de publicar, o postador espera o container da Meta ficar pronto; se a URL da arte primária for recusada, `cria_container_com_reserva()` tenta uma única arte pública estável do próprio repositório. Se nenhum container ficar pronto, não publica nada; a falha fica para o próximo ciclo. Isso evita o 400 de mídia prematura/indisponível, duplicata e mudança de cadência.
4. **Cadência, anti-spam e diversidade:** preservar janelas, máximo por canal, deduplicação e travas existentes. Os oito horários continuam iguais. O pulso técnico não publica diretamente: depois de quatro horas sem ciclo registrado, sem outra execução em curso e somente com fotografia de API/log bem formada, ele pode solicitar o workflow já existente. Qualquer incerteza não despacha; uma trava local de duas horas impede que cron atrasado e retaguarda gerem dois ciclos próximos. A fila factual alterna repertório dos dois jogos e, após dois destinos seguidos do mesmo jogo, só prioriza a reserva do outro quando ela já existe na lista fechada; isso não cria conteúdo, post, canal ou frequência. O caçador do Bluesky reserva no máximo três tentativas por dia UTC antes de enviar; falha/estado diário ambíguo não abre compensação nem rajada. Resultados `PULADO` por janela/trava/cota são comportamento saudável, não erro a “consertar” aumentando frequência.
5. **Cobertura honesta:** `OK` significa somente que a operação técnica daquele canal retornou aceitação; `PULADO` é guarda normal de janela/cadência; `INDISPONIVEL` é configuração de publicação ausente no runtime; `FALHOU` é tentativa que retornou erro. Nenhum desses rótulos prova exibição, entrega independente, alcance, engajamento, download, conversão ou satisfação. Não manter lista estática de canais “verdes”: a classificação vem do ciclo que efetivamente rodou.
6. **Métricas:** `posts/progresso-metas.md` registra apenas sinais externos que a leitura atual consegue observar. `NAO_OBSERVAVEL` e `NAO_CONFIGURADO` nunca significam zero, mau resultado ou ausência de público; `VARIACAO_OBSERVADA` não atribui causa aos posts. Alcance, engajamento, downloads e conversão permanecem lacunas até existir leitura independente autorizada. `estado-ia.json` conserva histórico próprio e só pode ser usado com seu carimbo de atualização, não como painel atual por padrão.
7. **Segredos e contas:** credenciais ficam somente em Secrets/cofre já autorizado. Nunca entram em conteúdo, URL, commit, log, issue ou documentação. O postador não lê caixa de recuperação, não redefine senha, não renova nem obtém token e não escreve no cofre privado; recuperação de conta/credencial exige revisão humana explícita. Não rotacionar/revogar nem criar chaves por iniciativa própria.
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
