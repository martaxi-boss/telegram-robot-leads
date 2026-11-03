# Telegram Robot Leads — instalacao VPS Ubuntu

**Repositorio:** `martaxi-boss/telegram-robot-leads`.
**Data da verificacao:** 2026-11-03 UTC.

## Instalacao fisica canonica

- Codigo e dependencias exclusivas: `/srv/projects/telegram-robot-leads/` (aprox. 72,7 MB).
- Python ativo: `/srv/projects/telegram-robot-leads/.venv/`.
- Opt-in: `/srv/projects/telegram-robot-leads/optin/`.
- Python anterior (arquivo nao ativo): `/srv/projects/telegram-robot-leads/archive/previous-telegram-python-env/`.
- `/opt/telegram-robot-leads`: **symlink temporario**, nao uma segunda instalacao.

A migracao fisica foi executada pelo motor REA e validada com codigo interno zero, verificacoes Python/Node/Bash e PID PM2 inalterado (430721). O outro robo `iptvpn_bot` manteve PID 1120. [Prova: VPS Actions #41711090273](https://github.com/martaxi-boss/VPS/actions/runs/41711090273).

Foram alinhados os caminhos raiz de codigo no `ecosystem.config.js`, instalador e scripts principais, tanto na VPS como no GitHub. **Nao foi atualizada nem alterada a logica operacional do robo ou o conteudo das sessoes.** O GitHub `main` inclui apenas codigo, dependencias declarativas e documentacao, nao dados pessoais ou sessao.

## Componentes ainda fora e nao movidos

- Estado operacional: `/var/lib/telegram-robot-leads/` (aprox. 9 MB).
- Vault privado: `/root/project-secrets/telegram-robot-leads/` (aprox. 3,1 MB e **duas sessoes privadas**, permissao 0600).
- PM2 global em `/root/.pm2/`, com o processo em execucao ainda ligado a `/opt/telegram-robot-leads`.
- Um script antigo de ativacao em `/usr/local/sbin/telegram_leads_activate_20261020.py`.
- No repositorio `martaxi-boss/VPS`, o workflow de deploy `.github/workflows/telegram-leads-vps-stage-20261019.yml` continua a usar caminhos antigos e SHA de deploy antigo. **Nao foi alterado automaticamente**, pois a propria alteracao deste workflow desencadeia um deploy em `push main`. Precisa de cutover coordenado antes de um novo deploy.

Alguns modulos validam que diretorios de estado e de sessoes nao sao symlinks. **Nao criar symlinks para o vault ou os dados sem atualizar tambem todos os caminhos de arranque e o ambiente PM2 e testar um reinicio real**, para nao bloquear o bot.

## A desinstalacao ainda nao e por simples apagamento

Para concluir a organizacao, falta migrar dados e vault de forma transacional, alinhar PM2 e workflows, retirar a compatibilidade antiga, validar arranque/reinicio e registrar o procedimento de uninstall com exportacao/restauro de dados. Nao apagar nenhuma sessao nem publicar credenciais no GitHub.

## Higienizacao anterior

Foram removidas as pastas auxiliares externas `/opt/telegram-leads-optin` e `/home/ubuntu/telegram-leads-venv` ao integrar os componentes na pasta principal. O processo continuou online.
