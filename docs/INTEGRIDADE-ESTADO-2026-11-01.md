# Estado concorrente e resultado verificável

Pedido do dono: fechar o ciclo sem concluir apenas cortes intermediários. O helper deixou de chamar todo posts/*.json/md de saída descartável. Estados usam merge de três vias: campos independentes, tarefas por ID, listas/históricos append-only. Conflito incompatível permanece explícito e preserva commits; não escolhe arbitrariamente uma tarefa e não repete ação externa. Só saídas conhecidas podem ser regeneradas, com GERAR configurado e sucesso obrigatório. Sem gerador, não descarta versão.

Gerador falho, commit falho, ação falha e persistência falha não são sucesso. Loop usa o helper comum de entrada no main e encerra o bloco com erro após tentativa de persistir diagnóstico, em vez de seguir sem checkpoint. Crons e canais não mudaram; este patch não dispara publicação.

Testes em bare Git/clones temporários comprovam preservação de duas novas tarefas e ausência de push quando o gerador falha. Contratos cobrem estados incompatíveis, edição+remoção, IDs repetidos, campos disjuntos, histórico, fila e códigos de falha. Não garante transação com plataforma social ou exatamente-uma-vez. Rollback: reverter esta PR, sem reverter dados privados/publicados nem reexecutar efeitos externos. Resultados e hashes da promoção ficam na Base.
