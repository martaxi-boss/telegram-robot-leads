/**
 * Telegram Robot Leads — canonical safe PM2 runtime.
 *
 * Public discovery uses two existing authorized accounts for regional group
 * metadata searches only. The worker never enumerates third-party members
 * or auto-adds people from search results.
 */
const cwd = "/srv/projects/telegram-robot-leads";

module.exports = {
  apps: [
    {
      name: "telegram-robot-leads",
      cwd,
      script: "main.py",
      interpreter: "/srv/projects/telegram-robot-leads/.venv/bin/python",
      args: "--loop --interval 60 --vault /srv/projects/telegram-robot-leads/private",
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      env: {
        TELEGRAM_OPERATION_STATE:
          "/srv/projects/telegram-robot-leads/data/operation-state.json",
        TELEGRAM_TZ: "Europe/Lisbon",
        TELEGRAM_GROUP_ALLOWLIST: "group_allowlist.txt",
        TELEGRAM_APPROVED_USERS: "approved_users.txt",
        TELEGRAM_PUBLIC_DISCOVERY_ENABLED: "1",
        TELEGRAM_REGIONAL_PUBLIC_DISCOVERY_ENABLED: "1",
        TELEGRAM_EVENT_JOURNAL:
          "/srv/projects/telegram-robot-leads/data/supervisor-events.jsonl",
      },
    },
  ],
};
