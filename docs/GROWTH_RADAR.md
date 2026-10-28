# Growth Radar — Telegram Robot Leads (REA 6.8.0)

## Objetivo

Adicionar uma camada de **inteligência de aquisição para o grupo @iptvpncode**
sem outro daemon, sem novos logins, sem novos bots e sem tocar em outros
projetos da VPS. O Radar aproveita o catálogo de grupos **públicos** já
descobertos pelo Telethon e a base de eventos de adesão do próprio projeto.

O Radar é **offline e read-only**. Não extrai participantes de grupos terceiros,
não envia mensagens, não força a entrada de pessoas, não inventa contagens de
membros, não simula comportamento humano e não contorna restrições do Telegram.

## Referências de arquitetura (ideias, sem copiar código)

- [Mikonila/Referal_system_bot](https://github.com/Mikonila/Referal_system_bot):
  campanhas por origem, relatórios e fluxos de aceitação
- [itsAPK/Telegram-Referral-Bot](https://github.com/itsAPK/Telegram-Referral-Bot):
  painel de origem e classificação de campanhas; exemplo antigo, **não** usar
  configurações ou credenciais incluídas no repositório
- [AaronPemberton/Telegram-Referral-Bot](https://github.com/AaronPemberton/Telegram-Referral-Bot):
  referências e atividade; arquitetura antiga e requisitos de segurança a
  reavaliar
- [DeepBlue-dot/GrowBot](https://github.com/DeepBlue-dot/GrowBot):
  diferenciação entre referência, adesão confirmada e permanência;
  apenas ideias, código de terceiros **não copiado**
- [Exey/HypeStats](https://github.com/Exey/HypeStats):
  comparação de canais e potenciais trocas de divulgação, sem importar
  os dados de participantes de terceiros

As ferramentas existentes `scripts/growth_store.py`,
`scripts/growth_tracker.py`, `scripts/organic_growth.py` e
`scripts/public_group_discovery.py` continuam a ser as fontes canónicas.
Não criar outro poller Bot API nem reutilizar o bot de outro projeto.

## Execução local na VPS (sem Telegram ou alterações)

```bash
cd /opt/telegram-robot-leads
.venv/bin/python scripts/growth_radar.py
.venv/bin/python scripts/growth_radar.py --top 20
```

A saída JSON inclui:

- `public_groups_ranked`: grupos públicos para revisão e propostas de
  colaboração **apenas quando os administradores autorizarem**;
  `metadata_relevance_score` é relevância nominal, NÃO dimensão,
  qualidade ou audiência comprovada
- `campaign_measurement`: entradas realmente observadas nos últimos 7 e 30
  dias, segundo a base do bot de métricas existente; sem base, o resultado é
  `NOT_CONFIGURED` e a contagem de entradas é `null`, nunca zero inventado
- `next_steps`: ações de aquisição e de medição recomendadas
- `telegram_requests=0`, `messages_sent=0`, `users_enumerated=0`

Ficheiros existentes, sem copiar dados:

- Grupos públicos: `/var/lib/telegram-robot-leads/public-groups.json`
- Métricas do serviço já existente, quando disponível:
  `/opt/telegram-leads-optin/growth_metrics.sqlite3`

O relatório exige bases privadas pertencentes ao utilizador que o executa,
rejeita links simbólicos e ficheiros SQLite com permissões inseguras. Usa
`mode=ro`; não cria bases de dados nem modifica eventos. Por predefinição,
se a base não existir, o serviço mantém-se operável e assinala que não tem
provas de adesões. Nomes de campanhas são metadados configurados pelo
administrador, nunca números de telefone ou nomes de participantes.

## Da descoberta à aquisição

1. Pesquisar nomes e temas de grupos públicos do nicho, com a descoberta
   existente e sem enumerar participantes.
2. Usar o Radar para priorizar possíveis parcerias relevantes. A descoberta
   de um grupo não dá direito a escrever lá ou adicionar pessoas.
3. Negociar e publicar a divulgação apenas em canais próprios ou em grupos
   onde o administrador aceitou a colaboração; usar uma campanha nomeada
   por origem.
4. Medir pedidos e entradas efetivas pelos eventos oficiais do **nosso**
   grupo. Priorizar origens que produzem adesões observadas, não cliques,
   números inventados ou seguidores falsos.

As duas contas Telegram existentes são preservadas. A ativação do motor
orgânico continua dependente da configuração privada `growth_model.json`
e das permissões administrativas do destino; este relatório não substitui
essa autorização nem resolve a falta de audiência externa.

## Verificação

```bash
python -m unittest tests.test_growth_radar -v
python -m unittest discover -s tests -v
```

A validação GitHub Actions certifica apenas código e testes. Para afirmar
que houve entradas reais no grupo, são necessários eventos `chat_member`
ou equivalentes observados e um sistema de medição operacional. Nenhum
resultado simulado pode substituir essas provas.

## Estado de instalação verificado (28/10/2026)

O Radar foi integrado no repositório Telegram pelo PR #38, no commit
`5ade747d82066515bc0032ca53639b13670ccc36`, mas **ainda não foi
comprovada a sua instalação na VPS**. A última instalação validada na
VPS foi da versão `7c0ef8a1d9be5d18568a133bcfdb79e4e0bcd9aa`
([execução central 40609597231](https://github.com/martaxi-boss/VPS/actions/runs/40609597231)).
A presença do ficheiro Python no GitHub não significa que esteja no servidor.

Para qualquer atualização, usar **exclusivamente** o workflow existente
`martaxi-boss/VPS/.github/workflows/telegram-leads-vps-stage-20261019.yml`
com a credencial SSH já configurada no repositório VPS. O pacote do
workflow precisa de incluir `scripts/growth_radar.py`, e os parâmetros
`TARGET_SHA` e `EXPECTED_INSTALLED` precisam de refletir os SHAs
realmente verificados. Não criar novo workflow nem nova credencial SSH
no repositório Telegram; consultar
[`TELEGRAM_ONLY_INSTALLATION.md`](TELEGRAM_ONLY_INSTALLATION.md).
