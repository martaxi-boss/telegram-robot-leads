# Descoberta de grupos públicos — Robot Leads

## Objetivo e resultado

O Robot Leads pode pesquisar por tema grupos **públicos** do Telegram com
uma das duas sessões Telethon existentes, sem novo bot, conta ou sessão.
A pesquisa automática funciona dentro do trabalhador PM2 existente, se a
opção TELEGRAM_PUBLIC_DISCOVERY_ENABLED=1 estiver ativa.

Isto **não é extração de membros**: a pesquisa isolada só consulta metadados
públicos, sem enumerar pessoas, enviar mensagens ou adicionar membros ao grupo
do proprietário. Na versão atual do **trabalhador PM2**, quando a descoberta
regional está ativa, os grupos encontrados são encaminhados para tentativas
de **entrada das próprias duas contas**. Isso não significa adicionar outras
pessoas ao grupo do proprietário. Consultar `docs/BOOTSTRAP.md` para as
regras atuais de adesão e deduplicação por conta.

## Configuração

- Cofre preservado: /root/project-secrets/telegram-robot-leads/
- Processo existente: telegram-robot-leads (sem criar outro)
- Catálogo: /var/lib/telegram-robot-leads/public-groups.json, privado,
  com permissões 0600 e escrita atómica
- Temas opcionais: discovery_keywords.txt no cofre, privado com modo 0600,
  uma expressão por linha, máximo seis, comentários iniciados por #
- Sem ficheiro de temas, e só para o grupo de destino atual IPTV, usam-se
  automaticamente os temas iptv portugal e iptv
- A pesquisa pública devolve até 30 resultados por termo; o programa só
  conserva o nome público, título, URL e termo associado de supergrupos
- No modo automático há no máximo uma tentativa de **pesquisa** por conta e
  por dia civil (Europe/Lisbon), evitando consultas repetidas; **não existe
  quota fixa diária para adesões das contas a grupos públicos**
- As restrições de conta/rate limit do Telegram não são contornadas

## Comandos após instalar o novo commit na VPS

~~~bash
# Verificar temas sem chamadas ao Telegram:
python3 scripts/public_group_discovery.py --preview

# Fazer apenas pesquisa pública, sem adicionar membros:
python3 scripts/public_group_discovery.py --once

# Ler o catálogo descoberto, offline:
python3 scripts/public_group_discovery.py --list

# Usar termos concretos numa pesquisa pontual:
python3 scripts/public_group_discovery.py --once --query 'iptv portugal' --query 'iptv'
~~~

No trabalhador normal, `TELEGRAM_PUBLIC_DISCOVERY_ENABLED=1` e
`TELEGRAM_REGIONAL_PUBLIC_DISCOVERY_ENABLED=1` ativam a pesquisa regional
e a sua integração no ciclo do trabalhador, com conta 1 para PT/ES e conta 2
para os demais termos europeus. A conta pode entrar no grupo encontrado
apenas se a plataforma o permitir. O histórico é por **(conta, grupo)**,
não impede a outra conta de estar no mesmo grupo e não altera as regras de
adição autorizada de membros nem ativa mensagens a terceiros.
A documentação atual desta lógica é `docs/BOOTSTRAP.md`.

## Ligação de adesão sem BotFather

O programa produz a ligação pública do TARGET_GROUP. Para o atual
@iptvpncode, o formato é https://t.me/iptvpncode, caso o identificador
permaneça válido e o grupo seja público.

O proprietário pode divulgar a ligação em locais que autorizem essa divulgação.
Os módulos existentes de campanhas e métricas são opcionais e continuam
a exigir um bot dedicado e permissões administrativas para acompanhar os
pedidos de adesão. Não utilizar o bot IPTV nem o Supervisor do Project Leader.

## Validação e estado de implantação

Os testes simulam respostas da pesquisa pública, confirmam a deduplicação,
permissões dos ficheiros, idempotência diária e ausência de recolha de pessoas.

**CI verde não significa serviço remoto ativo.** O arranque preparado para
20/10/2026 foi fixado no commit anterior. O novo código só ficará em execução
após atualizar a versão na VPS, verificar a identidade do código e confirmar
o estado do trabalhador e o catálogo de grupos públicos. As duas sessões
existentes devem permanecer inalteradas.
