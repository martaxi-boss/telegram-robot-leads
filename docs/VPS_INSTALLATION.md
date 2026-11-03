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
- O ativador de 20-10-2026 e as duas unidades systemd foram movidos para `/srv/projects/telegram-robot-leads/archive/legacy/20261020-activation/`. O temporizador expirado ficou desativado. [Prova #41723648731](https://github.com/martaxi-boss/VPS/actions/runs/41723648731).
- Os quatro workflows historicos Telegram e o ativador de origem em `martaxi-boss/VPS` foram arquivados em `docs/archive/legacy-telegram-202610/`, fora das pastas executaveis. O deploy antigo tinha caminhos e SHAs desatualizados. [Commit 823a072d](https://github.com/martaxi-boss/VPS/commit/823a072dbb3377eca48b276e5d257a32960fe96f).
- A ligacao `/opt/telegram-robot-leads` so deve ser retirada apos comprovacao de ausencia de referencias de arranque, scripts e processos.
- A desinstalacao independente exige parar apenas o bot correspondente e seguir procedimento que exporte/guarde os dados privados, sem alterar o outro robot.

## Regra permanente

Cada projeto GitHub tem codigo, runtime, fornecedores e estado exclusivos dentro da sua propria pasta. O Linux e o gestor de processos podem exigir ficheiros de integracao em caminhos padrao; inventariar esses ficheiros por proprietario e garantir que a desinstalacao de um projeto nao interrompe outro. **Nao alterar a logica operacional do Telegram Robot Leads durante tarefas de organizacao.**

## Auditoria cruzada final

A verificacao real [GitHub Actions #41724074992](https://github.com/martaxi-boss/VPS/actions/runs/41724074992) confirmou os dois bots online com os mesmos PID, duas sessoes presentes em `private/`, estado em `data/`, sete raizes reais de projeto em `/srv/projects/` e servicos principais ativos. O PM2 global permanece uma pendencia de isolamento; o REA FINAL e o Codex tambem continuam fisicamente fora das pastas canonicas e nao foram fundidos com outros projetos.
