# Telegram Robot Leads — comparativo técnico (31-10-2026)

**Âmbito:** motor histórico, motor atual e melhorias pedidas pelo proprietário. A única fonte normativa é [BOOTSTRAP.md](BOOTSTRAP.md); este relatório apenas documenta evidências e próximos testes.

## Fontes
- Histórico: commit [18629988](https://github.com/martaxi-boss/telegram-robot-leads/commit/1862998844782764d263ee8e49a1476a7f86beac), main.py (2.312 linhas), leitura REA [#41249943708](https://github.com/martaxi-boss/VPS/actions/runs/41249943708).
- Atual: scripts/safe_runtime.py, scripts/operation_policy.py e scripts/member_groups.py, commit e9beebb08623d012a2d25ea4ad63b20449f459fa; REA [#41251602824](https://github.com/martaxi-boss/VPS/actions/runs/41251602824).
- VPS: SHA instalado 8298503f7b21466ebf14b9f164f9e103c9c781e7, duas sessões, PM2 online, 3 grupos catalogados, uma adesão a grupo pela conta 2 e **zero ações de membros** em 16.730 eventos observados: [#41250971838](https://github.com/martaxi-boss/VPS/actions/runs/41250971838).

## Comparação comprovada

| Aspeto | Motor antigo | Motor atual | Decisão |
|---|---|---|---|
| Descobrir grupos públicos | Sim, nicho e pesquisas por região | Sim, PT_ES e EU_OTHER | Preservar |
| Entrar em grupos | Sim, por sessão | Sim, histórico por (conta, grupo); ambas podem entrar no mesmo grupo | Preservar |
| Filtrar terceiros | Iteração de participantes, exclusão de administradores, bots, contas eliminadas e perfis sem username | Não extrai membros de grupos terceiros | Não reativar |
| Seleção complementar | Atividade recente, nome/perfil e região | Apenas entradas de pessoas com autorização expressa | Não presumir que username prevê permissão |
| Fila | SQLite users.db com pendentes e estados finais | approved_users.txt com marcadores de autorização e tratamento serial pelo worker | Melhorar a visibilidade |
| Histórico global | IDs estáveis e estados no SQLite | approved_user_ids_done, approved_join_requests_done, pending_member_ids e approved_users_done no estado comum | Reutilizar, não duplicar |
| Pessoa sai do destino | Proprietário afirma que não era readicionada; sem registo histórico recuperado para provar | Resultado antigo persiste; mudança de username e mudança de conta não anulam o ID | Testar reinício e saída |
| Limites/tempo | Intervalos variáveis e tratamento de erros | Horário existente 08:00–22:00, intervalos e reação às restrições reais | Preservar sem disfarces |
| Sucesso | invite_ok, adds_ok e erros de privacidade/contacto | Só considera sucesso confirmado pela resposta (missing_invitees); pendências ambíguas persistem | Preservar |
| Acompanhamento | adder_daily e adder_events | Supervisor passivo, PM2 e diário sanitizado | Acrescentar contagens de fila sem identidades |
| Provas de membros adicionados | Existia capacidade no código; registos antigos indisponíveis | Zero adições observadas nos dados atuais | Não confundir ausência de prova com prova de ausência |

## Requisitos adicionais acordados

A deduplicação de **grupos de origem** é por conta e por grupo. A memória das **pessoas do grupo de destino** é global, para as duas contas e para qualquer grupo de origem. Uma pessoa previamente adicionada não deve voltar a ser adicionada após sair, reaparecer noutro grupo ou mudar o username. A referência estável, quando legítima e disponível, é o ID Telegram. Recusas, desistências e resultados incertos também devem ser preservados sem repetição automática.

A experiência do proprietário é de aproximadamente dez adições por dia por conta, com praticamente nenhuma falha observada. Não foi possível confirmar esses números nos registos atuais. O motor antigo tratava UserPrivacyRestrictedError e UserNotMutualContactError, pelo que o código não comprova um filtro capaz de antecipar todas as permissões.

A simples presença de alguém num grupo público, um username ou atividade recente **não equivale à sua autorização para entrar noutro grupo**. Recuperar apenas funções compatíveis com admissões autorizadas; não voltar a recolher indiscriminadamente membros de terceiros nem a disfarçar operações para ultrapassar restrições Telegram.

## Próxima fase de implementação

1. **Visibilidade da fila autorizada no mesmo worker e supervisor:** configured (entradas autorizadas), waiting (pendentes), recorded (resultado conhecido), uncertain (resultado remoto ambíguo), global_recorded_ids (IDs históricos únicos). Mostrar somente totais agregados, sem usernames, telefones ou IDs.
2. **Testes de regressão da memória comum:** após adição, saída voluntária, reinício e mudança de alias, a segunda conta não pode gerar outra tentativa para o mesmo ID.
3. **Resultados comprovados:** testar que missing_invitees, restrições de privacidade e retornos incertos não são contabilizados como entradas bem-sucedidas.
4. **Dados históricos:** se for encontrado backup antigo de users.db/telethon_adder.log, primeiro verificar e comparar em modo só de leitura; não importar nem apagar nada automaticamente.
5. **Governança:** testes, diff e PR antes de qualquer deploy. Não alterar a ponte, as sessões, o estado privado ou outros projetos.

## Resultado desta passagem

**Comparação feita e requisitos detalhados.** A tentativa de edição do runtime pelo REA foi bloqueada antes da execução por uma verificação de segurança da ferramenta; por isso **não há nova funcionalidade de fila implementada ou testada nesta passagem**. O código em produção permanece inalterado.
