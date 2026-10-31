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

## Motor antigo: recuperação do conhecimento (31-10-2026)

**Âmbito:** esta secção documenta o que foi encontrado no histórico, o relato
do proprietário e o que falta investigar. Não reativa o motor antigo, não
autoriza operações sobre terceiros e não modifica o trabalhador em produção.

### Funcionalidades comprovadas no código histórico

- O motor original sobrevive no commit
  [`1862998844782764d263ee8e49a1476a7f86beac`](https://github.com/martaxi-boss/telegram-robot-leads/commit/1862998844782764d263ee8e49a1476a7f86beac),
  em `main.py` (2.312 linhas). **Não é o ponto de entrada ativo** da VPS.
- Existia descoberta e adesão a grupos de origem, consulta de participantes,
  exclusão dos administradores/donos da origem, de bots, de contas eliminadas
  e de perfis sem `@username`. Existiam ainda filtros de atividade recente
  (`is_worth_scraping`) e de região/perfil.
- O motor antigo guardava candidatos em `users.db`, com fila e estados,
  repartição de trabalho por sessão, deduplicação por ID de utilizador,
  métricas por conta e por dia (`adder_daily`) e registo de eventos.
  Tratava estados finais para evitar repetir certas operações.
- A rotina antiga chamava `InviteToChannelRequest` e contabilizava
  `invite_ok`/`adds_ok`, bem como recusas de privacidade, ausência de
  contacto mútuo e restrições do Telegram. **Não se comprovou um filtro que
  garantisse antecipadamente o consentimento ou 100% de sucesso**.
- Existiam temporizações variáveis e retoma da fila. Isso descreve a
  implementação histórica, **não** uma licença para imitar pessoas ou
  contornar proteção anti-spam.

### Relato do proprietário — não confundir com prova técnica

- O objetivo inicial era automatizar um trabalho manual: descobrir grupos
  públicos relevantes e gerir uma fila de potenciais novos membros para
  o grupo de destino, com ambas as contas e base comum.
- O proprietário recorda aproximadamente **10 adições por dia por conta**
  e uma taxa de sucesso muito elevada; esse número **não foi certificado**
  pelos dados ainda disponíveis.
- A preferência inequívoca é que **uma pessoa já adicionada ao grupo de
  destino não seja novamente adicionada**, mesmo que depois saia. O mesmo
  bloqueio de repetição aplica-se se a outra conta a encontrar noutro grupo.
  Para essa memória, usar ID estável de utilizador quando obtido de modo
  legítimo; `@username` isolado pode mudar.
- Os candidatos recebiam estados de fila e de resultado, de modo que
  reinícios, cruzamento entre contas e repetição de grupos não apagassem o
  histórico. Esta é a regra funcional a preservar na arquitetura.

### Estado comprovado hoje, sem extrapolações

- Instalação VPS verificada: `8298503f7b21466ebf14b9f164f9e103c9c781e7`,
  dois ficheiros de sessão, trabalhador PM2 online e descoberta regional
  ativa (REA #41248796124, 31-10-2026).
- Catálogo atual: **3 grupos públicos**; **1 adesão a grupo registada pela
  conta 2** no diário. Isto é diferente de adicionar pessoas ao grupo de
  destino; a pertença não foi confirmada independentemente pelo diálogo.
- Estado atual: **0 ações de adição de membros concluídas** nas duas contas.
  Auditoria a 16.730 eventos operacionais: **0 ações de membros registadas**
  e 1 entrada em grupo de origem (REA #41250971838).
- A base histórica `users.db` e `telethon_adder.log` **não foram localizadas**
  nas pastas inspecionadas do projeto na VPS. Isso **não prova** que nunca
  houve adições no passado, em especial pela conta 1.
- O motor atual `scripts/safe_runtime.py` não executa a cadeia histórica
  de consulta de participantes e adição automática de terceiros. Não
  confundir testes de software (272 PASS) com prova de crescimento de membros.

### Comparativo concluído e fase seguinte definida (31-10-2026)

- Relatório factual de correspondências e diferenças:
  [Motor antigo versus atual](HISTORICAL-ENGINE-COMPARISON-20261031.md).
  **O relatório não cria outra fonte de regras.**
- A distinção entre histórico de grupos por **(conta, grupo)** e histórico
  global de **pessoas** já está implementada no motor atual. A memória
  global de IDs, adições, pedidos aprovados e operações pendentes não deve
  ser substituída nem apagada, mesmo que alguém saia do grupo ou mude
  de username.
- A fila atual aceita apenas pessoas que tenham autorizado a entrada;
  as contas 1/2 continuam com as regiões e as sessões existentes.
- **Melhoria ainda por implementar:** contadores agregados de fila
  (autorizados configurados, à espera, concluídos, ambíguos e IDs históricos),
  sem expor dados pessoais no PM2/supervisor; testes explícitos de saída,
  reinício e tentativa pela segunda conta. Não criar worker, base de dados,
  framework, motor ou ponte adicionais.
- A ferramenta bloqueou a tentativa de edição operacional antes da
  execução: **não foi aplicado nem certificado novo código de fila** nesta
  passagem; todo o trabalho gravado é documental.
- Faltam backups antigos da base users.db e do log telethon_adder.log
  para determinar se alguma conta adicionou pessoas no passado.
  Uma recuperação exigirá primeiro comparação em modo só de leitura.
- Não reativar recolha indiscriminada de participantes terceiros nem
  adições não autorizadas. Um username, atividade recente ou participação
  num grupo público não equivale a autorização para entrar noutro grupo.

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

O deploy de grupos e a correção de catálogo foram instalados e verificados
na VPS com SHA `8298503f7b21466ebf14b9f164f9e103c9c781e7`.
O ciclo do trabalhador voltou a `CYCLE` depois da correção do
`TypeError` (REA #41243391285), e a verificação de 31-10-2026
(REA #41248796124) confirmou PM2 online, duas sessões e uma adesão a
grupo de origem registada, sem novas ações de membros.

A inspeção histórica do código (REA #41249943708) confirmou as funções
de extração, fila e adição do motor antigo. As auditorias de evidência
(REA #41250761576, #41250832084, #41250916097 e #41250971838)
**não localizaram sucesso histórico de adições de pessoas** nos dados
examinados. Ausência de dados antigos não equivale a prova de zero
adições históricas. O comparativo funcional posterior encontra-se em
[Motor antigo versus atual](HISTORICAL-ENGINE-COMPARISON-20261031.md).
A melhoria de visibilidade da fila é apenas especificação, sem deploy.
Consultar `docs/PROJECT-STATE.md` para a situação e proveniência.
