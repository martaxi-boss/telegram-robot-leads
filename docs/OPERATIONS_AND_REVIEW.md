# Robot Leads — operação, revisão de grupos e diagnóstico

**Nota de atualização, 31-10-2026:** este manual inclui comandos antigos
de revisão manual e marcos históricos. As **regras funcionais atuais**
estão em [BOOTSTRAP.md](BOOTSTRAP.md); o **estado de implantação** está em
[PROJECT-STATE.md](PROJECT-STATE.md). Não interpretar limites ou
agendamentos antigos deste manual como configuração atual.

## 1. O que já existe

O Robot Leads pesquisa grupos públicos do nicho IPTV, guarda apenas metadados
públicos num catálogo privado e anuncia uma ligação pública para **adesão
voluntária** ao grupo de destino. Utiliza o trabalhador PM2 e as duas sessões
existentes, sem agente adicional.

A pesquisa **não** recolhe participantes, não pede dados pessoais de membros
de terceiros e não efetua promoções ou inclusões automáticas nesses grupos.
Ter um @username público não significa ter aceitado ser adicionado a outro grupo.

## 2. Consultar o catálogo e selecionar grupos

Com a nova versão instalada na VPS, os comandos são executados em
/opt/telegram-robot-leads com o ambiente Python existente:

~~~bash
.venv/bin/python scripts/public_group_discovery.py --list
.venv/bin/python scripts/public_group_review.py --list

# Apenas quando o operador escolher esse grupo específico depois de rever
# o catálogo e os seus termos; exemplo ilustrativo, não é executado por CI:
.venv/bin/python scripts/public_group_review.py \
  --approve @NOME_PUBLICO_ENCONTRADO --confirm-operator-selection
~~~

O último comando não se liga ao Telegram: inclui **apenas** o grupo público
selecionado no ficheiro de allowlist do projeto, no cofre existente,
validando propriedade e permissões. É a via **manual opcional**.
A implementação mais recente também pode encaminhar automaticamente os grupos
públicos encontrados na pesquisa regional para a conta correspondente, no
trabalhador existente, se as opções de descoberta estiverem ativas.
**Não há um máximo diário fixo de adesões a grupos.** Existe controlo por
(conta, grupo), espaçamento entre operações e respeito pelas restrições reais.
Isto não adiciona pessoas ao grupo de destino e não altera outras aplicações.

## 3. Estado do serviço e prova de funcionamento

~~~bash
# Resumo sem contactos Telegram, sem modificar sessões ou base de dados:
.venv/bin/python scripts/leads_operational_report.py \
  --expected-source CODIGO_SHA_VERIFICADO \
  --no-pm2

# Opcional: usar apenas no contexto do utilizador que gere o PM2 correto.
# A CLI do PM2 pode iniciar outro daemon se ainda não existir nenhum.
.venv/bin/python scripts/leads_operational_report.py \
  --expected-source CODIGO_SHA_VERIFICADO \
  --with-pm2

# O comando de estado já existente inclui o relatório:
bash scripts/telegram-robot-leads-status.sh
~~~

A resposta identifica:

- SHA realmente instalada e se coincide com o SHA esperado.
- Duas sessões legíveis **offline**; distingue credenciais próprias da
  aplicação da API pública Android de fallback.
- Estado PM2 apenas com `--with-pm2`, nunca por defeito; sem isso
  o resultado é `NOT_QUERIED` para evitar arrancar daemons noutras contas.
- Contagens redigidas da fila (`approved_username_entries`) e dos
  grupos autorizados (`allowlisted_group_entries`), distinguindo uma
  fila vazia (`EMPTY`) de grupos apenas encontrados na pesquisa.
- Quantidade de grupos públicos pesquisados e data da última tentativa.
- Contagem de contas restringidas, ações pendentes e adições autorizadas.
- Último evento do Supervisor, com contagens e códigos, **sem nomes de
  utilizadores, listas, auth keys nem segredos**.
- Estado LIVE_PUBLIC_DISCOVERY_OBSERVED *apenas* quando há código e
  proveniência válidos, PM2 online, estado operacional legível e um ciclo
  recente de pesquisa concluída **posterior à instalação da versão**.

Esse estado significa pesquisa realmente observada, **não** certificação da
capacidade de adicionar pessoas ou de continuar online indefinidamente.

## 4. Permissões legítimas e credenciais

- Um TARGET_GROUP público permite divulgar uma ligação voluntária.
  A ligação não confirma, por si só, que o grupo está acessível na plataforma.
- Links de pedido de adesão dedicados, com nomes de campanhas, podem requerer
  um bot dedicado ou permissões administrativas da conta autorizada.
- Não copiar tokens de outros projetos, usar o bot iptvpn_bot nem intervir
  no Supervisor do Project Leader.
- Credenciais de aplicação Telegram próprias (api_id/api_hash) continuam
  a depender do registo autorizado no Telegram; não podem ser inventadas.
  Nunca inserir credenciais em commits, Issues, logs ou nesta conversa.
- Falhas de permissão e restrições reais do Telegram devem continuar visíveis
  nos relatórios e **não** ser contornadas.

## 5. Evidência e limite da certificação

GitHub Actions executa testes offline de relatório, privacidade, seleção,
deduplicação e manipulação de ficheiros privados. **CI verde não comprova
implantação nem pesquisa real online.** O agendamento de 20-10-2026 às 08h00
é um registo histórico, não uma instrução atual de arranque. Consultar a
versão efetivamente instalada e o PM2 antes de qualquer conclusão. Em
31-10-2026 a revisão da PR #47 tinha 272 testes PASS, sem deploy comprovado.

O motor de adição direta está limitado a quem autorizou explicitamente entrar
no grupo. Não inclui cópia em massa de listas de terceiros nem camuflagem do
comportamento para evitar controlos anti-spam do Telegram.

## 6. Correcoes preventivas propostas em 2026-10-23

- **Histórico de 23-10-2026:** a descoberta usava a conta 1. Hoje a pesquisa
  regional atribui PT/ES à conta 1 e os restantes termos europeus à conta 2.
  Se o estado persistente indicar uma restricao da conta, o ciclo suspende
  essa conta sem ligar ao Telegram ou repetir tentativas bloqueadas. A remocao do bloqueio
  requer reconciliacao operacional explicita; nunca ocorre por meia-noite.
- O ficheiro `operation-state.json` existente deve ser um ficheiro regular,
  pertencente ao utilizador do processo, privado (sem permissoes de grupo ou
  outros) e com tamanho limitado. Um estado incorreto bloqueia a operacao;
  **nao apagar nem recriar** o ficheiro para ultrapassar o bloqueio, pois
  contem deduplicacao e resultados de operacoes remotas incertas.
- Um estado com data invalida ou posterior ao calendario de Portugal
  bloqueia a leitura, em vez de reiniciar as quotas a zero. A recuperacao
  depende de analise humana da proveniencia e preservacao dos pendentes.
- Qualquer falha durante a ligacao/autorizacao de uma sessao Telethon
  desencadeia a sua desconexao antes de propagar o erro, sem modificar o
  ficheiro de sessao SQLite guardado.
- O stdout regular do PM2 e o modo `--once` devolvem apenas contagens
  e codigos de estado. Os nomes de grupos e de utilizadores permanecem no
  diario privado do Supervisor (`supervisor-events.jsonl`, permissao 0600);
  nao encaminhar esse ficheiro para logs ou notificacoes publicas.
- Esta verificacao apenas introduz testes offline e codigo num ramo de revisao.
  Nao constitui prova de instalacao na VPS, sucesso da pesquisa ou adicoes.
