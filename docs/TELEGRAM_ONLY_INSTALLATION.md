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

## Via canónica — GitHub Actions central → SSH → VPS (28/10/2026)

**Existe uma única via de instalação remota: o workflow já existente no
repositório `martaxi-boss/VPS`, em
`.github/workflows/telegram-leads-vps-stage-20261019.yml`.**
Esse workflow usa a credencial **já existente no repositório VPS**,
`secrets.VPS_SSH_PASSWORD`, autentica com o utilizador SSH `ubuntu`
e confirma a identidade ED25519 fixada da VPS antes de enviar código.
Não criar, duplicar nem copiar passwords, chaves, secrets ou workflows
SSH para o repositório Telegram. A credencial não é herdada por outros
repositórios GitHub Actions.

Neste repositório, `.github/workflows/safe-growth-checks.yml` limita-se
a testes locais sem SSH. O antigo
`.github/workflows/deploy-telegram-leads.yml` foi removido: exigia
`TELEGRAM_LEADS_SSH_HOST`, `TELEGRAM_LEADS_SSH_USER`,
`TELEGRAM_LEADS_SSH_KEY` e `TELEGRAM_LEADS_SSH_KNOWN_HOSTS` que
não estavam disponíveis neste repositório; os seus erros de
GitHub Actions **não** eram falhas do PM2 ou da VPS.

**Prova real:** execução do workflow central
[40609597231](https://github.com/martaxi-boss/VPS/actions/runs/40609597231),
de 28/10/2026, 00:34 UTC. Certificou a origem
`7c0ef8a1d9be5d18568a133bcfdb79e4e0bcd9aa`, a identidade SSH,
higienização `APPLIED`, ativação `PROJECT_WORKER_RESTARTED`, duas
sessões preservadas e PM2 `ONLINE`. O relatório **não** comprovou
as duas contas autenticadas online nem novas adesões ao grupo.

**Diferença de versões:** a instalação verificada na VPS continua no
SHA `7c0ef8a1d9be5d18568a133bcfdb79e4e0bcd9aa`; o merge do
Radar de Crescimento (#38) pôs a `main` do Telegram no SHA
`5ade747d82066515bc0032ca53639b13670ccc36`. CI verde não
significa que o Radar já esteja instalado na VPS.

Antes de um *novo* deploy, o **mesmo workflow central** terá de ser
atualizado e validado, com `TARGET_SHA` igual ao novo commit aprovado,
`EXPECTED_INSTALLED` igual ao SHA realmente instalado, e o ficheiro
`scripts/growth_radar.py` incluído tanto nos testes como no pacote
de runtime. O workflow central está atualmente fixado na versão antiga.
**Não alterar o repositório VPS a partir deste projeto sem autorização**
e não tentar contornar a verificação de versão do instalador.

A instalação verifica paths e versões, modifica apenas os ficheiros
permitidos em `/opt/telegram-robot-leads` e conserva backups privados
em `.telegram-leads-release-backups`. As sessões, `.env`,
`accounts.json`, bases de dados, estado, journals e `.venv` são
preservados.

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

O workflow central verifica que existe **exatamente um** worker com nome
`telegram-robot-leads`, cwd `/opt/telegram-robot-leads`, script
`/opt/telegram-robot-leads/main.py` e PM2 do proprietário correto
(`/root/.pm2`). Só então o script de ativação reinicia esse worker.
Nenhum `pm2 restart all`, `pm2 delete`, `pm2 start` ou criação de
novo daemon é autorizada. Se o estado for divergente, bloquear.

O código só ativa o modelo orgânico se existir um
`growth_model.json` privado, válido e autorizado no cofre. PM2
`ONLINE` não demonstra autorização, ligação das contas Telegram ou
novas entradas de membros no grupo.

## Critérios de fecho

Só declarar o deploy concluído quando o **workflow central da VPS**
terminar com `SUCCESS` e devolver prova do SHA exato instalado,
identidade SSH fixada, duas sessões preservadas, higienização limitada
a este projeto, worker único verificado e relatório pós-ativação.
O SHA da `main` do Telegram e o SHA instalado são verificações
independentes, não podem ser confundidos.

O relatório operacional deve separar os estados PM2 e Telethon.
A confirmação de membros adicionados exige eventos reais e
verificáveis; testes, modelos e estados `ONLINE` não a substituem.
Não forçar marcadores, não apagar estado, não trocar secrets e
não reiniciar serviços de outros projetos perante bloqueios.
