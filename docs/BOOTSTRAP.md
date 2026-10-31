# Telegram Robot Leads — Bootstrap operacional

Este ficheiro regista as regras acordadas pelo proprietário e serve de **referência
operacional única para a lógica de grupos**. Não cria um novo framework,
serviço, bot, motor ou workflow. É a regra atual para futuras correções;
os registos históricos datados não a substituem.

## Descoberta e grupos

- **Conta 1:** pesquisa pública do nicho IPTV/VPN em Portugal e Espanha (PT_ES).
- **Conta 2:** pesquisa do nicho IPTV/VPN no restante contexto europeu (EU_OTHER).
- Os sinais regionais são palavras-chave; não garantem a origem geográfica real do grupo.
- **Não existe quota fixa de um grupo por dia.** Respeitam-se o espaçamento entre operações, as permissões dos grupos e os erros/restrições reais do Telegram.
- **As duas contas podem pertencer ao mesmo grupo público.**
- O histórico de adesões e os resultados incertos são separados por **(conta, grupo)**, usando uma base partilhada. Nunca repetir uma tentativa confirmada ou incerta da mesma conta. Os registos válidos do formato antigo continuam a ser reconhecidos.
- A descoberta pública identifica grupos. A entrada de uma conta num grupo é uma operação separada e deve ser confirmada; ausência num diálogo parcial não prova que a conta abandonou um grupo.
- Os grupos públicos descobertos com etiqueta PT_ES são encaminhados para a conta 1; os de EU_OTHER, para a conta 2. Se um grupo for identificado nas duas pesquisas, ambas podem tentar aderir, cada uma apenas uma vez.
- O único trabalhador agenda no máximo uma tentativa de entrada por conta em cada ciclo, sem impor um máximo diário. O histórico de membros de grupos é sempre separado por conta. Uma pesquisa concluída não significa que a adesão foi aceite.
- **Pesquisa versus adesão:** a implementação atual limita a frequência de **pesquisas** a uma tentativa diária por conta (para não repetir a mesma consulta). Isto **não** significa um limite diário de grupos descobertos ou de adesões a grupos públicos.
- A adesão automática a grupos encontrados exige que a descoberta regional esteja ativa na configuração do trabalhador. Um grupo descoberto não é, por si só, um grupo em que a conta já entrou.

## Sistema existente

- Um único trabalhador PM2, duas sessões privadas, estado persistente partilhado e supervisor passivo; sem novas camadas, pontes ou coordenadores.
- Não alterar as regras existentes de membros: entrar no grupo de destino exige permissão ou adesão voluntária. Não recolher listas de participantes de grupos de terceiros.
- Preservar sessões, estado, históricos e backups. Não tocar noutros projetos.
- Alterar e testar código no GitHub não prova que a revisão foi instalada ou ativada na VPS. Conferir SHA instalado, funcionamento do trabalhador e operações reais antes de declarar conclusão.

## Progresso desta revisão

- Separar a deduplicação de grupos por conta e retirar a quota fixa de um grupo por dia.
- Manter espaçamento e paragem perante restrições reais.
- Validação de software em cópia isolada; implantação em produção requer confirmação separada.

## Hierarquia e sincronização dos documentos

- `AGENTS.md`: entrada para agentes e limites de atuação; remete para este bootstrap.
- `docs/BOOTSTRAP.md`: **regras funcionais atuais** das duas contas, regiões, grupos e deduplicação.
- `docs/PROJECT-STATE.md`: **factos observados** de GitHub, testes e instalação na VPS (com data e SHA).
- `docs/GOVERNANCE.md`: normas de governação do repositório.
- Documentos datados, checkpoints e decisões anteriores são **histórico**; não prevalecem sobre a especificação operacional atual nem justificam alterar produção.
- Sempre que se altere uma regra: atualizar **neste mesmo projeto** o código, os testes, o bootstrap e o estado; corrigir documentos operacionais que contradigam a nova regra, sem apagar evidências históricas.
- Não criar outra estrutura de framework nem duplicar estas regras em vários ficheiros como fontes independentes. Preferir ligações para este documento.

## Estado de validação e implantação

A revisão de grupos está integrada na `main` e passou 272 testes em execução
isolada pelo REA FINAL (GitHub Actions #41239720587). **O deploy na VPS não
está certificado para esta revisão:** o último SHA instalado confirmado em
31-10-2026 era `3d53bf473fc0a37a4d8905f58a5bfff0948b3177`. Consultar
`docs/PROJECT-STATE.md` para a verificação operacional mais recente.
Não modificar sessões privadas, histórico persistente ou backups para
sincronizar apenas documentação.
