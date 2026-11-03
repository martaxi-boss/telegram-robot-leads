# Telegram Robot Leads — instalacao VPS Ubuntu independente

**Repositorio GitHub:** `martaxi-boss/telegram-robot-leads`.
**Estado verificado:** 2026-11-03 UTC.

## Raiz fisica do projeto

`/srv/projects/telegram-robot-leads/` e a instalacao fisica; o caminho antigo `/opt/telegram-robot-leads` permanece como **symlink temporario**, sem uma segunda copia.

Componentes proprios:
- `main.py`, `scripts/` — aplicacao e operacoes;
- `.venv/` — ambiente Python do projeto;
- `optin/` — componentes Opt-in;
- `archive/` — ambiente antigo, preservado mas nao ativo;
- `data/` — estado operacional (antes em `/var/lib/telegram-robot-leads`);
- `private/` — duas sessoes Telegram e outros segredos (antes em `/root/project-secrets/telegram-robot-leads`).

As diretorias `data/` e `private/` foram **movidas fisicamente**, nao copiadas nem ligadas por symlink. As sessoes foram confirmadas por hash SHA-256, tamanho e inode. O processo foi reiniciado somente para aplicar os novos caminhos e ficou `online` com PID `606651`. O robot independente `iptvpn_bot` nao foi reiniciado e manteve PID `1120`. A configuracao PM2 foi guardada.

**Prova principal:** [GitHub Actions #41721810190](https://github.com/martaxi-boss/VPS/actions/runs/41721810190) — execucao REA com exit 0 e verificacoes de sessao e PM2. A correcao previa dos caminhos de arranque PM2 foi validada no [#41721220196](https://github.com/martaxi-boss/VPS/actions/runs/41721220196).

O GitHub guarda **apenas codigo, manifests, testes e documentacao**. A `.gitignore` exclui `/private/` e `/data/`. Nunca publicar tokens, ficheiros de sessao, estado, segredos ou arquivos de execucao.

## Pendencias de isolamento

- O daemon PM2 continua global, em `/root/.pm2`, tambem utilizado por `iptvpn_bot`. A separacao dos processos foi respeitada nas migracoes, mas **a independencia do gestor PM2 ainda nao esta certificada**.
- Em `/usr/local/sbin/telegram_leads_activate_20261020.py` existe um script de ativacao antigo, ainda com referencias anteriores. Avaliar a sua relacao com unidades e cron antes de mover ou retirar.
- No repositorio `martaxi-boss/VPS`, o workflow de deploy historico `.github/workflows/telegram-leads-vps-stage-20261019.yml` ainda tem caminhos legados e um SHA pinned. Uma alteracao nesse workflow pode desencadear deploy automatico. **Nao executar a versao antiga sem atualizar e validar.**
- A ligacao `/opt/telegram-robot-leads` so deve ser retirada apos comprovacao de ausencia de referencias de arranque, scripts e processos.
- A desinstalacao independente exige parar apenas o bot correspondente e seguir procedimento que exporte/guarde os dados privados, sem alterar o outro robot.

## Regra permanente

Cada projeto GitHub tem codigo, runtime, fornecedores e estado exclusivos dentro da sua propria pasta. O Linux e o gestor de processos podem exigir ficheiros de integracao em caminhos padrao; inventariar esses ficheiros por proprietario e garantir que a desinstalacao de um projeto nao interrompe outro. **Nao alterar a logica operacional do Telegram Robot Leads durante tarefas de organizacao.**
