# Estado concorrente e resultado verificável

Pedido do dono: fechar o ciclo sem concluir apenas cortes intermediários. O helper deixou de chamar todo posts/*.json/md de saída descartável. Estados usam merge de três vias: campos independentes, tarefas por ID, listas/históricos append-only. Conflito incompatível permanece explícito e preserva commits; não escolhe arbitrariamente uma tarefa e não repete ação externa. Só saídas conhecidas podem ser regeneradas, com GERAR configurado e sucesso obrigatório. Sem gerador, não descarta versão.

Gerador falho, commit falho, ação falha e persistência falha não são sucesso. Loop usa o helper comum de entrada no main e encerra o bloco com erro após tentativa de persistir diagnóstico, em vez de seguir sem checkpoint. Crons e canais não mudaram; este patch não dispara publicação.

Testes em bare Git/clones temporários comprovam preservação de duas novas tarefas e ausência de push quando o gerador falha. Contratos cobrem estados incompatíveis, edição+remoção, IDs repetidos, campos disjuntos, histórico, fila e códigos de falha. Não garante transação com plataforma social ou exatamente-uma-vez. Rollback: reverter esta PR, sem reverter dados privados/publicados nem reexecutar efeitos externos. Resultados e hashes da promoção ficam na Base.

## Integridade da própria bancada

A primeira coleta de arquivos desta rodada incluiu seis estados alterados por testes legados, inclusive duas pendências publicar geradas em cópia local. Foram restaurados exatamente pelos SHAs originais em PR4, sem sobrescrever alterações concorrentes. Não eram medições nem tarefas autorizadas. Nunca considerar fixture como progresso real.

Agora os contratos rodam em cópia descartável por teste, sem .git/segredos e com transporte externo bloqueado. Mesmo teste que escreve estado ou falha não altera o checkout a publicar. Workflows usam o executor isolado; novas provas exercitam escrita/falha/segredo/rede e nome de script inválido. O coletor de promoção deve aceitar somente caminhos explícitos de código, workflow e documentação, nunca todo diff da bancada. Dados autoritativos e novas métricas não pertencem a PR de correção de código.
