# Reforço de entradas nos workflows do Site — 03/11/2026

## Achado
A auditoria encontrou valores de inputs de disparo manual interpolados diretamente em campos `run` de workflows do Site, inclusive etapas de itch.io e YouTube que recebem Secrets. Esse padrão deixa texto do usuário sujeito a interpretação como shell quando o workflow é iniciado, em especial se o dispatch usar API.

## Corte
- Nos sete workflows afetados (`administrar-itch`, `administrar-youtube`, `enviar-itch`, `enviar-youtube`, `gravar-gameplay`, `gravar-prancheta`, `marketing-continuo`), os inputs passam primeiro por `env` e só então são usados como variáveis do shell entre aspas.
- Condições de confirmação, `if`, janelas, quantidade de pulsos, concorrência, agendas, limites, secrets e comandos funcionais existentes foram preservados. Nenhum workflow foi disparado.
- A barreira `tools/testes-workflows.py` passa a analisar o YAML de cada workflow e rejeitar novos usos diretos de `inputs.*` ou `github.event.inputs.*` dentro de `run`; inclui fixture negativa que garante que o detector acusa o padrão.
- A CI de `barreira-offline.yml` executa a regressão sem segredos, publicação, conta ou tráfego de API externa.

## Limites
Mover para env mitiga **injeção de shell por interpolação direta**. Não torna inputs confiáveis nem substitui validação no script Python/Node, limites de publicação e autorizações do titular. Não foi executado envio, vídeo, publicação ou edição de metadados reais. Não promete zero erros.

Reversão: reverter por PR normal após verificar CI, preservando históricos e políticas.
