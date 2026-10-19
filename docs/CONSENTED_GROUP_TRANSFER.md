# Migração com consentimento entre grupos — Robot Leads

Esta funcionalidade é **opcional**, não altera o worker PM2, as sessões, o motor
de pesquisa pública ou os dois bots de IPTV/Supervisor. Não arranca sozinha.

## As duas etapas

1. **Verificar membros de um grupo de origem administrado pelo operador.**
   O programa verifica online que a conta existente é administradora do
   supergrupo de origem. Consulta **apenas** os usernames para os quais o
   titular declarou consentimento expresso no ficheiro privado. Não percorre
   os participantes do grupo, não recolhe a lista geral e não contacta ninguém.
   Rejeita bots, administradores e contas eliminadas.
2. **Colocar os membros elegíveis na fila de adição já existente.**
   Apenas por comando confirmado, adiciona entradas CONSENTED a
   approved_users.txt, sem apagar linhas anteriores, com gravação atómica
   e permissões 0600. **Não faz nenhuma adição de utilizadores durante o
   comando.** O trabalhador normal executa adições posteriormente, sujeito
   aos limites horários, quotas diárias e recusas do Telegram.

## Pré-requisitos

- Ser administrador do supergrupo de origem. A confirmação é feita
  online; um grupo público de terceiros sem esse direito não serve.
- Ter consentimento individual realmente documentado. A marcação
  CONSENTED e a referência no ficheiro são **declarações do operador**,
  não prova criptográfica nem verificação do texto da mensagem.
  O titular deve ter realmente aceite a transferência.
- Usar credenciais próprias de aplicação Telegram na pasta privada do
  projeto. O fallback Android publicado é **bloqueado** neste comando
  para não iniciar consultas novas em produção com essa configuração.
- Não editar ficheiros de sessão nem reutilizar o bot IPTV ou Supervisor.

## Ficheiro de opt-ins

Guardar no cofre já existente:

/root/project-secrets/telegram-robot-leads/migration_optins.txt

Exemplo **fictício** do formato (não cria qualquer utilizador real):

~~~text
# username | consentimento | grupo origem | data ISO | referência operador
@UtilizadorExemplo|CONSENTED|@GrupoAdministrado|2026-10-20|dm:12345
~~~

Cada referência dm:<número> ou joinreq:<número> deve corresponder ao
registo real de autorização do utilizador; não é recolhida por este script.
O script valida datas com máximo de 90 dias e até 10 pessoas por grupo
numa invocação. Guardar o ficheiro com permissões privadas 0600.

## Comandos depois de distribuir esta revisão

No checkout do projeto existente:

~~~bash
# 1. Pré-visualização offline: apenas valida registos privados.
.venv/bin/python scripts/consented_group_transfer.py \
  --source @GrupoAdministrado --preview

# 2. Verificação de administração e participação real, só leitura MTProto.
.venv/bin/python scripts/consented_group_transfer.py \
  --source @GrupoAdministrado --verify

# 3. Colocar apenas opt-ins verificados na fila existente (sem adicionar agora).
.venv/bin/python scripts/consented_group_transfer.py \
  --source @GrupoAdministrado --queue --confirm-consented-transfer
~~~

O comando não lista usernames nem identificadores no output: apenas
contagens, estado e bloqueios. O ficheiro approved_users.txt mantém-se no
cofre original. O worker atual reconhece @username|CONSENTED e continua
a processar sob a política existente.

## Limitações e aceitação

- Este é um fluxo de **migração voluntária administrada**, não extração
  indiscriminada de membros de terceiros nem adição não solicitada.
- Um operador mal-intencionado poderia escrever falsamente CONSENTED.
  O software não pode provar por si só a vontade de outra pessoa; o
  consentimento tem de existir e ser auditável fora da ferramenta.
- A API pode negar visibilidade ou impedir adições mesmo após os checks.
  O processo para em erros não previstos, sem trocar para a segunda conta
  para escapar a restrições.
- Os testes do PR usam clientes fictícios offline; não há grupos de origem
  nem consentimentos reais fornecidos nesta conversa. **Não executar
  --queue na VPS antes de verificar esses dois pré-requisitos.**
- Nenhuma ação real é ativada pelo merge no GitHub. O staging VPS está
  fixado numa versão específica e esta mudança exige distribuição
  separada após autorização e validação.
