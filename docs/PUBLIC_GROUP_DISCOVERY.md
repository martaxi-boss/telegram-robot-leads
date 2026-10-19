# Descoberta de grupos públicos — Robot Leads

## Objetivo e resultado

O Robot Leads pode pesquisar por tema grupos **públicos** do Telegram com
uma das duas sessões Telethon existentes, sem novo bot, conta ou sessão.
A pesquisa automática funciona dentro do trabalhador PM2 existente, se a
opção TELEGRAM_PUBLIC_DISCOVERY_ENABLED=1 estiver ativa.

Isto **não é extração de membros**: não enumera pessoas nem os respetivos
IDs, não envia mensagens, não adere aos grupos encontrados e não adiciona
terceiros ao grupo do proprietário. A adesão tem de ser voluntária.

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
- No modo automático há no máximo uma tentativa por dia civil em
  Europe/Lisbon; uma falha não gera repetições infinitas
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

No trabalhador normal a opção TELEGRAM_PUBLIC_DISCOVERY_ENABLED=1 inicia
a pesquisa diária em conjunto com os ciclos regulares. Não altera as regras
de adição autorizada de membros nem ativa envios de mensagens.

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
