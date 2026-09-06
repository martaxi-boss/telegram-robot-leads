/**
 * PM2 — Não apagues "const cwd"; troca só o caminho se a pasta no VPS for outra.
 * Credenciais Telegram: .env (preferido) ou telegram_api.json — vê telegram_api.json.example.
 * Se my.telegram.org não der: TELEGRAM_USE_PUBLISHED_ANDROID_API=1 (= par público app Android OSS).
 * Se no PM2 ainda passares TELEGRAM_API_* placeholders, põe DOTENV_OVERRIDE: "1" em env.
 */
const cwd = "/root/TELEGRAM-IPTVPN";

module.exports = {
  apps: [
    {
      name: "TELEGRAM-IPTVPN",
      cwd,
      script: "main.py",
      interpreter: ".venv/bin/python",
      env: {
        DOTENV_OVERRIDE: "1",
        TARGET_GROUP: "@iptvpncode",
        MAX_ADDS_PROJECT_PER_DAY: "100",
        TELEGRAM_SCRAPE_RELAX_NAME_FILTER: "1",
        TELEGRAM_PRIORITY_SCRAPE_GROUPS:
          "IPTVCLASES,iptvcccampt,stremioEs,iptvgermanyvip,iptvromaniatv,iptvpolskie,iptvgermanquality",
      },
    },
  ],
};
