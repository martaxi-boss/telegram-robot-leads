/**
 * Telegram Robot Leads — canonical safe PM2 runtime.
 *
 * No legacy discovery/scraping/human-mimic configuration is accepted here.
 * The worker reads only the protected project vault plus explicit operator
 * allowlists and approved/consented usernames.
 */
const cwd = "/opt/telegram-robot-leads";

module.exports = {
  apps: [
    {
      name: "telegram-robot-leads",
      cwd,
      script: "main.py",
      interpreter: "/opt/telegram-robot-leads/.venv/bin/python",
      args: "--loop --interval 60 --vault /root/project-secrets/telegram-robot-leads",
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      env: {
        TELEGRAM_OPERATION_STATE:
          "/var/lib/telegram-robot-leads/operation-state.json",
        TELEGRAM_TZ: "Europe/Lisbon",
        TELEGRAM_GROUP_ALLOWLIST: "group_allowlist.txt",
        TELEGRAM_APPROVED_USERS: "approved_users.txt",
        TELEGRAM_PUBLIC_DISCOVERY_ENABLED: "1",
        TELEGRAM_EVENT_JOURNAL:
          "/var/lib/telegram-robot-leads/supervisor-events.jsonl",
      },
    },
  ],
};
