# Robot Leads — fecho operacional e aprovação de grupos

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
validando propriedade e permissões. O trabalhador normal continuará a aplicar
os limites de adesão a grupos e as restrições da plataforma. O programa não
autoriza automaticamente todos os grupos encontrados nem altera outras apps.

## 3. Estado do serviço e prova de funcionamento

~~~bash
# Resumo sem contactos Telegram, sem modificar sessões ou base de dados:
.venv/bin/python scripts/leads_operational_report.py \
  --expected-source CODIGO_SHA_VERIFICADO \
  --no-pm2

# Inclui o estado PM2, mantendo zero chamadas ao Telegram:
.venv/bin/python scripts/leads_operational_report.py \
  --expected-source CODIGO_SHA_VERIFICADO

# O comando de estado já existente inclui o relatório:
bash scripts/telegram-robot-leads-status.sh
~~~

A resposta identifica:

- SHA realmente instalada e se coincide com o SHA esperado.
- Duas sessões legíveis **offline**; distingue credenciais próprias da
  aplicação da API pública Android de fallback.
- PM2 online/ausente/duplicado, sem confundir com funcionamento Telegram.
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
deduplicação e manipulação de ficheiros privados. **CI verde e instalação
STAGED_NOT_STARTED não comprovam pesquisa online.** O temporizador já preparado
para 20/10/2026 às 08h00 em Portugal continua responsável pelo arranque;
não antecipar a ativação.

O motor de adição direta está limitado a quem autorizou explicitamente entrar
no grupo. Não inclui cópia em massa de listas de terceiros nem camuflagem do
comportamento para evitar controlos anti-spam do Telegram.

## 6. Correcoes preventivas propostas em 2026-10-23

- A descoberta publica usa a conta 1. Se o estado persistente indicar uma
  restricao da conta, o ciclo reporta `account_1_hard_stop` sem ligar ao
  Telegram nem repetir uma pesquisa no dia seguinte. A remocao do bloqueio
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
- Esta verificacao apenas introduz testes offline e codigo num ramo de revisao.
  Nao constitui prova de instalacao na VPS, sucesso da pesquisa ou adicoes.
