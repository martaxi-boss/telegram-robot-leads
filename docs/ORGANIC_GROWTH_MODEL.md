# Modelo de crescimento autónomo — Telegram Robot Leads

## O problema observado em 27/10/2026

A instalação da VPS apresentou duas sessões Telegram legíveis offline e dois
grupos públicos no catálogo, mas o ciclo observado não tinha nenhuma ação de
adição autorizada. Descobrir grupos de terceiros **não cria uma fila de membros
autorizados**. A fonte na VPS (\`d8736bd\`) também diferia de \`main\` e a
configuração usava credenciais Android de fallback. Não existe prova de
qualquer nova adesão no ciclo consultado.

Este modelo cria dois caminhos com consentimento explícito, sem copiar listas
de pessoas de grupos alheios, evitar proteções do Telegram ou imitar humanos:

1. **Promoção no teu próprio canal**: até uma publicação por dia com uma
   ligação de adesão voluntária ao grupo. Só publica num canal **broadcast**
   explicitamente declarado pelo proprietário. Verifica direitos de
   proprietário ou administrador com permissão de publicar.
2. **Pedidos de adesão ao teu grupo**: verifica apenas a fila de **pedidos
   pendentes feitos pelas próprias pessoas** ao grupo de destino configurado.
   Confirma direitos administrativos para admitir membros e aprova um pedido
   por ciclo, sujeito aos limites existentes e entre 08:00 e 22:00 em Portugal.
   Nunca consulta membros de grupos terceiros.

As duas funções usam o **worker já existente**, com o mesmo lock e os mesmos
registos privados. Não criam outro bot, sessão, projeto, daemon nem processo
PM2. A opção de divulgação é facultativa e a admissão de pedidos é independente.

## Ativação explícita e privada

A funcionalidade está **desligada por defeito**. Para a ativar, o proprietário
deve criar este ficheiro **apenas** no cofre do Telegram Robot Leads:

\`/root/project-secrets/telegram-robot-leads/growth_model.json\`

Exemplo ilustrativo (o canal é FICTÍCIO; substituir por um canal realmente teu):

~~~json
{
  "schema": 1,
  "target_group": "@iptvpncode",
  "approve_join_requests": true,
  "owned_channel": "@MeuCanalDeExemplo",
  "publish_in_owned_channel": true,
  "publisher_account": 1
}
~~~

O ficheiro tem de ser regular, sem symlink, propriedade do utilizador que
executa o worker e modo \`0600\`, num diretório privado. É proibido colocar
credenciais neste ficheiro ou no GitHub. O grupo tem de corresponder exatamente
ao TARGET_GROUP configurado no cofre. Para aprovar pedidos **sem** publicações,
usar \`"owned_channel": null\` e \`"publish_in_owned_channel": false\`.

**Não colocar o nome de um grupo público de terceiros como owned_channel**.
O código recusa grupos e só publica em canais broadcast com direitos verificados.
Não enviar textos a membros de terceiros, não fazer scraping de participantes.

Um ficheiro ausente causa estado \`NOT_CONFIGURED\` sem contactos extra ao
Telegram. Ficheiros incorretos fazem o worker falhar de forma explícita,
sem ativar operações por omissão.

## Funcionamento e limitações

- A promoção começa a poder ocorrer após as **12:00**, no máximo uma vez por
  dia por canal. Textos originais variam entre três mensagens transparentes,
  sem fingir ser uma pessoa. Não há cadência destinada a contornar filtros.
- O controlo de pedidos é, no máximo, uma pesquisa de 30 em 30 minutos;
  apenas a fila de adesões voluntárias do **teu** grupo é consultada. Se uma
  pessoa pediu entrada, pode ser aprovada apenas uma por ciclo, sem ultrapassar
  o teto combinado de **10 ações por conta e 20 por projeto** (adições e
  aprovações partilham os limites).
- A conta 1 trata dos pedidos; a conta do canal é explicitamente escolhida
  (\`publisher_account\` = 1 ou 2). Nenhuma restrição provoca a troca automática
  de conta para a contornar.
- Estados \`pending\` são escritos **antes** de pedidos remotos. Uma resposta
  ambígua bloqueia a repetição automática até reconciliação manual; não apagar
  esses registos para contornar o bloqueio.
- Aprovação confirmada pelo servidor **não equivale a evento de membro
  observado**. Para confirmar adesões efetivas e atribuir campanhas, usar
  eventos de entrada com um bot de métricas dedicado (já existente no projeto,
  mas anteriormente inativo por falta de token exclusivo).
- Não há garantias de crescimento: se não houver audiência no canal,
  pedidos de adesão ou autorizações, as contagens permanecerão em zero.
- Sessões e permissões reais têm de ser verificadas na VPS antes da ativação.

## Consulta e teste

O modelo surge no relatório de cada ciclo em \`organic_growth\`, sem divulgar
usernames dos participantes. No stdout do PM2 estão apenas os indicadores
\`owned_channel_posts\` e \`join_requests_approved\` e códigos de estado.

Antes da instalação na VPS, executar CI na PR da alteração:
\`python -m unittest discover -s tests -v\`. A verificação online posterior
deve usar **apenas** o ambiente do Telegram Robot Leads; não iniciar um novo
PM2 através de utilizador REA diferente. O relatório do projeto consulta o
PM2 apenas com \`--with-pm2\` e sob o utilizador proprietário do daemon.

## Preparação sem qualquer ação remota

É possível validar a configuração privada sem mensagens, adições ou leitura
de contas através de \`organic_growth.preview(vault, target)\`, invocado
programaticamente pelos testes. O modelo nunca é ativado por CI.
