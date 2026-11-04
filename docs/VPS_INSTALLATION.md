# Telegram Robot Leads — instalacao VPS Ubuntu independente

**Repositorio GitHub:** `martaxi-boss/telegram-robot-leads`.
**Estado verificado:** 2026-11-04 UTC, após separação de PM2.

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

- O daemon PM2 **já não é global**: foi transferido para `/srv/projects/telegram-robot-leads/.pm2` em [#41813373759](https://github.com/martaxi-boss/VPS/actions/runs/41813373759). O PM2 binário é próprio em `/srv/projects/telegram-robot-leads/tools/pm2` e o serviço `pm2-telegram-robot-leads.service` está ativo e habilitado. O antigo `pm2-root.service` foi desativado e parado. A antiga `/root/.pm2` ainda existe, mas está inativa e requer triagem de logs históricos de ambos os projetos antes de arquivar e eliminar.
- O ativador de 20-10-2026 e as duas unidades systemd foram movidos para `/srv/projects/telegram-robot-leads/archive/legacy/20261020-activation/`. O temporizador expirado ficou desativado. [Prova #41723648731](https://github.com/martaxi-boss/VPS/actions/runs/41723648731).
- Os quatro workflows historicos Telegram e o ativador de origem em `martaxi-boss/VPS` foram arquivados em `docs/archive/legacy-telegram-202610/`, fora das pastas executaveis. O deploy antigo tinha caminhos e SHAs desatualizados. [Commit 823a072d](https://github.com/martaxi-boss/VPS/commit/823a072dbb3377eca48b276e5d257a32960fe96f).
- A ligacao `/opt/telegram-robot-leads` so deve ser retirada apos comprovacao de ausencia de referencias de arranque, scripts e processos.
- A desinstalacao independente exige parar apenas o bot correspondente e seguir procedimento que exporte/guarde os dados privados, sem alterar o outro robot.

## Regra permanente

Cada projeto GitHub tem codigo, runtime, fornecedores e estado exclusivos dentro da sua propria pasta. O Linux e o gestor de processos podem exigir ficheiros de integracao em caminhos padrao; inventariar esses ficheiros por proprietario e garantir que a desinstalacao de um projeto nao interrompe outro. **Nao alterar a logica operacional do Telegram Robot Leads durante tarefas de organizacao.**

## Auditoria cruzada final

A verificacao real [GitHub Actions #41724074992](https://github.com/martaxi-boss/VPS/actions/runs/41724074992) confirmou os dois bots online com os mesmos PID, duas sessoes presentes em `private/`, estado em `data/`, sete raizes reais de projeto em `/srv/projects/` e servicos principais ativos. Esta era a fotografia de 03-11: o PM2 global e os caminhos exteriores REA/Codex foram tratados posteriormente; consultar a secção atual de 04-11.

## PM2 exclusivo e arranque autónomo — 04-11-2026

- [Actions #41812493196](https://github.com/martaxi-boss/VPS/actions/runs/41812493196): instalação física e verificação PM2 7.0.4 dentro de `/srv/projects/telegram-robot-leads/tools/pm2` com dependências próprias, sem tocar no processo ativo.
- [Actions #41813129459](https://github.com/martaxi-boss/VPS/actions/runs/41813129459): cópia de estado/dump PM2 contendo **apenas** `telegram-robot-leads` em `/srv/projects/telegram-robot-leads/.pm2/`, logs privados, fonte da unidade em `deploy/systemd/` e ligação do Ubuntu em `/etc/systemd/system/pm2-telegram-robot-leads.service`. Tudo validado sem reiniciar o bot.
- [Actions #41813373759](https://github.com/martaxi-boss/VPS/actions/runs/41813373759): **`PRIVATE_PM2_CUTOVER_VERIFIED`**. O processo foi transferido de PID `606651` para `687619`, com código `main.py`, intérprete `.venv` e argumentos originais preservados. Logs/PM2_HOME do novo processo são exclusivos da pasta principal. Serviço novo ativo, enabled; `pm2-root.service` antigo parado e disabled; demais serviços estáveis.

**Origem GitHub:** `deploy/systemd/pm2-telegram-robot-leads.service` é o manifesto próprio; `.gitignore` exclui `.pm2/`, `tools/`, `private/`, `data/` e `archive/`. Não versionar dum​​ps, credenciais, sessões, logs ou estados ativos. O fluxo do robô e a lógica operacional não foram alterados nesta operação.

**Restante higienização:** a pasta física histórica `/root/.pm2` pode ter logs antigos de **ambos** os robôs. Nunca movê-la integralmente para a pasta Telegram sem separar os ficheiros pertencentes ao IPTV PN Bot. Validar referências e processos antes de remover o alias `/opt/telegram-robot-leads`. O reboot completo da VPS e o teste de restauro/desinstalação ainda não foram certificados.
