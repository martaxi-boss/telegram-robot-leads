# Telegram Robot Leads — Bootstrap operacional

Este ficheiro regista as regras acordadas pelo proprietário. Não cria um novo framework, serviço, bot, motor ou workflow.

## Descoberta e grupos

- **Conta 1:** pesquisa pública do nicho IPTV/VPN em Portugal e Espanha (PT_ES).
- **Conta 2:** pesquisa do nicho IPTV/VPN no restante contexto europeu (EU_OTHER).
- Os sinais regionais são palavras-chave; não garantem a origem geográfica real do grupo.
- **Não existe quota fixa de um grupo por dia.** Respeitam-se o espaçamento entre operações, as permissões dos grupos e os erros/restrições reais do Telegram.
- **As duas contas podem pertencer ao mesmo grupo público.**
- O histórico de adesões e os resultados incertos são separados por **(conta, grupo)**, usando uma base partilhada. Nunca repetir uma tentativa confirmada ou incerta da mesma conta. Os registos válidos do formato antigo continuam a ser reconhecidos.
- A descoberta pública identifica grupos. A entrada de uma conta num grupo é uma operação separada e deve ser confirmada; ausência num diálogo parcial não prova que a conta abandonou um grupo.
- A passagem automática dos grupos descobertos para a fila de adesões deve manter a divisão regional e não confundir pesquisa com entrada efetiva.

## Sistema existente

- Um único trabalhador PM2, duas sessões privadas, estado persistente partilhado e supervisor passivo; sem novas camadas, pontes ou coordenadores.
- Não alterar as regras existentes de membros: entrar no grupo de destino exige permissão ou adesão voluntária. Não recolher listas de participantes de grupos de terceiros.
- Preservar sessões, estado, históricos e backups. Não tocar noutros projetos.
- Alterar e testar código no GitHub não prova que a revisão foi instalada ou ativada na VPS. Conferir SHA instalado, funcionamento do trabalhador e operações reais antes de declarar conclusão.

## Progresso desta revisão

- Separar a deduplicação de grupos por conta e retirar a quota fixa de um grupo por dia.
- Manter espaçamento e paragem perante restrições reais.
- Validação de software em cópia isolada; implantação em produção requer confirmação separada.
