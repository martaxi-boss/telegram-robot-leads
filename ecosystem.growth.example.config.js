/**
 * OPTIONAL and INACTIVE until an operator explicitly runs PM2 start.
 * Tracks voluntary Telegram group joins only; it does NOT run legacy main.py.
 *
 * Before starting: verify bot token isolation, permissions and group with:
 *   python3 scripts/growth_tracker.py --check
 * This assumes the existing repo checkout has a working .venv/bin/python.
 */
module.exports = {
  apps: [
    {
      name: 'TELEGRAM-LEADS-METRICS',
      cwd: __dirname,
      script: './.venv/bin/python',
      args: ['-u', 'scripts/growth_tracker.py', '--run'],
      interpreter: 'none',
      watch: false,
      autorestart: true,
      min_uptime: '30s',
      max_restarts: 3,
      exp_backoff_restart_delay: 10000,
      kill_timeout: 5000,
      env: {
        PYTHONUNBUFFERED: '1',
      },
    },
  ],
};
