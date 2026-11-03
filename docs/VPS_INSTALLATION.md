# Telegram Robot Leads — instalação Ubuntu VPS (inventário real)

**Fonte:** `martaxi-boss/telegram-robot-leads`. **Diretório de execução atual:** `/opt/telegram-robot-leads` (nome igual ao repositório). PM2: `telegram-robot-leads` online na verificação de 03-11-2026.

## Componentes da pasta do projeto

- Código, scripts e documentação: `/opt/telegram-robot-leads/`.
- Ambiente Python ativo: `/opt/telegram-robot-leads/.venv/`.
- Ferramentas Opt-in: `/opt/telegram-robot-leads/optin/`, movidas de `/opt/telegram-leads-optin`. Referências atualizadas no runtime e no repositório.
- Ambiente Python antigo: `/opt/telegram-robot-leads/archive/previous-telegram-python-env/`, anteriormente em `/home/ubuntu/telegram-leads-venv`. **Não é o ambiente ativo** e contém scripts com caminhos absolutos antigos: não executar sem reconstruir.

## Componentes ainda externos — migração pendente

- Dados operacionais: `/var/lib/telegram-robot-leads/`.
- Configurações privadas e sessões: `/root/project-secrets/telegram-robot-leads/`.
- Configuração do processo: PM2 global (ficheiros do PM2 em `/root/.pm2/`).
- Outras configurações systemd/timers, quando presentes, precisam de ser associadas ao mesmo projeto.

Os dados e as sessões são privados e **não podem ser colocados no GitHub**. O repositório guarda apenas código, manifesto e instruções sem segredos.

## Estado e desinstalação

Reorganização **parcial**: Opt-in e ambiente antigo já estão dentro do diretório. Reunião dos dados e sessões privadas não concluída; procedimento de desinstalação/reinstalação ainda não certificado. Não confundir com `iptvpn-bot`, um robô diferente. Evitar alterações ao motor lógico e não apagar as duas sessões de contas sem preservação.

Auditorias: [Opt-in PASS #41699135050](https://github.com/martaxi-boss/VPS/actions/runs/41699135050) e [ambiente antigo PASS #41699620015](https://github.com/martaxi-boss/VPS/actions/runs/41699620015).
