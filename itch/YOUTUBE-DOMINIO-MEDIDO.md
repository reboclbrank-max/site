# O que eu domino no YouTube — medido, não prometido

Medição: 26/10/2026 · runs `40411712196` (capacidades) e `40411813385` (limpeza).
Conta: **Rebocl Brank** · 160 vídeos antes da limpeza · 24 inscritos · 5.414 views.

## Escopo concedido

`https://www.googleapis.com/auth/youtube` — o **amplo**: cobre ler, escrever metadados,
organizar playlists, trocar miniatura e **enviar vídeo**. (Não é `youtube.readonly`.)

## Funciona de servidor (com HTTP medido)

| ação | HTTP | observação |
|---|---|---|
| renovar token pelo refresh_token | 200 | sem intervenção do dono |
| ler canal e estatísticas | 200 | 24 inscritos · 160 vídeos · 5.414 views |
| buscar vídeos do próprio canal | 200 | |
| `videos.list` (detalhe + privacidade) | 200 | |
| **editar título/descrição/tags** (`videos.update`) | **200** | regravei o mesmo texto, nada mudou na tela |
| criar playlist privada (`playlists.insert`) | 200 | apagada na mesma execução (204) |
| **trocar miniatura** (`thumbnails.set`) | **200** | 16.576 bytes regravados em vídeo público |
| **iniciar upload** (`videos.insert` resumable) | **200** | sessão aberta e abandonada: **nenhum byte enviado, nenhum vídeo criado** |
| apagar vídeo (`videos.delete`) | 204 | 4 vídeos de sonda meus apagados do canal |

## Não funciona com o escopo atual (403 insufficientPermissions)

| ação | HTTP | o que exigiria |
|---|---|---|
| ler/moderar comentários (`commentThreads`) | 403 | escopo `youtube.force-ssl` → novo consentimento do dono (2 min) |
| legendas (`captions`) | 403 | idem |

## A diferença em relação ao itch

No itch, conteúdo (devlog, texto de página) é **impossível** de servidor: o itch não tem
endpoint e a Cloudflare barra o meu IP antes do formulário.

No YouTube é o contrário: **título, descrição, tags, playlist, miniatura e envio de vídeo
são todos por API**, sem navegador e sem clique. A única pendência é comentário/legenda,
e ela se resolve com um consentimento novo — não com trabalho manual no painel.

## Regra da casa ainda em vigor

`enviar-youtube.yml` **não tem cron** e exige palavra de confirmação: publicar vídeo só com
pedido explícito. A janela de horário (`posts/calendario.json`, 09h-22h) vale para texto;
para vídeo, o gatilho continua sendo decisão explícita.
