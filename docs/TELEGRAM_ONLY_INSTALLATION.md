# Instalação e higienização — EXCLUSIVAMENTE Telegram Robot Leads

## Autorização e fronteira

Autorização do proprietário, 27/10/2026: instalar e higienizar apenas o
**Telegram Robot Leads**, sem alterações em nenhum outro projeto na VPS.

Repositório: martaxi-boss/telegram-robot-leads
Runtime: /opt/telegram-robot-leads
Cofre preservado: /root/project-secrets/telegram-robot-leads
Estado preservado: /var/lib/telegram-robot-leads
Worker único: telegram-robot-leads

Não tocar no iptvpn_bot, Supervisor Project Leader, PINK IPTV, FADEGO,
Low Cost Europa, VPN, REA, outros processos PM2 ou repositórios.
Não criar um novo servidor, agente, processo PM2 ou sessão Telegram.

## Provas anteriores à instalação

- Em 27/10/2026, REA observou o commit antigo instalado
  d8736bd359de795182ee717448c93df2977d0a44, as duas sessões
  legíveis offline e um catálogo de dois grupos públicos.
- O último ciclo visto registava zero ações de membros autorizados;
  isso não é prova de uma falha de adição.
- O audit report viu credenciais de API Android de fallback, não
  credenciais privadas de uma aplicação Telegram. Não substituir segredos.
- Uma operação REA de process capture falhou na limpeza de subprocessos,
  pelo que **não** se deve usar esse mecanismo repetidamente para deploy
  ou para comandos globais de PM2.
- GitHub CI prévio não certifica uma instalação live.

## Caminho previsto — apenas GitHub Actions deste repositório

O workflow do projeto é .github/workflows/deploy-telegram-leads.yml.
É executado depois do merge do novo workflow em main ou por workflow_dispatch.
Uma PR pode certificar o código, mas **nunca** faz login SSH com secrets.

O workflow exige os seguintes Actions secrets pertencentes a
**este repositório** (não os copiar de outro projeto sem autorização):

- TELEGRAM_LEADS_SSH_HOST: hostname ou IP da VPS.
- TELEGRAM_LEADS_SSH_USER: utilizador SSH com acesso root validado.
- TELEGRAM_LEADS_SSH_KEY: chave SSH privada com acesso já autorizado.
- TELEGRAM_LEADS_SSH_KNOWN_HOSTS: pin SSH do host verificado.
- TELEGRAM_LEADS_SSH_PORT: opcional, porta SSH (22 por defeito).
- TELEGRAM_LEADS_PM2_HOME: opcional, diretório do daemon PM2 correto
  (por exemplo, /root/.pm2, SOMENTE após verificação).

Não imprimir keys ou hashes da aplicação no Actions/logs.
O workflow bloqueia se host, utilizador, chave ou known_hosts estiverem vazios.

A instalação compara exatamente o commit anterior auditado. Se o commit
da VPS mudou entretanto, bloqueia: NÃO reiniciar, forçar o marcador,
apagar o estado, nem substituir a versão mais recente.
O instalador modifica apenas uma lista fixa de ficheiros de código dentro
de /opt/telegram-robot-leads. A cópia de segurança fica dentro da pasta
do projeto, em .telegram-leads-release-backups (NÃO apagar).
As duas sessões, .env, accounts.json, bases de dados, state, journals e
o ambiente virtual não são apagados nem substituídos.

## Higienização

A única remoção autorizada é bytecode Python *.pyc ou *.pyo dentro de
/opt/telegram-robot-leads/__pycache__,
/opt/telegram-robot-leads/scripts/__pycache__ ou
/opt/telegram-robot-leads/tests/__pycache__.

A limpeza bloqueia conteúdo inesperado ou symlinks. Não entra na .venv,
noutros diretórios, nem elimina backups, sessões, logs ou histórico.
Comando de inventário (sem alterações):

    /usr/bin/python3 /opt/telegram-robot-leads/scripts/project_hygiene.py

Comando de aplicação (após autorização explícita do operador):

    /usr/bin/python3 /opt/telegram-robot-leads/scripts/project_hygiene.py --apply --confirm-telegram-only

## Ativação, sem PM2 global

O instalador reporta STAGED_NOT_ACTIVATED. O workflow só tenta reiniciar
o worker único **se** TELEGRAM_LEADS_PM2_HOME estiver configurado com o
diretório de um daemon PM2 existente e o processo tiver um script e um cwd
exatamente iguais aos do Telegram Robot Leads.

Se o worker estiver em falta, duplicado, noutro cwd, ou o PM2 for
desconhecido, o estado é BLOCKED e não há reinícios globais, nem pm2 start,
pm2 delete, nem alterações a outros trabalhadores.
O script ativador não considera PM2 ONLINE prova de sucesso Telegram.

O modelo orgânico do novo código não entra em ação se não existir no
cofre do projeto um growth_model.json privado e validado. Nenhum
nome de canal fictício deve ser instalado em produção.

## Critérios de fecho

Uma instalação é confirmada somente com: workflow SUCCESS com HEAD exato
de main, SHA da versão instalada verificada depois da cópia, duas sessões
originais preservadas, limpeza de caches concluída e reavaliação da versão
na VPS. Uma ativação requer adicionalmente prova do processo único correto,
ambas as contas autenticadas online e operação de adesão voluntária
observada com contadores de resultados, não apenas testes de mocks.

Se faltarem SSH secrets, acesso à VPS, PM2_HOME ou permissões de Telegram,
informar que a instalação/ativação NÃO está concluída, com código de
bloqueio. Não inferir sucesso com base na PR ou no commit.
