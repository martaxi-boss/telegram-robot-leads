# Modelo de entrada de membros conforme regras oficiais do Telegram

Revisão documental: 31 de outubro de 2026. Âmbito exclusivo: **Telegram Robot Leads**.

## Fontes oficiais e interpretação operacional

- [Termos gerais](https://telegram.org/tos) e [FAQ de spam](https://telegram.org/faq_spam): não contactar nem adicionar pessoas a grupos sem uma expectativa legítima de participação; `@username` não é consentimento.
- [Termos de utilização da API](https://core.telegram.org/api/terms): respeitar a privacidade e o consentimento dos utilizadores, usar credenciais API próprias e não treinar sistemas de IA com dados do Telegram.
- [Convites e pedidos de entrada](https://core.telegram.org/api/invites): os administradores podem gerar links com `request_needed` e aprovar pedidos explícitos.
- [messages.exportChatInvite](https://core.telegram.org/method/messages.exportChatInvite): criar um link cuja adesão exige aprovação; não revogar automaticamente o convite principal.
- [messages.hideChatJoinRequest](https://core.telegram.org/method/messages.hideChatJoinRequest): aprovar ou rejeitar um pedido específico do próprio grupo.
- [Bot API](https://core.telegram.org/bots/api): fluxo equivalente de pedidos, mas **este projeto usa as duas contas Telethon já existentes**, sem criar outro bot.

Os limites exatos de abuso e de FloodWait **não são garantidos** pelo Telegram. Nenhum intervalo ou quota fixa assegura ausência de restrições. Respeitar sempre erros reais, suspender a conta afetada, não trocar para outra conta para contornar a restrição.

## Funcionamento do projeto

1. A descoberta de grupos públicos do nicho continua repartida: conta 1 pesquisa Portugal/Espanha; conta 2 pesquisa outras regiões europeias. O catálogo contém **metadados de grupos**, não membros.
2. O sistema confirma separadamente os grupos em que cada conta já é membro; nunca confunde descoberta com adesão.
3. No grupo do proprietário `@iptvpncode`, a conta 1 administra um **link exclusivo de pedidos de adesão voluntária**, denominado `Leads voluntary request`.
4. A função `ensure_voluntary_request_link` de `scripts/organic_growth.py`, executada pontualmente pelo operador, verifica direitos administrativos, procura uma ligação anterior com o mesmo título e **só cria outra se não existir**. Não corre em cada ciclo.
5. O link completo é mantido no cofre privado `/root/project-secrets/telegram-robot-leads/voluntary_group_join_link.json` (acesso do proprietário), não no GitHub nem em relatórios públicos.
6. O trabalhador PM2 `telegram-robot-leads`, já existente, valida os pedidos enviados **pelos próprios interessados** ao grupo do proprietário. Verifica permissões administrativas; aprova no máximo um pedido por ciclo, com controlo persistente de estado, de duplicados e de restrições. O registo distingue **aprovação aceite** de **adesão efetivamente observada**.
7. O canal do proprietário e os grupos de terceiros **não recebem mensagens automáticas** por esta função. A publicação do link deve ocorrer onde o proprietário esteja autorizado a fazê-lo, por iniciativa própria ou por uma campanha expressamente autorizada.
8. Não são feitas listagens de participantes de grupos de terceiros, não se envia publicidade privada não solicitada e não se usa simulação humana para evitar bloqueios. `@username` não é necessário para um pedido legítimo de adesão.

## Pré-condições e limites honestos

- As duas sessões privadas permanecem no cofre existente; não criar sessões ou processos adicionais.
- A conta 1 precisa de ter `can_invite_users` no próprio grupo, confirmado em execução real.
- O utilizador tem de **abrir e usar o link com pedido de aprovação**. Um grupo público também pode ter acesso direto; um link especial não altera automaticamente essa opção.
- O worker só pode aprovar pedidos presentes na fila oficial e durante o horário e limites próprios do projeto. Sem pedidos, o resultado correto é zero.
- A função `ensure_voluntary_request_link` não publica o link, não o devolve nos eventos do supervisor e não adiciona qualquer pessoa.
- Se uma operação de criação do link terminar com resultado desconhecido, inspecionar os links do grupo antes de repetir. Uma ligação revogada pelo proprietário não é regenerada automaticamente.
- Erros de permissão, limites reais, respostas incompletas e estado inconsistente bloqueiam ações, não desencadeiam mecanismos de evasão.

## Verificação

Executar `python -m unittest discover -s tests -v` para testar criação, reutilização, deduplicação, permissões, expiração, segurança do ficheiro e regressões do modelo. Validar separadamente a ligação real, os dois números autenticados, a fila de adesões e o PM2, sem atribuir falsas entradas de membros.

Para partilhar a ligação, abrir o grupo no Telegram: **Editar / Gerir grupo → Ligações de convite** e selecionar **Leads voluntary request**. A experiência exata depende da versão da aplicação Telegram.

## Dois administradores, uma fila oficial

As duas contas Telethon existentes têm direitos administrativos no grupo. O único trabalhador distribui aprovações de pedidos voluntários pela conta com menos ações de membros já autorizadas no dia, com desempate pela conta 1. Regista a conta usada para cada aprovação sem divulgar dados de utilizadores.

A fila, o controlo de duplicados, a janela e o histórico são **comuns**. Uma restrição real em qualquer conta suspende as aprovações; a outra conta nunca é usada automaticamente para ultrapassar bloqueios ou FloodWait. Aprovação aceite não prova entrada efetiva.
