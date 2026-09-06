import asyncio
import os
import random
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys
import shutil
import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

class EstadoBot:
    def __init__(self, filename="estado_bot.json"):
        # Put it in _SCRIPT_DIR to be sure
        self.filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        self.lock = asyncio.Lock()
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    async def _save(self):
        async with self.lock:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)

    async def get_status(self, user_id):
        return self.data.get(str(user_id), {}).get("status")

    async def set_status(self, user_id, status, session=None):
        uid = str(user_id)
        if uid not in self.data:
            self.data[uid] = {}
        self.data[uid]["status"] = status
        self.data[uid]["updated_at"] = datetime.datetime.now().isoformat()
        if session:
            self.data[uid]["session"] = session
        await self._save()

estado_bot = EstadoBot()
from telethon import TelegramClient, errors
from telethon.utils import parse_phone
from telethon.tl.types import (
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    Channel,
    ChannelParticipantsAdmins,
)
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.contacts import SearchRequest
import aiosqlite
from langdetect import detect, LangDetectException

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_DOTENV_PATH = os.path.join(_SCRIPT_DIR, ".env")
try:
    from dotenv import load_dotenv

    # DOTENV_OVERRIDE=1 (shell/PM2): .env sobrepõe env já herdado — útil se o processo vier
    # com variáveis placeholders de um ecossistema antigo em vez de ler o par real do disco.
    _override = os.environ.get("DOTENV_OVERRIDE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    load_dotenv(ENV_DOTENV_PATH, override=_override)
except ImportError:
    pass

USERS_DB = os.path.join(_SCRIPT_DIR, "users.db")
LOG_FILE = os.path.join(_SCRIPT_DIR, "telethon_adder.log")
SQLITE_BUSY_TIMEOUT = float(os.environ.get("SQLITE_BUSY_TIMEOUT", "30"))

# Uma conta de cada vez a fazer convite (mesma API / IP): reduz "Too many requests" entre conta1+conta2.
INVITE_SERIAL_LOCK = asyncio.Lock()

STALE_PROCESSING_SEC = int(os.environ.get("STALE_PROCESSING_SEC", str(45 * 60)))

_MIN_SESSION_BYTES = 256  # ficheiro .session Telethon(SQLite) realista é bem maior; isto só rejeita vazio/corrupto óbvio


def _session_file_path(session_name: str) -> str:
    return os.path.join(_SCRIPT_DIR, f"{session_name}.session")


def _has_usable_session_file(session_name: str) -> bool:
    try:
        p = _session_file_path(session_name)
        return os.path.isfile(p) and os.stat(p).st_size >= _MIN_SESSION_BYTES
    except OSError:
        return False


def _env_bool(key: str, default: bool = True) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return default
    try:
        return int(str(v).strip())
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return default
    try:
        return float(str(v).strip())
    except ValueError:
        return default


def _disk_free_bytes(path: str) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return -1


def open_users_db():
    """SQLite com timeout de bloqueio (duas contas + PM2 = menos 'database is locked')."""
    return aiosqlite.connect(USERS_DB, timeout=SQLITE_BUSY_TIMEOUT)


# ==========================================
# CONFIGURAÇÕES (credenciais: ficheiro .env — vê .env.example)
# ==========================================
def _validate_account_phones(accounts: list) -> None:
    """E.164 válido em 'phone' OU ficheiro .session credível (migração / login já feito)."""
    for acc in accounts:
        session = acc.get("session", "?")
        phone = acc.get("phone")
        has_sess = _has_usable_session_file(session)
        if phone is None or not str(phone).strip():
            if not has_sess:
                raise SystemExit(
                    f"Config: conta {session!r} sem 'phone' e sem {_session_file_path(session)!r}. "
                    "Preenche telefone E.164 ou copia o .session do servidor antigo."
                )
            print(
                f"Aviso: conta {session!r} sem 'phone' no JSON — existe .session; arranque assume sessão já autorizada.",
                file=sys.stderr,
            )
            continue
        if not parse_phone(phone):
            if has_sess:
                print(
                    f"Aviso: conta {session!r}: telefone no JSON não é E.164 válido, mas existe .session — "
                    "a assumir sessão já autorizada (corrige accounts.json quando puderes).",
                    file=sys.stderr,
                )
                continue
            raise SystemExit(
                f"Config: telefone inválido para a sessão {session!r}: {phone!r} "
                f"(e não há .session em {_session_file_path(session)!r}).\n"
                "Usa E.164 só com dígitos (ex.: +351912345678) ou copia os .session do servidor antigo."
            )


def _load_accounts():
    raw = os.environ.get("TELEGRAM_ACCOUNTS_JSON")
    if raw and raw.strip():
        accounts = json.loads(raw)
    else:
        ap = os.path.join(_SCRIPT_DIR, "accounts.json")
        if os.path.isfile(ap):
            with open(ap, encoding="utf-8") as fp:
                accounts = json.load(fp)
        else:
            raise SystemExit(
                "Config: cria accounts.json (copia accounts.json.example) ou define TELEGRAM_ACCOUNTS_JSON."
            )
    _validate_account_phones(accounts)
    return accounts


# Par PUBLICADO no código-fonte do Telegram for Android (BuildVars.APP_ID / APP_HASH).
# Uso só para contornar my.telegram.org; o Telegram espera desenvolvedores a registarem
# a própria app — ver https://core.telegram.org/api/obtaining_api_id
_ANDROID_OSS_PUBLISHED_API_ID = 4
_ANDROID_OSS_PUBLISHED_API_HASH = "014b35b6184100b085b0d0572f9b5103"


def _telegram_api_credentials():
    if _env_bool("TELEGRAM_USE_PUBLISHED_ANDROID_API", False):
        print(
            "Arranque: TELEGRAM_USE_PUBLISHED_ANDROID_API=1 → credenciais = APP_ID / APP_HASH "
            "do repositório Android open-source (telegram.org GPLv2). Preferível usar o "
            "teu par em my.telegram.org quando o site responder.",
            file=sys.stderr,
        )
        return _ANDROID_OSS_PUBLISHED_API_ID, _ANDROID_OSS_PUBLISHED_API_HASH

    # Chave presente no .env mas vazia (TELEGRAM_API_ID=) dava int('') → ValueError.
    raw_id = (os.environ.get("TELEGRAM_API_ID") or os.environ.get("API_ID") or "").strip()
    try:
        api_id = int(raw_id) if raw_id else 0
    except ValueError:
        raise SystemExit(
            "Config: TELEGRAM_API_ID deve ser só dígitos (ex.: 12345678), sem letras nem espaços.\n"
            "https://my.telegram.org/apps\n"
            "Ou TELEGRAM_USE_PUBLISHED_ANDROID_API=1 (par público do cliente Telegram Android OSS). "
            "Ou telegram_api.json / TELEGRAM_CREDENTIALS_FILE — vê telegram_api.json.example."
        )
    api_hash = (os.environ.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH") or "").strip()

    def merge_from_cred_file(path: str) -> bool:
        """Preenche api_id/api_hash em falta a partir de um JSON."""
        nonlocal api_id, api_hash
        if not path or not os.path.isfile(path):
            return False
        try:
            with open(path, encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, json.JSONDecodeError) as e:
            print(
                f"Aviso: não foi possível ler credenciais de {path!r}: {e}",
                file=sys.stderr,
            )
            return False
        jid = data.get("api_id", data.get("TELEGRAM_API_ID"))
        jhash = data.get("api_hash", data.get("TELEGRAM_API_HASH", ""))
        if jid is None and not jhash:
            return False
        if not api_id and jid is not None:
            try:
                api_id = int(str(jid).strip())
            except ValueError:
                print(
                    f"Aviso: api_id inválido em {path} (tem de ser dígitos).",
                    file=sys.stderr,
                )
        if not api_hash and isinstance(jhash, str) and jhash.strip():
            api_hash = jhash.strip()
        return bool(api_id and api_hash)

    if not api_id or not api_hash:
        paths_try = []
        tf = os.environ.get("TELEGRAM_CREDENTIALS_FILE", "").strip()
        if tf:
            paths_try.append(tf if os.path.isabs(tf) else os.path.join(_SCRIPT_DIR, tf))
        paths_try.append(os.path.join(_SCRIPT_DIR, "telegram_api.json"))

        loaded = False
        for cred_path in paths_try:
            loaded = merge_from_cred_file(cred_path) or loaded
            if loaded and api_id and api_hash:
                break

        if loaded and api_id and api_hash:
            return api_id, api_hash

    if not api_id or not api_hash:
        print(
            "\n!!! Config em falta !!!\n"
            f"Este processo lê o .env AQUI (caminho absoluto):\n  {ENV_DOTENV_PATH}\n"
            "Preenche TELEGRAM_API_ID (só dígitos) e TELEGRAM_API_HASH (string).\n"
            "https://my.telegram.org/apps\n\n"
            "Ou cria telegram_api.json (ou TELEGRAM_CREDENTIALS_FILE) com api_id/api_hash.\n"
            "Ou, se só o site falhar mas queres mesmo arrancar: TELEGRAM_USE_PUBLISHED_ANDROID_API=1 "
            "(par público do app Android OSS — menos ideal para longo prazo).\n",
            file=sys.stderr,
        )
        raise SystemExit(
            f"Config: define TELEGRAM_API_ID e TELEGRAM_API_HASH em:\n  {ENV_DOTENV_PATH}\n"
            "Ou JSON de credenciais, ou TELEGRAM_USE_PUBLISHED_ANDROID_API=1."
        )
    return api_id, api_hash


API_ID, API_HASH = _telegram_api_credentials()
ACCOUNTS = _load_accounts()
ACCOUNT_COUNT = max(1, len(ACCOUNTS))
SESSION_TO_INDEX = {a["session"]: i for i, a in enumerate(ACCOUNTS)}
TARGET_GROUP = os.environ.get("TARGET_GROUP", "@iptvpncode").strip()

# Palavras-chave por região (conta1 = PT+ES, conta2 = resto Europa).
REGION_PT_ES = "pt_es"
REGION_EUROPE = "europe"

SEARCH_KEYWORDS_PT_ES = [
    'iptv portugal',
    'iptv pt',
    'lista iptv portugal',
    'iptv gratis portugal',
    'm3u portugal',
    'stremio portugal',
    'filmes portugal',
    'series pt',
    'iptv españa',
    'iptv spain',
    'lista iptv españa',
    'iptv gratis españa',
    'm3u españa',
    'stremio españa',
    'peliculas español',
    'series españa',
    'cccam portugal',
    'android tv iptv',
    'fire stick iptv',
    'liga portugal iptv',
    'dazn portugal',
    'canal plus iptv',
]

SEARCH_KEYWORDS_EUROPE = [
    'iptv deutschland',
    'iptv germany',
    'iptv gratis deutschland',
    'm3u deutschland',
    'iptv france',
    'iptv france gratuit',
    'iptv italia',
    'lista iptv italia',
    'iptv uk',
    'iptv uk free',
    'streaming uk',
    'iptv polska',
    'iptv romania',
    'iptv europe',
    'iptv nederland',
    'iptv belgie',
    'iptv schweiz',
    'iptv austria',
    'stremio',
    'm3u playlist',
    'iptv smarters',
    'tivimate',
    'iptv 4k',
    'iptv premium',
    'cccam',
    'oscam iptv',
]

# Grupos @ conhecidos (alto tráfego IPTV/streaming) — scrape prioritário antes da pesquisa.
PRIORITY_SCRAPE_GROUPS_PT_ES = [
    'iptvcccampt',
    'stremioEs',
    'pt_series',
    'FILMES_SERIES_PTBR',
    'tecnologiaportugal',
    'portugaltec',
    'iptvportugal',
    'seriesespanolas',
    'SERIES_DE_ESPANA_01',
    'djiminiseries',
]

PRIORITY_SCRAPE_GROUPS_EUROPE = [
    'iptvromaniatv',
    'iptvgermanyvip',
    'iptvgermany46',
    'iptvgermanquality',
    'iptvpolskie',
    'iptvITALlA',
    'iptvgermanyvip',
    'france_portogallo_streaming',
    'inghilterra_olanda_streaming_eur',
    'iptvromaniatv',
    'UK_29z',
    'moua_ukraine',
    'iptveurope',
    'IPTVCLASES',
]

SEARCH_KEYWORDS = SEARCH_KEYWORDS_PT_ES  # compat legado

EUROPE_LANGS = frozenset({
    'de', 'fr', 'it', 'en', 'nl', 'pl', 'ro', 'hu', 'cs', 'sk',
    'da', 'sv', 'no', 'fi', 'el', 'tr', 'uk', 'ru', 'bg', 'hr',
    'sl', 'lt', 'lv', 'et', 'sr', 'mk', 'sq', 'be', 'is', 'ga',
})

PT_ES_LANGS = frozenset({'pt', 'es', 'gl', 'ca', 'eu'})

# Divisão geográfica: conta1 PT+ES, conta2 resto Europa (convites + scrape separados).
TELEGRAM_REGION_SPLIT = _env_bool("TELEGRAM_REGION_SPLIT", ACCOUNT_COUNT > 1)


def _parse_account_regions() -> list[str]:
    raw = (os.environ.get("TELEGRAM_ACCOUNT_REGIONS") or "").strip()
    if raw:
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
        out = []
        for p in parts:
            if p in (REGION_PT_ES, "pt", "es", "pt-es", "pt_es"):
                out.append(REGION_PT_ES)
            elif p in (REGION_EUROPE, "eu", "europe", "rest_europe"):
                out.append(REGION_EUROPE)
            else:
                out.append(p)
        return out
    defaults = [REGION_PT_ES, REGION_EUROPE]
    while len(defaults) < ACCOUNT_COUNT:
        defaults.append(REGION_EUROPE)
    return defaults[:ACCOUNT_COUNT]


ACCOUNT_REGIONS = _parse_account_regions()


def session_region(session_name: str) -> str:
    idx = SESSION_TO_INDEX.get(session_name, 0)
    if idx < len(ACCOUNT_REGIONS):
        return ACCOUNT_REGIONS[idx]
    return REGION_PT_ES if idx == 0 else REGION_EUROPE


def keywords_for_region(region: str) -> list[str]:
    if region == REGION_EUROPE:
        return list(SEARCH_KEYWORDS_EUROPE)
    return list(SEARCH_KEYWORDS_PT_ES)

# --- Ritmo diário por conta (configurável via .env) ---
# A conta que consegue convidar tenta chegar perto deste alvo; o teto global
# (MAX_ADDS_PROJECT_PER_DAY) e a quota justa por conta limitam o total.
MIN_ADDS_PER_DAY = _env_int("MIN_ADDS_PER_DAY", 45)
MAX_ADDS_PER_DAY = _env_int("MAX_ADDS_PER_DAY", 80)

# Teto global (soma de adds_ok de todas as sessões nesse dia). Ajustável: env MAX_ADDS_PROJECT_PER_DAY
MAX_ADDS_PROJECT_PER_DAY = int(os.environ.get("MAX_ADDS_PROJECT_PER_DAY", "70"))

# Modo operação (testar com calma na VPS sem disparar convites)
# TELEGRAM_INVITES_ENABLED=0  → liga contas, resolve grupo; não envia convites (só heartbeat)
# SCRAPE_ENABLED=0            → nenhuma conta corre descoberta/extração
# SCRAPE_ALL_ACCOUNTS=1       → todas as contas com pesquisa global (keywords); raro — mais carga na API
# TELEGRAM_FIXED_SCRAPE_GROUPS=meugrupo,outro → contas extra (não a 1.ª) só extraiem destes @, sem pesquisa
# EXCLUDE_SOURCE_GROUP_ADMINS=0  → na extração, não saltar donos/admins dos grupos de origem (não recomendado)
TELEGRAM_INVITES_ENABLED = _env_bool("TELEGRAM_INVITES_ENABLED", True)
SCRAPE_ENABLED = _env_bool("SCRAPE_ENABLED", True)
SCRAPE_ALL_ACCOUNTS = _env_bool("SCRAPE_ALL_ACCOUNTS", False)
# Contas extras (não a 1.ª): depois dos grupos em TELEGRAM_FIXED_SCRAPE_GROUPS, também fazem scrape global (keywords).
SCRAPE_EXTRA_ACCOUNTS_ALSO_GLOBAL = _env_bool("SCRAPE_EXTRA_ACCOUNTS_ALSO_GLOBAL", False)
EXCLUDE_SOURCE_GROUP_ADMINS = _env_bool("EXCLUDE_SOURCE_GROUP_ADMINS", True)
# Modo activo: 24/7, pausas curtas, retentar cedo após PeerFlood (contas OK no @SpamBot).
TELEGRAM_ACTIVE_MODE = _env_bool("TELEGRAM_ACTIVE_MODE", False)
# Extração: não filtrar nome/idioma (grupos IPTV são multilingues — mais membros na fila).
TELEGRAM_SCRAPE_RELAX_NAME_FILTER = _env_bool("TELEGRAM_SCRAPE_RELAX_NAME_FILTER", False)
# Convites: pending mais recentes primeiro (scrape fresco = mais conversões).
TELEGRAM_INVITE_NEWEST_FIRST = _env_bool("TELEGRAM_INVITE_NEWEST_FIRST", True)
# Pesquisa global Telegram por keyword (mais grupos por ronda).
TELEGRAM_SEARCH_LIMIT = _env_int("TELEGRAM_SEARCH_LIMIT", 25)
# Máx. membros extraídos por grupo por ronda (grupos gigantes).
TELEGRAM_SCRAPE_MAX_PER_GROUP = _env_int("TELEGRAM_SCRAPE_MAX_PER_GROUP", 500)
# Fila vazia: segundos antes de novo scrape (menos = mais agressivo).
QUEUE_EMPTY_WAIT_SEC = _env_int("QUEUE_EMPTY_WAIT_SEC", 90)
# Sessões sem convites (só scrape) — útil se PeerFlood constante numa conta.
TELEGRAM_INVITES_DISABLED_SESSIONS = frozenset(
    s.strip()
    for s in (os.environ.get("TELEGRAM_INVITES_DISABLED_SESSIONS") or "").split(",")
    if s.strip()
)
# Após N PeerFlood no mesmo dia, convites dessa sessão pausam até amanhã.
TELEGRAM_PEERFLOOD_DAILY_MAX = _env_int("TELEGRAM_PEERFLOOD_DAILY_MAX", 4)


def _parse_cooldown_until():
    """ISO datetime (hora de Lisboa) até à qual NÃO se enviam convites — só scrape.

    Deixa o throttle PeerFlood expirar sem o 'picar'. Formatos aceites:
      '2026-05-29T06:00'  ou  '2026-05-29 06:00'  ou só '+4h' (4h a partir de agora).
    """
    raw = (os.environ.get("TELEGRAM_INVITE_COOLDOWN_UNTIL") or "").strip()
    if not raw:
        return None
    try:
        if raw.startswith("+") and raw.lower().endswith("h"):
            hours = float(raw[1:-1])
            return datetime.datetime.now(TZ) + datetime.timedelta(hours=hours)
        norm = raw.replace(" ", "T")
        dt = datetime.datetime.fromisoformat(norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt
    except (ValueError, TypeError):
        print(
            f"TELEGRAM_INVITE_COOLDOWN_UNTIL inválido: {raw!r} — ignorado.",
            file=sys.stderr,
        )
        return None
TELEGRAM_HUMAN_SCHEDULE = _env_bool(
    "TELEGRAM_HUMAN_SCHEDULE", not TELEGRAM_ACTIVE_MODE
)
# 1 = conta2+ partilham o horário “humano” (wake/bed) da 1.ª conta; evita a 2.ª dormir horas a mais com RNG diferente.
TELEGRAM_UNIFIED_HUMAN_SCHEDULE = _env_bool("TELEGRAM_UNIFIED_HUMAN_SCHEDULE", False)
# Multi-conta: cada sessão prefere pending com ABS(user_id) % N == índice (menos corrida pela mesma fatia → menos PeerFlood numa conta).
TELEGRAM_QUEUE_PARTITION = _env_bool("TELEGRAM_QUEUE_PARTITION", ACCOUNT_COUNT > 1)
# Multi-conta: meta aleatória do dia por conta limitada para caber no teto global (evita uma conta “roubar” o cap).
TELEGRAM_BALANCE_DAILY_TARGETS = _env_bool("TELEGRAM_BALANCE_DAILY_TARGETS", ACCOUNT_COUNT > 1)


def _daily_invite_bounds() -> tuple[int, int]:
    """Limites [min,max] para random da meta diária desta conta."""
    if not TELEGRAM_BALANCE_DAILY_TARGETS or ACCOUNT_COUNT <= 1:
        return MIN_ADDS_PER_DAY, MAX_ADDS_PER_DAY
    slice_cap = max(2, MAX_ADDS_PROJECT_PER_DAY // ACCOUNT_COUNT)
    eff_max = min(MAX_ADDS_PER_DAY, slice_cap)
    eff_min = min(MIN_ADDS_PER_DAY, eff_max)
    eff_min = max(1, eff_min)
    if eff_min > eff_max:
        eff_min = eff_max
    return eff_min, eff_max


def _parse_group_list(raw: str) -> list[str]:
    out = []
    for part in raw.split(","):
        u = part.strip().lstrip("@")
        if u and u not in out:
            out.append(u)
    return out


def _fixed_scrape_group_usernames():
    return _parse_group_list(os.environ.get("TELEGRAM_FIXED_SCRAPE_GROUPS") or "")


def _priority_scrape_groups_for_region(region: str) -> list[str]:
    """Grupos IPTV de alto volume: env + listas embutidas."""
    extra = _parse_group_list(os.environ.get("TELEGRAM_PRIORITY_SCRAPE_GROUPS") or "")
    base = (
        list(PRIORITY_SCRAPE_GROUPS_PT_ES)
        if region == REGION_PT_ES
        else list(PRIORITY_SCRAPE_GROUPS_EUROPE)
    )
    fixed = _fixed_scrape_group_usernames()
    merged: list[str] = []
    for g in (*extra, *fixed, *base):
        if g not in merged:
            merged.append(g)
    return merged


def _session_should_scrape(session_name: str) -> bool:
    """
    Por defeito: só ACCOUNTS[0] faz scrape completo (keywords).
    TELEGRAM_REGION_SPLIT=1: cada conta faz scrape da sua região (PT+ES vs Europa).
    """
    if not SCRAPE_ENABLED:
        return False
    if TELEGRAM_REGION_SPLIT:
        return True
    if SCRAPE_ALL_ACCOUNTS:
        return True
    if session_name == ACCOUNTS[0]["session"]:
        return True
    if SCRAPE_EXTRA_ACCOUNTS_ALSO_GLOBAL:
        return True
    return bool(_fixed_scrape_group_usernames())

# Aviso se disco livre < N MiB (evita erro Telethon "database or disk is full")
DISK_WARN_FREE_MB = int(os.environ.get("DISK_WARN_FREE_MB", "400"))

# Pausas entre convites bem-sucedidos: triangular (picos no meio), não uniforme "robótico".
# Otimizado para eficiência máxima mantendo o comportamento humano
_pause_def = (4 * 60, 12 * 60, 6 * 60) if TELEGRAM_ACTIVE_MODE else (8 * 60, 25 * 60, 12 * 60)
HUMAN_PAUSE_MIN_SEC = _env_int("HUMAN_PAUSE_MIN_SEC", _pause_def[0])
HUMAN_PAUSE_MAX_SEC = _env_int("HUMAN_PAUSE_MAX_SEC", _pause_def[1])
HUMAN_PAUSE_MODE_SEC = _env_int("HUMAN_PAUSE_MODE_SEC", _pause_def[2])
# Pequeno ruído em segundos (evita minutos redondos sempre iguais)
HUMAN_PAUSE_JITTER_SEC = (-60, 120) if TELEGRAM_ACTIVE_MODE else (-60, 120)
# Às vezes uma pausa maior (simula "afastou do telemóvel") — probabilidade baixa para não estourar o dia.
EXTRA_LONG_PAUSE_PROB = 0.0 if TELEGRAM_ACTIVE_MODE else 0.12
EXTRA_LONG_PAUSE_MIN_SEC = 10 * 60
EXTRA_LONG_PAUSE_MAX_SEC = 42 * 60

# Ao começar cada "dia" (Lisboa), atraso aleatório por conta (evita as duas a atuarem à mesma hora).
_jitter_def = (0, 30) if TELEGRAM_ACTIVE_MODE else (2 * 60, 38 * 60)
DAY_START_JITTER_MIN_SEC = _env_int("DAY_START_JITTER_MIN_SEC", _jitter_def[0])
DAY_START_JITTER_MAX_SEC = _env_int("DAY_START_JITTER_MAX_SEC", _jitter_def[1])

# Comportamento tipo pessoa: janelas de vigília em Lisboa (por conta e por dia, estável no mesmo dia).
# Fins-de-semana: acorda mais tarde / deita um pouco mais tarde.
WEEKEND_WAKE_EXTRA_H_MAX = 2
WEEKEND_BED_EXTRA_MIN = 25

# Hesitação antes de carregar em “adicionar” (pessoa a ver perfis / notificações).
_hes_def = (2, 10, 4) if TELEGRAM_ACTIVE_MODE else (5, 45, 15)
PRE_ACTION_HESITATION_MIN_SEC = _env_int("PRE_ACTION_HESITATION_MIN_SEC", _hes_def[0])
PRE_ACTION_HESITATION_MAX_SEC = _env_int("PRE_ACTION_HESITATION_MAX_SEC", _hes_def[1])
PRE_ACTION_HESITATION_TYPICAL_SEC = _env_int("PRE_ACTION_HESITATION_TYPICAL_SEC", _hes_def[2])

# Pausa estilo “distração” (fez outra coisa no telemóvel) — rara, antes de pegar na fila.
DISTRACTION_PAUSE_PROB = 0.0 if TELEGRAM_ACTIVE_MODE else 0.08
DISTRACTION_PAUSE_MIN_SEC = 4 * 60
DISTRACTION_PAUSE_MAX_SEC = 28 * 60

# Pausa de almoço (desligada no modo activo).
LUNCH_BREAK_PROB = _env_float("LUNCH_BREAK_PROB", 0.0 if TELEGRAM_ACTIVE_MODE else 0.24)

# Espera após PeerFlood (SpamBot OK ≠ convites ilimitados; modo activo retenta em minutos, não horas).
_pf_def = (20 * 60, 60 * 60) if TELEGRAM_ACTIVE_MODE else (12 * 3600, 24 * 3600)
TELEGRAM_PEERFLOOD_WAIT_MIN_SEC = _env_int("TELEGRAM_PEERFLOOD_WAIT_MIN_SEC", _pf_def[0])
TELEGRAM_PEERFLOOD_WAIT_MAX_SEC = _env_int("TELEGRAM_PEERFLOOD_WAIT_MAX_SEC", _pf_def[1])

# Depois das 21h em Lisboa, pausas entre convites esticam um pouco (cansaço / TV).
EVENING_SLOWDOWN_START_HOUR = 21
EVENING_PAUSE_FACTOR_MIN = 1.06
EVENING_PAUSE_FACTOR_MAX = 1.38

# Escalonamento ao arranque: evita dois logins Telethon ao mesmo tempo (429 / flood na API).
WORKER_LOGIN_STAGGER_SEC = float(os.environ.get("WORKER_LOGIN_STAGGER_SEC", "45"))

# Multiplica pausas entre convites OK (≥1). Com 2+ contas o default modesto (~+15 %) reduz rajadas na mesma conta.
_INV_DEF = "1.15" if ACCOUNT_COUNT > 1 else "1.0"
try:
    TELEGRAM_INVITE_PAUSE_FACTOR = float(os.environ.get("TELEGRAM_INVITE_PAUSE_FACTOR", _INV_DEF).strip())
except ValueError:
    TELEGRAM_INVITE_PAUSE_FACTOR = float(_INV_DEF)
TELEGRAM_INVITE_PAUSE_FACTOR = max(1.0, min(TELEGRAM_INVITE_PAUSE_FACTOR, 2.5))

FINAL_INVITE_STATUSES = frozenset({
    'privacy_restricted',
    'not_mutual',
    'added',
    'error',
    'unresolvable',
    'no_username',
    'bloqueado',
    'not_addable',
    'too_many_channels',
    'user_restricted',
    'bot_not_addable',
})

_FINAL_INVITE_ERROR_CLASSES = (
    errors.UserChannelsTooMuchError,
    errors.UserKickedError,
    errors.UserBlockedError,
    errors.UserBotError,
    errors.UserRestrictedError,
    errors.BotGroupsBlockedError,
    errors.BotsTooMuchError,
)

_TARGET_INVITE_ERROR_CLASSES = (
    errors.ChatAdminRequiredError,
    errors.ChatWriteForbiddenError,
    errors.ChannelPrivateError,
    errors.ChatForbiddenError,
)


def _rpc_name(exc: Exception) -> str:
    """Extrai o erro RPC do Telegram quando Telethon não tem classe específica."""
    return str(exc).upper()


def _is_generic_member_add_failed(exc: Exception) -> bool:
    return "CHAT_MEMBER_ADD_FAILED" in _rpc_name(exc)


def _final_invite_status(exc: Exception) -> str:
    if isinstance(exc, errors.UserChannelsTooMuchError):
        return "too_many_channels"
    if isinstance(exc, (errors.UserBotError, errors.BotGroupsBlockedError, errors.BotsTooMuchError)):
        return "bot_not_addable"
    if isinstance(exc, errors.UserRestrictedError):
        return "user_restricted"
    return "not_addable"

# Meia-noite e contadores no fuso de Portugal (alinha com hábitos humanos no país).
TZ = ZoneInfo("Europe/Lisbon")

# Arrefecimento de convites (precisa do TZ, por isso é resolvido aqui).
INVITE_COOLDOWN_UNTIL = _parse_cooldown_until()


def today_local():
    return datetime.datetime.now(TZ).date()


# --- Registos (SQLite) para controlo e afinação ---
DAILY_BUMP_COLS = frozenset({
    'adds_ok', 'err_privacy', 'err_not_mutual', 'err_floodwait', 'err_rate_limit',
    'err_other', 'scrape_new_users', 'scrape_runs', 'queue_empty_events',
    'lunch_breaks', 'distraction_count', 'human_schedule_waits',
})


async def count_pending_users(region: str | None = None):
    try:
        async with open_users_db() as db:
            if region:
                async with db.execute(
                    "SELECT COUNT(*) FROM users WHERE status = 'pending' AND region = ?",
                    (region,),
                ) as c:
                    row = await c.fetchone()
                    return int(row[0]) if row else 0
            async with db.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'") as c:
                row = await c.fetchone()
                return int(row[0]) if row else 0
    except Exception:
        return 0


async def record_event(session, event_type, detail=None, username=None, user_id=None, extra=None):
    """Linha de auditoria (não deve bloquear o bot)."""
    day = today_local().isoformat()
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
    try:
        async with open_users_db() as db:
            await db.execute(
                '''INSERT INTO adder_events (day, session, event_type, detail, username, user_id, extra_json)
                   VALUES (?,?,?,?,?,?,?)''',
                (day, session, event_type, detail, username, user_id, extra_json),
            )
            await db.commit()
    except Exception:
        pass


async def metrics_ensure_day(day_str: str, session: str, target_adds: int):
    """Uma única ligação à BD (evita nested connects SQLite + melhora fiabilidade da meta)."""
    try:
        async with open_users_db() as db:
            async with db.execute(
                "SELECT COUNT(*) FROM users WHERE status = 'pending'"
            ) as c:
                row = await c.fetchone()
                pending = int(row[0]) if row else 0
            cur = await db.execute(
                "SELECT 1 FROM adder_daily WHERE day = ? AND session = ?",
                (day_str, session),
            )
            exists = await cur.fetchone()
            if not exists:
                await db.execute(
                    """INSERT INTO adder_daily (
                        day, session, target_adds, pending_at_day_start, updated_at
                    ) VALUES (?, ?, ?, ?, datetime('now'))""",
                    (day_str, session, target_adds, pending),
                )
            else:
                await db.execute(
                    """UPDATE adder_daily SET target_adds = ?, updated_at = datetime('now')
                       WHERE day = ? AND session = ?""",
                    (target_adds, day_str, session),
                )
            await db.commit()
    except Exception as e:
        logger.warning("metrics_ensure_day falhou (%s, %s): %s", day_str, session, e)


async def metrics_bump(day_str: str, session: str, field: str, n: int = 1):
    if field not in DAILY_BUMP_COLS:
        return
    try:
        async with open_users_db() as db:
            await db.execute(
                f"""INSERT INTO adder_daily (day, session, {field}, updated_at)
                    VALUES (?, ?, ?, datetime('now'))
                    ON CONFLICT(day, session) DO UPDATE SET
                      {field} = {field} + ?,
                      updated_at = datetime('now')""",
                (day_str, session, n, n),
            )
            await db.commit()
    except Exception:
        pass


async def metrics_mark_target_met(day_str: str, session: str):
    try:
        async with open_users_db() as db:
            await db.execute(
                """UPDATE adder_daily SET target_met = 1, updated_at = datetime('now')
                   WHERE day = ? AND session = ?""",
                (day_str, session),
            )
            await db.commit()
    except Exception:
        pass

async def total_project_adds_ok_for_day(day_str: str) -> int:
    """Soma convites OK (coluna adds_ok) de todas as contas num dia."""
    try:
        async with open_users_db() as db:
            async with db.execute(
                "SELECT COALESCE(SUM(adds_ok), 0) FROM adder_daily WHERE day = ?",
                (day_str,),
            ) as c:
                row = await c.fetchone()
                return int(row[0] or 0)
    except Exception:
        return 0


async def session_adds_ok_for_day(day_str: str, session: str) -> int:
    """Convites OK desta sessão no dia (persistido — sobrevive a pm2 restart)."""
    try:
        async with open_users_db() as db:
            async with db.execute(
                "SELECT COALESCE(adds_ok, 0) FROM adder_daily WHERE day = ? AND session = ?",
                (day_str, session),
            ) as c:
                row = await c.fetchone()
                return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def session_fair_daily_cap() -> int:
    """Quota por conta: parte justa + folga para uma conta cobrir a outra se esta estiver limitada.

    Com 2 contas e teto 100, dá ~70 — assim, se a conta1 (PeerFlood) só faz 20,
    a conta2 pode chegar a 70 e o projeto aproxima-se do teto em vez de ficar a meio.
    """
    if ACCOUNT_COUNT <= 1:
        return MAX_ADDS_PROJECT_PER_DAY
    fair = MAX_ADDS_PROJECT_PER_DAY / ACCOUNT_COUNT
    with_slack = int(fair * 1.4)
    return max(2, min(MAX_ADDS_PROJECT_PER_DAY, with_slack))



def _rng_for_day(account_key: str, day: datetime.date) -> random.Random:
    """RNG estável por (conta, dia), igual após reinício do PM2."""
    digest = hashlib.sha256(f"{account_key}:{day.isoformat()}".encode()).hexdigest()
    seed = int(digest[:16], 16)
    return random.Random(seed)


def wake_and_bed_for_day(account_key: str, day: datetime.date):
    """Hora de começar a ‘usar o Telegram’ e hora de largar por hoje (Lisboa)."""
    rnd = _rng_for_day(account_key, day)
    wkd = day.weekday()
    weekend = wkd >= 5

    wh = rnd.randint(7, 9)
    wm = rnd.randint(0, 59)
    if weekend:
        wh += rnd.randint(0, WEEKEND_WAKE_EXTRA_H_MAX)
    if wh > 10:
        wh = 10
    wake = datetime.datetime.combine(day, datetime.time(wh, wm), tzinfo=TZ)

    if rnd.random() < 0.38:
        # Em alguns dias fica online até logo depois da meia-noite
        bed = datetime.datetime.combine(
            day + datetime.timedelta(days=1),
            datetime.time(0, rnd.randint(8, 52)),
            tzinfo=TZ,
        )
    else:
        bh = 23
        bm = rnd.randint(5, 58)
        if weekend:
            bm = min(59, bm + rnd.randint(0, WEEKEND_BED_EXTRA_MIN))
        bed = datetime.datetime.combine(day, datetime.time(bh, bm), tzinfo=TZ)

    if bed <= wake:
        bed = wake + datetime.timedelta(hours=12)

    return wake, bed


async def idle_until_human_active_window(session_name: str):
    """Dorme fora da janela ‘pessoa real’ (madrugada / já deitado)."""
    if not TELEGRAM_HUMAN_SCHEDULE:
        return
    day = today_local()
    sched_session = (
        ACCOUNTS[0]["session"] if TELEGRAM_UNIFIED_HUMAN_SCHEDULE else session_name
    )
    wake, bed = wake_and_bed_for_day(sched_session, day)
    now = datetime.datetime.now(TZ)

    if now < wake:
        sec = (wake - now).total_seconds()
        logger.info(
            f"[{session_name}] Ainda cedo em Lisboa. A retomar ~{wake.strftime('%H:%M')} "
            f"(pausa {int(sec // 60)} min)."
        )
        await record_event(
            session_name,
            'human_wait_morning',
            f'até {wake.strftime("%H:%M")} ({int(sec)}s)',
            extra={'seconds': int(sec)},
        )
        await metrics_bump(day.isoformat(), session_name, 'human_schedule_waits')
        await asyncio.sleep(sec)
        return

    if now >= bed:
        nxt = day + datetime.timedelta(days=1)
        wake_next, _ = wake_and_bed_for_day(sched_session, nxt)
        sec = (wake_next - now).total_seconds()
        logger.info(
            f"[{session_name}] Fim do dia (hábito humano). Voltamos ~{wake_next.strftime('%H:%M')} "
            f"(pausa {int(sec // 60)} min)."
        )
        await record_event(
            session_name,
            'human_wait_night',
            f'até {wake_next.strftime("%H:%M")} ({int(sec)}s)',
            extra={'seconds': int(sec)},
        )
        await metrics_bump(day.isoformat(), session_name, 'human_schedule_waits')
        await asyncio.sleep(max(60, sec))
        return


async def pre_invite_hesitation(session_name: str):
    """Pequeno atraso antes do convite (nem sempre o mesmo)."""
    s = int(
        random.triangular(
            PRE_ACTION_HESITATION_MIN_SEC,
            PRE_ACTION_HESITATION_MAX_SEC,
            PRE_ACTION_HESITATION_TYPICAL_SEC,
        )
    )
    if s >= 55:
        logger.info(f"[{session_name}] Pausa curta antes de convidar (~{s // 60} min).")
    await asyncio.sleep(s)


async def maybe_distraction_pause(session_name: str):
    if random.random() >= DISTRACTION_PAUSE_PROB:
        return
    sec = random.randint(DISTRACTION_PAUSE_MIN_SEC, DISTRACTION_PAUSE_MAX_SEC)
    logger.info(f"[{session_name}] Pausa curta (outras notificações / distração, ~{sec // 60} min).")
    day_s = today_local().isoformat()
    await record_event(session_name, 'distraction_pause', f'{sec}s', extra={'seconds': sec})
    await metrics_bump(day_s, session_name, 'distraction_count')
    await asyncio.sleep(sec)


def human_pause_seconds():
    """Intervalo entre convites: forma mais orgânica que randint plano."""
    base = random.triangular(
        HUMAN_PAUSE_MIN_SEC, HUMAN_PAUSE_MAX_SEC, HUMAN_PAUSE_MODE_SEC
    )
    base += random.randint(*HUMAN_PAUSE_JITTER_SEC)
    base = max(HUMAN_PAUSE_MIN_SEC, base)
    if random.random() < EXTRA_LONG_PAUSE_PROB:
        base += random.randint(EXTRA_LONG_PAUSE_MIN_SEC, EXTRA_LONG_PAUSE_MAX_SEC)
    now = datetime.datetime.now(TZ)
    if now.hour >= EVENING_SLOWDOWN_START_HOUR:
        base *= random.uniform(EVENING_PAUSE_FACTOR_MIN, EVENING_PAUSE_FACTOR_MAX)
    base *= TELEGRAM_INVITE_PAUSE_FACTOR
    return int(base)

# ==========================================
# LOGGING
# ==========================================
_LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
_LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "3"))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("AdderBot")

# ==========================================
# BASE DE DADOS (SQLite)
# ==========================================
async def init_db():
    async with open_users_db() as db:
        await db.execute('PRAGMA journal_mode=WAL')
        await db.execute('PRAGMA synchronous=NORMAL')
        await db.execute('PRAGMA busy_timeout=8000')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                status TEXT DEFAULT 'pending',
                added_by TEXT DEFAULT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS adder_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL DEFAULT (datetime('now')),
                day TEXT NOT NULL,
                session TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT,
                username TEXT,
                user_id INTEGER,
                extra_json TEXT
            )
        ''')
        await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_adder_events_day ON adder_events(day)'
        )
        await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_adder_events_session_day ON adder_events(session, day)'
        )
        await db.execute('''
            CREATE TABLE IF NOT EXISTS adder_daily (
                day TEXT NOT NULL,
                session TEXT NOT NULL,
                target_adds INTEGER DEFAULT 0,
                target_met INTEGER DEFAULT 0,
                pending_at_day_start INTEGER,
                adds_ok INTEGER DEFAULT 0,
                err_privacy INTEGER DEFAULT 0,
                err_not_mutual INTEGER DEFAULT 0,
                err_floodwait INTEGER DEFAULT 0,
                err_rate_limit INTEGER DEFAULT 0,
                err_other INTEGER DEFAULT 0,
                scrape_new_users INTEGER DEFAULT 0,
                scrape_runs INTEGER DEFAULT 0,
                queue_empty_events INTEGER DEFAULT 0,
                lunch_breaks INTEGER DEFAULT 0,
                distraction_count INTEGER DEFAULT 0,
                human_schedule_waits INTEGER DEFAULT 0,
                updated_at TEXT,
                PRIMARY KEY (day, session)
            )
        ''')
        try:
            await db.execute("ALTER TABLE users ADD COLUMN region TEXT")
        except Exception:
            pass
        await db.commit()


async def migrate_pending_user_regions():
    """Pendentes antigos sem região: classificar para a fila certa de cada conta."""
    async with open_users_db() as db:
        async with db.execute(
            "SELECT user_id, username FROM users WHERE status = 'pending' AND (region IS NULL OR region = '')"
        ) as cur:
            rows = await cur.fetchall()
        for user_id, username in rows:
            region = classify_profile_region(username or "")
            if not region:
                region = REGION_PT_ES  # fila legada era sobretudo PT+ES
            await db.execute(
                "UPDATE users SET region = ? WHERE user_id = ?",
                (region, user_id),
            )
        await db.commit()

async def claim_next_pending(session_name: str):
    """
    Escolhe um pending de forma atómica; repõe 'processing' antigo (processo morreu a meio).
    TELEGRAM_REGION_SPLIT: cada conta só convida utilizadores da sua região (pt_es / europe).
    """
    idx = SESSION_TO_INDEX.get(session_name, 0)
    account_region = session_region(session_name)
    async with open_users_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await db.execute(
                f"""UPDATE users SET status = 'pending', added_by = NULL
                   WHERE status = 'processing'
                   AND datetime(timestamp) < datetime('now', '-{STALE_PROCESSING_SEC} seconds')"""
            )
            row = None
            order_sql = "ORDER BY rowid DESC" if TELEGRAM_INVITE_NEWEST_FIRST else "ORDER BY RANDOM()"
            if TELEGRAM_REGION_SPLIT:
                cur = await db.execute(
                    f"""UPDATE users SET status = 'processing', added_by = ?, timestamp = CURRENT_TIMESTAMP
                       WHERE rowid = (
                         SELECT rowid FROM users WHERE status = 'pending' AND region = ?
                         {order_sql} LIMIT 1
                       )
                       RETURNING user_id, username""",
                    (session_name, account_region),
                )
                row = await cur.fetchone()
            elif TELEGRAM_QUEUE_PARTITION and ACCOUNT_COUNT > 1:
                cur = await db.execute(
                    f"""UPDATE users SET status = 'processing', added_by = ?, timestamp = CURRENT_TIMESTAMP
                       WHERE rowid = (
                         SELECT rowid FROM users WHERE status = 'pending'
                           AND (ABS(user_id) % ?) = ?
                         {order_sql} LIMIT 1
                       )
                       RETURNING user_id, username""",
                    (session_name, ACCOUNT_COUNT, idx),
                )
                row = await cur.fetchone()
            if row is None and not TELEGRAM_REGION_SPLIT:
                cur = await db.execute(
                    f"""UPDATE users SET status = 'processing', added_by = ?, timestamp = CURRENT_TIMESTAMP
                       WHERE rowid = (
                         SELECT rowid FROM users WHERE status = 'pending' {order_sql} LIMIT 1
                       )
                       RETURNING user_id, username""",
                    (session_name,),
                )
                row = await cur.fetchone()
            await db.commit()
            
            if row:
                # Update estado_bot
                await estado_bot.set_status(row[0], 'processing', session_name)
            
            return row
        except Exception:
            await db.rollback()
            raise


async def update_user_status(user_id, status, account_name=None):
    await estado_bot.set_status(user_id, status, account_name)
    async with open_users_db() as db:
        await db.execute(
            "UPDATE users SET status = ?, added_by = ?, timestamp = CURRENT_TIMESTAMP WHERE user_id = ?",
            (status, account_name, user_id)
        )
        await db.commit()

# ==========================================
# FUNÇÕES DE FILTRAGEM E DESCOBERTA
# ==========================================
def is_active_recently(user):
    """Convites: critério mais estrito (últimas ~24h onde o Telegram dá dados)."""
    if isinstance(user.status, UserStatusOnline):
        return True
    if isinstance(user.status, UserStatusRecently):
        return True
    if isinstance(user.status, UserStatusOffline):
        now = datetime.datetime.now(datetime.timezone.utc)
        if (now - user.status.was_online).days < 1:
            return True
    return False


def is_worth_scraping(user):
    """
    Extração para a fila: critério mais largo.
    À noite muita gente passa a 'last seen' há horas/dias; com o filtro de 24h a fila fica vazia.
    """
    if isinstance(user.status, UserStatusOnline):
        return True
    if isinstance(user.status, UserStatusRecently):
        return True
    if isinstance(user.status, UserStatusLastWeek):
        return True
    if isinstance(user.status, UserStatusOffline):
        now = datetime.datetime.now(datetime.timezone.utc)
        offline_hours = (now - user.status.was_online).total_seconds() / 3600
        if offline_hours <= 72:  # até ~3 dias (ajusta se quiseres mais fino)
            return True
    return False

def classify_profile_region(text: str) -> str | None:
    """Classifica perfil para pt_es ou europe (convites por conta)."""
    if not text or not str(text).strip():
        return None
    text_lower = str(text).lower()
    if any(
        char in text_lower
        for char in ('ã', 'õ', 'ç', 'á', 'é', 'í', 'ó', 'ú', 'à', 'â', 'ê', 'ô')
    ):
        return REGION_PT_ES
    if 'ñ' in text_lower:
        return REGION_PT_ES
    if len(text) < 4:
        return None
    try:
        lang = detect(text)
        if lang in PT_ES_LANGS:
            return REGION_PT_ES
        if lang in EUROPE_LANGS:
            return REGION_EUROPE
    except LangDetectException:
        pass
    return None


def is_acceptable_profile_for_region(text: str, region: str) -> bool:
    """Filtro de nome alinhado com a região da conta que está a extrair."""
    if not text:
        return False
    classified = classify_profile_region(text)
    if classified and classified != region:
        return False
    if region == REGION_PT_ES:
        text_lower = text.lower()
        if any(
            char in text_lower
            for char in ('ã', 'õ', 'ç', 'á', 'é', 'í', 'ó', 'ú', 'à', 'â', 'ê', 'ô', 'ñ')
        ):
            return True
        if len(text) < 5:
            return True
        try:
            lang = detect(text)
            return lang in PT_ES_LANGS or lang in ('it', 'en', 'fr')
        except LangDetectException:
            return True
    # Europa (exclui PT/ES óbvios)
    text_lower = text.lower()
    if any(
        char in text_lower
        for char in ('ã', 'õ', 'ç', 'á', 'é', 'í', 'ó', 'ú', 'à', 'â', 'ê', 'ô')
    ):
        return False
    if 'ñ' in text_lower:
        return False
    if len(text) < 5:
        return True
    try:
        lang = detect(text)
        if lang in PT_ES_LANGS:
            return False
        return lang in EUROPE_LANGS
    except LangDetectException:
        return True


def is_acceptable_profile_name(text):
    """Legado: aceita PT/ES + alguns europeus (sem split de região)."""
    return is_acceptable_profile_for_region(text, REGION_PT_ES) or is_acceptable_profile_for_region(
        text, REGION_EUROPE
    )

async def discover_groups(client, session_name: str, region: str):
    """Pesquisa grupos por região (PT+ES ou Europa)."""
    label = "PT+ES" if region == REGION_PT_ES else "Europa"
    discovered_groups = list(_priority_scrape_groups_for_region(region))
    if discovered_groups:
        logger.info(
            "[%s] %d grupo(s) IPTV prioritário(s) (%s): %s",
            session_name,
            len(discovered_groups),
            label,
            ", ".join("@" + g for g in discovered_groups[:8])
            + ("…" if len(discovered_groups) > 8 else ""),
        )
    logger.info(
        "[%s] A procurar mais grupos (%s), ordem aleatória nesta ronda…",
        session_name,
        label,
    )
    keywords = keywords_for_region(region)
    random.shuffle(keywords)

    for keyword in keywords:
        try:
            result = await client(SearchRequest(
                q=keyword,
                limit=TELEGRAM_SEARCH_LIMIT,
            ))
            for chat in result.chats:
                if isinstance(chat, Channel) and chat.megagroup and chat.username:
                    discovered_groups.append(chat.username)
                    logger.info(
                        "[%s] Grupo encontrado: @%s (Palavra-chave: %s)",
                        session_name,
                        chat.username,
                        keyword,
                    )

            await asyncio.sleep(random.uniform(2.2, 4.8))
        except Exception as e:
            logger.error("[%s] Erro ao pesquisar pela palavra %r: %s", session_name, keyword, e)

    return list(set(discovered_groups))

# ==========================================
# MOTOR DE EXTRAÇÃO (Scraper)
# ==========================================
async def _source_group_admin_user_ids(client, session_name: str, group) -> frozenset:
    """Dono + administradores do grupo de origem (Telegram inclui o criador em Admins)."""
    ids: set[int] = set()
    try:
        async for user in client.iter_participants(group, filter=ChannelParticipantsAdmins()):
            if user is not None and getattr(user, "id", None):
                ids.add(user.id)
    except Exception as e:
        g = group if isinstance(group, str) else getattr(group, "username", group)
        logger.warning(
            "[%s] Não foi possível listar admins de @%s — a extrair sem filtro admin neste grupo. %s",
            session_name,
            g,
            e,
        )
        return frozenset()
    gn = group if isinstance(group, str) else getattr(group, "username", "?")
    if ids:
        logger.info("[%s] @%s: %d conta(s) (dono/admin) excluídas da fila.", session_name, gn, len(ids))
    return frozenset(ids)


async def _extract_from_group_usernames(
    client, session_name: str, groups_to_scrape: list[str], region: str | None = None
) -> int:
    if region is None:
        region = session_region(session_name) if TELEGRAM_REGION_SPLIT else REGION_PT_ES
    novos_nesta_ronda = 0
    async with open_users_db() as db:
        for group in groups_to_scrape:
            try:
                admin_ids = frozenset()
                if EXCLUDE_SOURCE_GROUP_ADMINS:
                    admin_ids = await _source_group_admin_user_ids(client, session_name, group)
                logger.info("[%s] A extrair do grupo: @%s", session_name, group)
                skipped_admins = 0
                scraped_in_group = 0
                group_l = group.lower()
                iptv_group = any(
                    t in group_l
                    for t in ("iptv", "m3u", "stremio", "stream", "cccam", "oscam", "tivi", "smarters")
                )
                relax_names = TELEGRAM_SCRAPE_RELAX_NAME_FILTER or iptv_group
                async for user in client.iter_participants(group):
                    if scraped_in_group >= TELEGRAM_SCRAPE_MAX_PER_GROUP:
                        break
                    if EXCLUDE_SOURCE_GROUP_ADMINS and user.id in admin_ids:
                        skipped_admins += 1
                        continue
                    if user.bot or user.deleted or not user.username:
                        continue

                    if not is_worth_scraping(user):
                        continue

                    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

                    if not relax_names:
                        if TELEGRAM_REGION_SPLIT:
                            if not is_acceptable_profile_for_region(full_name, region):
                                continue
                        elif not is_acceptable_profile_name(full_name):
                            continue

                    try:
                        await db.execute(
                            "INSERT INTO users (user_id, username, region) VALUES (?, ?, ?)",
                            (user.id, user.username, region),
                        )
                        await db.commit()
                        novos_nesta_ronda += 1
                        scraped_in_group += 1
                        if novos_nesta_ronda <= 5 or novos_nesta_ronda % 25 == 0:
                            logger.info(
                                "[%s] Utilizador %s adicionado à fila (%s).",
                                session_name,
                                user.username,
                                region,
                            )
                    except aiosqlite.IntegrityError:
                        pass
                if skipped_admins and EXCLUDE_SOURCE_GROUP_ADMINS:
                    logger.info(
                        "[%s] @%s: %d utilizador(es) ignorados (dono/admin do grupo de origem).",
                        session_name,
                        group,
                        skipped_admins,
                    )
            except Exception as e:
                logger.error("[%s] Erro ao extrair do grupo @%s: %s", session_name, group, e)
    return novos_nesta_ronda


async def scrape_users(client, session_name: str, region: str | None = None):
    """Descobre grupos (keywords da região) e extrai utilizadores para a DB."""
    if region is None:
        region = session_region(session_name) if TELEGRAM_REGION_SPLIT else REGION_PT_ES
    day_key = today_local().isoformat()
    await metrics_bump(day_key, session_name, 'scrape_runs')
    groups_to_scrape = await discover_groups(client, session_name, region)

    if not groups_to_scrape:
        logger.warning(
            "[%s] Nenhum grupo encontrado (%s) com as palavras-chave fornecidas.",
            session_name,
            region,
        )
        await record_event(session_name, 'scrape_no_groups', region)
        return

    logger.info(
        "[%s] Iniciando extração em %d grupos (%s)…",
        session_name,
        len(groups_to_scrape),
        region,
    )
    novos_nesta_ronda = await _extract_from_group_usernames(
        client, session_name, groups_to_scrape, region=region
    )
    logger.info(
        "[%s] Extração concluída. Novos na fila nesta ronda: %d.",
        session_name,
        novos_nesta_ronda,
    )
    dk = today_local().isoformat()
    if novos_nesta_ronda:
        await metrics_bump(dk, session_name, 'scrape_new_users', novos_nesta_ronda)
    await record_event(
        session_name,
        'scrape_done',
        f'+{novos_nesta_ronda} novos na fila',
        extra={'novos': novos_nesta_ronda, 'groups': len(groups_to_scrape)},
    )


async def scrape_users_from_fixed_groups(client, session_name: str, group_usernames: list[str]):
    """Extrai só dos @ indicados (sem SearchRequest global)."""
    region = session_region(session_name) if TELEGRAM_REGION_SPLIT else REGION_PT_ES
    day_key = today_local().isoformat()
    await metrics_bump(day_key, session_name, 'scrape_runs')
    logger.info(
        "[%s] Extração fixa (%d grupo(s), região %s): %s",
        session_name,
        len(group_usernames),
        region,
        ", ".join("@" + u for u in group_usernames),
    )
    novos_nesta_ronda = await _extract_from_group_usernames(
        client, session_name, group_usernames, region=region
    )
    logger.info(
        "[%s] Extração fixa concluída. Novos na fila nesta ronda: %d.",
        session_name,
        novos_nesta_ronda,
    )
    dk = today_local().isoformat()
    if novos_nesta_ronda:
        await metrics_bump(dk, session_name, 'scrape_new_users', novos_nesta_ronda)
    await record_event(
        session_name,
        'scrape_done',
        f'+{novos_nesta_ronda} novos (grupos fixos)',
        extra={'novos': novos_nesta_ronda, 'groups': len(group_usernames), 'fixed': True},
    )


async def run_scrape_for_session(client, session_name: str):
    """Com TELEGRAM_REGION_SPLIT: cada conta faz scrape só da sua região."""
    if TELEGRAM_REGION_SPLIT:
        await scrape_users(client, session_name, region=session_region(session_name))
        return
    if SCRAPE_ALL_ACCOUNTS:
        await scrape_users(client, session_name)
        return
    if session_name == ACCOUNTS[0]["session"]:
        await scrape_users(client, session_name)
        return
    fixed = _fixed_scrape_group_usernames()
    if fixed:
        await scrape_users_from_fixed_groups(client, session_name, fixed)
    if SCRAPE_EXTRA_ACCOUNTS_ALSO_GLOBAL:
        await scrape_users(client, session_name)

# ==========================================
# MOTOR DE ADIÇÃO (Adder)
# ==========================================
TELEGRAM_START_TIMEOUT_SEC = float(os.environ.get("TELEGRAM_START_TIMEOUT_SEC", "300"))


async def _telethon_disconnect(client: TelegramClient, session_name: str) -> None:
    """Garante socket MTProto fechado ao sair do worker (PM2 restart / crash)."""
    try:
        if client.is_connected():
            await client.disconnect()
            logger.info("[%s] Sessão Telethon desligada (cleanup).", session_name)
    except Exception as e:
        logger.warning("[%s] Erro ao desligar Telethon: %s", session_name, e)


async def adder_worker(account, start_stagger_sec: float = 0):
    session_name = account['session']
    if start_stagger_sec > 0:
        logger.info(
            "[%s] Escalonamento: a aguardar %.0fs (evita dois logins Telethon ao mesmo tempo)…",
            session_name,
            start_stagger_sec,
        )
        await asyncio.sleep(start_stagger_sec)
    logger.info(
        "[%s] Trabalhador ACTIVO — a ligar ao Telegram (escalonamento=%.0fs).",
        session_name,
        start_stagger_sec,
    )
    await record_event(session_name, "worker_boot", "a ligar ao Telegram…")

    session_path = os.path.join(_SCRIPT_DIR, session_name)
    client = TelegramClient(session_path, API_ID, API_HASH)
    try:
        logger.info("[%s] a ligar ao Telegram (Telethon)…", session_name)
        await client.connect()
        if await client.is_user_authorized():
            logger.info(
                "[%s] Sessão já autorizada (.session); não é necessário telemóvel neste arranque.",
                session_name,
            )
        else:
            ph = account.get("phone")
            if not ph or not parse_phone(ph):
                msg = (
                    "Sessão não autorizada e 'phone' em accounts.json inválido ou em falta — "
                    "preenche E.164 ou corre login interativo uma vez por SSH."
                )
                logger.error("[%s] %s", session_name, msg)
                await record_event(session_name, "session_start_failed", msg[:240], extra={})
                await _telethon_disconnect(client, session_name)
                return
            await asyncio.wait_for(
                client.start(phone=ph),
                timeout=TELEGRAM_START_TIMEOUT_SEC,
            )
    except asyncio.TimeoutError:
        msg = (
            f"timeout {int(TELEGRAM_START_TIMEOUT_SEC)}s — sessão provavelmente precisa de "
            "código SMS ou 2FA. Corre uma vez em SSH interativo: "
            "cd /root/TELEGRAM-IPTVPN && source venv/bin/activate && python3 main.py"
        )
        logger.error("[%s] %s", session_name, msg)
        await record_event(session_name, "session_start_timeout", msg[:280])
        await _telethon_disconnect(client, session_name)
        return
    except Exception as e:
        logger.exception("[%s] Falha ao iniciar sessão Telethon: %s", session_name, e)
        await record_event(
            session_name, "session_start_failed", str(e)[:240], extra={"err": str(e)}
        )
        await _telethon_disconnect(client, session_name)
        return

    try:
        logger.info(f"[{session_name}] Sessão iniciada com sucesso.")
        me = await client.get_me()
        if me and getattr(me, "phone", None):
            phone_tail = str(me.phone)[-4:].rjust(4, "*")
        else:
            pp = parse_phone(account.get("phone") or "")
            phone_tail = pp[-4:].rjust(4, "*") if pp else "****"
        await record_event(
            session_name,
            "session_ready",
            phone_tail,
            extra={"session": session_name},
        )

        if _session_should_scrape(session_name):
            try:
                await run_scrape_for_session(client, session_name)
            except Exception as e:
                logger.exception("[%s] scrape falhou; a continuar para o ciclo diário. %s", session_name, e)
                await record_event(
                    session_name,
                    "scrape_failed",
                    str(e)[:280],
                    extra={"err": str(e)},
                )

        try:
            target_channel = await client.get_input_entity(TARGET_GROUP)
            logger.info("[%s] Grupo alvo resolvido (%s).", session_name, TARGET_GROUP)
            logger.info(
                "[%s] Motor de convites activo — a fila SQLite é partilhada entre todas as sessões.",
                session_name,
            )
        except Exception as e:
            logger.exception(
                "[%s] Não foi possível resolver o grupo %s — verifica username, se a conta é admin "
                "e se o grupo permite adicionar membros.",
                session_name,
                TARGET_GROUP,
            )
            await record_event(
                session_name,
                "target_channel_failed",
                str(e)[:280],
                extra={"err": str(e)},
            )
            return

        if not TELEGRAM_INVITES_ENABLED:
            logger.warning(
                "[%s] TELEGRAM_INVITES_ENABLED=0 — convites automáticos DESLIGADOS. "
                "Sessão mantém-se para testar ligação; pm2 stop quando terminares.",
                session_name,
            )
            await record_event(session_name, "invites_disabled_mode", "heartbeat", extra={})
            hb = int(os.environ.get("INVITES_OFF_HEARTBEAT_SEC", "1800"))
            while True:
                await asyncio.sleep(hb)
                logger.info("[%s] Convites OFF — heartbeat (%ds). Conta ainda ligada.", session_name, hb)

        while True:
            _mn, _mx = _daily_invite_bounds()
            current_date = today_local()
            dk_start = current_date.isoformat()
            added_today = await session_adds_ok_for_day(dk_start, session_name)
            daily_target = random.randint(_mn, _mx)
            if added_today >= daily_target:
                daily_target = added_today

            await asyncio.sleep(
                random.randint(DAY_START_JITTER_MIN_SEC, DAY_START_JITTER_MAX_SEC)
            )

            if added_today > 0:
                logger.info(
                    "[%s] Retoma após reinício/viragem: já %d convites OK hoje; meta do dia %d.",
                    session_name,
                    added_today,
                    daily_target,
                )
            logger.info(
                "[%s] Meta de hoje (%s): %d adições (faixa configurada %d–%d).",
                session_name,
                current_date,
                daily_target,
                _mn,
                _mx,
            )
            await metrics_ensure_day(current_date.isoformat(), session_name, daily_target)
            _pend = await count_pending_users()
            await record_event(
                session_name,
                'day_start',
                f'meta={daily_target} fila_pending={_pend}',
                extra={'target': daily_target, 'pending': _pend},
            )

            lunch_done_on = None
            peer_flood_consecutive = 0

            while added_today < daily_target:
                if today_local() != current_date:
                    logger.info(f"[{session_name}] Viragem de dia detetada. A reiniciar contadores.")
                    break

                # Override manual: conta marcada como só-scrape (não convida).
                if session_name in TELEGRAM_INVITES_DISABLED_SESSIONS:
                    if _session_should_scrape(session_name):
                        await run_scrape_for_session(client, session_name)
                    await asyncio.sleep(QUEUE_EMPTY_WAIT_SEC)
                    continue

                # Arrefecimento PeerFlood: não enviar convites até à hora marcada (só scrape),
                # para o throttle do Telegram expirar sem ser 'picado'. Retoma sozinho depois.
                if INVITE_COOLDOWN_UNTIL is not None:
                    now_cd = datetime.datetime.now(TZ)
                    if now_cd < INVITE_COOLDOWN_UNTIL:
                        restante = (INVITE_COOLDOWN_UNTIL - now_cd).total_seconds()
                        logger.info(
                            "[%s] Arrefecimento de convites até %s (faltam %d min). "
                            "Só scrape — a deixar o PeerFlood expirar.",
                            session_name,
                            INVITE_COOLDOWN_UNTIL.strftime("%H:%M"),
                            int(restante // 60),
                        )
                        if _session_should_scrape(session_name):
                            await run_scrape_for_session(client, session_name)
                        await asyncio.sleep(min(restante, 1800))
                        continue

                await idle_until_human_active_window(session_name)

                if today_local() != current_date:
                    logger.info(f"[{session_name}] Viragem de dia após pausa de horário. A reiniciar.")
                    break

                now = datetime.datetime.now(TZ)
                tod = now.hour * 60 + now.minute
                if (
                    lunch_done_on != current_date
                    and (12 * 60 + 5) <= tod <= (15 * 60 + 20)
                    and random.random() < LUNCH_BREAK_PROB
                ):
                    nap = random.randint(32 * 60, 88 * 60)
                    logger.info(f"[{session_name}] Intervalo (almoço / pausa ~{nap // 60} min).")
                    dk_lb = today_local().isoformat()
                    await record_event(session_name, 'lunch_break', f'{nap}s', extra={'seconds': nap})
                    await metrics_bump(dk_lb, session_name, 'lunch_breaks')
                    await asyncio.sleep(nap)
                    lunch_done_on = current_date
                    continue

                await maybe_distraction_pause(session_name)

                dk_cap = today_local().isoformat()
                tot_cap = await total_project_adds_ok_for_day(dk_cap)
                if tot_cap >= MAX_ADDS_PROJECT_PER_DAY:
                    my_ok = await session_adds_ok_for_day(dk_cap, session_name)
                    fair = session_fair_daily_cap()
                    if my_ok < fair and added_today < daily_target:
                        wait_cap = random.randint(40 * 60, 70 * 60)
                        logger.info(
                            "[%s] Teto global %d atingido (total hoje %d) mas esta conta só fez %d "
                            "(quota justa ~%d). Outra conta consumiu o dia — pausa %d min e volta a tentar "
                            "(não fica parada até meia-noite).",
                            session_name,
                            MAX_ADDS_PROJECT_PER_DAY,
                            tot_cap,
                            my_ok,
                            fair,
                            wait_cap // 60,
                        )
                        await record_event(
                            session_name,
                            "project_cap_wait_other_account",
                            dk_cap,
                            extra={
                                "cap": MAX_ADDS_PROJECT_PER_DAY,
                                "tot": tot_cap,
                                "my_ok": my_ok,
                                "fair": fair,
                                "wait_sec": wait_cap,
                            },
                        )
                        await asyncio.sleep(wait_cap)
                        continue
                    logger.info(
                        "[%s] Teto diário do projeto (%d convites OK, todas as contas). Paragem até amanhã.",
                        session_name,
                        MAX_ADDS_PROJECT_PER_DAY,
                    )
                    await record_event(
                        session_name,
                        "project_daily_cap_hit",
                        dk_cap,
                        extra={"cap": MAX_ADDS_PROJECT_PER_DAY, "my_ok": my_ok},
                    )
                    break

                user_data = await claim_next_pending(session_name)
                if not user_data:
                    _reg = session_region(session_name) if TELEGRAM_REGION_SPLIT else None
                    _p = await count_pending_users(_reg)
                    logger.warning(
                        f"[{session_name}] Fila vazia (região={_reg or 'todas'}; pending={_p}). "
                        "A aguardar 5 minutos antes de tentar novamente..."
                    )
                    dk = today_local().isoformat()
                    await metrics_bump(dk, session_name, 'queue_empty_events')
                    await record_event(
                        session_name,
                        'queue_empty',
                        f'pending_reg={_p} region={_reg}',
                        extra={'pending': _p, 'region': _reg},
                    )
                    await asyncio.sleep(QUEUE_EMPTY_WAIT_SEC)
                    if _session_should_scrape(session_name):
                        await run_scrape_for_session(client, session_name)
                    continue

                user_id, username = user_data
                
                estado_memoria = await estado_bot.get_status(user_id)
                if estado_memoria in FINAL_INVITE_STATUSES:
                    logger.info(f"[{session_name}] Agentic Loop: Utilizador {user_id} marcado como {estado_memoria} no estado_bot.json. A pular.")
                    if estado_memoria != 'pending' and estado_memoria != 'processing':
                        # Update DB as well so it's not picked up again as pending
                        async with open_users_db() as db:
                            await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (estado_memoria, user_id))
                            await db.commit()
                    continue

                uname = (username or "").strip()
                if not uname:
                    logger.info("[%s] user_id=%s sem username — a saltar.", session_name, user_id)
                    await update_user_status(user_id, "no_username", session_name)
                    dk = today_local().isoformat()
                    await record_event(
                        session_name,
                        "invite_skip_no_username",
                        str(user_id),
                        user_id=user_id,
                    )
                    await metrics_bump(dk, session_name, "err_other")
                    await asyncio.sleep(random.randint(10, 45))
                    continue

                try:
                    await pre_invite_hesitation(session_name)
                    logger.info("[%s] A tentar adicionar @%s…", session_name, uname)

                    peer = None
                    day_done_reason = None
                    async with INVITE_SERIAL_LOCK:
                        try:
                            peer = await client.get_input_entity(uname)
                        except errors.FloodWaitError:
                            await update_user_status(user_id, "pending")
                            raise
                        except (
                            ValueError,
                            errors.UsernameInvalidError,
                            errors.UsernameNotOccupiedError,
                            errors.UserIdInvalidError,
                        ) as ex:
                            logger.info(
                                "[%s] @%s não resolvível para convite: %s",
                                session_name,
                                uname,
                                ex,
                            )
                            await update_user_status(user_id, "unresolvable", session_name)
                            dk = today_local().isoformat()
                            await record_event(
                                session_name,
                                "invite_unresolvable",
                                uname,
                                username=uname,
                                user_id=user_id,
                                extra={"err": str(ex)},
                            )
                            await metrics_bump(dk, session_name, "err_other")
                            peer = None
                        except Exception as ex:
                            low = str(ex).lower()
                            if (
                                "could not find the input entity" in low
                                or "no user has" in low
                            ):
                                logger.info(
                                    "[%s] @%s — entidade desconhecida nesta sessão: %s",
                                    session_name,
                                    uname,
                                    ex,
                                )
                                await update_user_status(user_id, "unresolvable", session_name)
                                dk = today_local().isoformat()
                                await record_event(
                                    session_name,
                                    "invite_unresolvable",
                                    uname,
                                    username=uname,
                                    user_id=user_id,
                                    extra={"err": str(ex)},
                                )
                                await metrics_bump(dk, session_name, "err_other")
                                peer = None
                            else:
                                raise

                        if peer is not None:
                            dk_inv = today_local().isoformat()
                            tot_inv = await total_project_adds_ok_for_day(dk_inv)
                            my_inv = await session_adds_ok_for_day(dk_inv, session_name)
                            fair_inv = session_fair_daily_cap()
                            if tot_inv >= MAX_ADDS_PROJECT_PER_DAY:
                                await update_user_status(user_id, "pending", None)
                                peer = None
                                day_done_reason = "project_cap"
                            elif my_inv >= fair_inv:
                                logger.info(
                                    "[%s] Quota do dia desta conta (%d) atingida — termina o dia.",
                                    session_name,
                                    fair_inv,
                                )
                                await update_user_status(user_id, "pending", None)
                                peer = None
                                day_done_reason = "session_quota"
                            else:
                                await client(
                                    InviteToChannelRequest(target_channel, [peer])
                                )

                    if peer is None:
                        if day_done_reason:
                            break
                        await asyncio.sleep(random.randint(25, 90))
                        continue

                    await update_user_status(user_id, 'added', session_name)
                    added_today += 1
                    peer_flood_consecutive = 0
                    dk = today_local().isoformat()
                    await record_event(
                        session_name,
                        'invite_ok',
                        f'@{uname}',
                        username=uname,
                        user_id=user_id,
                        extra={'added_today': added_today, 'daily_target': daily_target},
                    )
                    await metrics_bump(dk, session_name, 'adds_ok')

                    # Pausa humana real entre convites bem-sucedidos
                    sleep_time = human_pause_seconds()
                    logger.info(
                        f"[{session_name}] Sucesso! Adicionados hoje: {added_today}/{daily_target}. "
                        f"Próxima ação humana em {sleep_time}s (~{sleep_time // 60}min)."
                    )
                    await asyncio.sleep(sleep_time)

                except errors.FloodWaitError as e:
                    wait_time = max(1200, e.seconds)  # Aguardar 20 mins ou o pedido pelo FloodWait
                    logger.warning(f"[{session_name}] FloodWait! Agente entra em hibernação por {wait_time}s (~{wait_time//60} min) e alternará contas.")
                    dk = today_local().isoformat()
                    await record_event(
                        session_name,
                        'invite_floodwait',
                        f'{wait_time}s',
                        username=uname,
                        user_id=user_id,
                        extra={'seconds': wait_time},
                    )
                    await metrics_bump(dk, session_name, 'err_floodwait')
                    await update_user_status(user_id, 'pending')
                    await asyncio.sleep(wait_time)

                except errors.PeerFloodError:
                    dk = today_local().isoformat()
                    peer_flood_consecutive += 1
                    # Recuo adaptativo: 1.º flood espera pouco; floods seguidos esperam cada vez
                    # mais (até ao teto). Um único sucesso repõe o contador → a conta que está a
                    # funcionar retoma depressa; a que está limitada abranda sozinha. NUNCA pára o dia.
                    base = max(60, TELEGRAM_PEERFLOOD_WAIT_MIN_SEC)
                    cap = max(base, TELEGRAM_PEERFLOOD_WAIT_MAX_SEC)
                    wait_peer = min(cap, int(base * (2 ** (peer_flood_consecutive - 1))))
                    if wait_peer > 120:
                        wait_peer = random.randint(int(wait_peer * 0.85), wait_peer)
                    wait_label = (
                        f"~{wait_peer // 60} min"
                        if wait_peer < 3600
                        else f"~{wait_peer // 3600}h{(wait_peer % 3600) // 60:02d}"
                    )
                    logger.warning(
                        "[%s] PeerFlood (seguidos: %d). A aguardar %s e retentar (sem parar o dia).",
                        session_name,
                        peer_flood_consecutive,
                        wait_label,
                    )
                    await record_event(
                        session_name,
                        'invite_peer_flood',
                        f'wait_{wait_peer}s',
                        username=uname,
                        user_id=user_id,
                        extra={'seconds': wait_peer, 'consecutive': peer_flood_consecutive},
                    )
                    await metrics_bump(dk, session_name, 'err_rate_limit')
                    await update_user_status(user_id, 'pending')
                    # Enquanto espera, enche a fila com scrape (não desperdiça o tempo de espera).
                    if peer_flood_consecutive >= 2 and _session_should_scrape(session_name):
                        try:
                            await run_scrape_for_session(client, session_name)
                        except Exception:
                            pass
                    await asyncio.sleep(wait_peer)

                except errors.UserPrivacyRestrictedError:
                    logger.info(f"[{session_name}] @{uname} tem restrições de privacidade. Ignorado.")
                    dk = today_local().isoformat()
                    await record_event(session_name, 'invite_privacy', uname, username=uname, user_id=user_id)
                    await metrics_bump(dk, session_name, 'err_privacy')
                    await update_user_status(user_id, 'privacy_restricted', session_name)
                    await asyncio.sleep(random.randint(30, 120))

                except errors.UserNotMutualContactError:
                    logger.info(f"[{session_name}] @{uname} requer contacto mútuo. Ignorado.")
                    dk = today_local().isoformat()
                    await record_event(session_name, 'invite_not_mutual', uname, username=uname, user_id=user_id)
                    await metrics_bump(dk, session_name, 'err_not_mutual')
                    await update_user_status(user_id, 'not_mutual', session_name)
                    await asyncio.sleep(random.randint(30, 120))

                except _FINAL_INVITE_ERROR_CLASSES as e:
                    status = _final_invite_status(e)
                    logger.info(
                        "[%s] @%s não pode ser adicionado (%s). A remover da fila.",
                        session_name,
                        uname,
                        status,
                    )
                    dk = today_local().isoformat()
                    await record_event(
                        session_name,
                        'invite_not_addable',
                        str(e)[:240],
                        username=uname,
                        user_id=user_id,
                        extra={'status': status, 'err': str(e)},
                    )
                    await metrics_bump(dk, session_name, 'err_other')
                    await update_user_status(user_id, status, session_name)
                    await asyncio.sleep(random.randint(30, 120))

                except Exception as e:
                    err = str(e).lower()
                    dk = today_local().isoformat()
                    if isinstance(e, _TARGET_INVITE_ERROR_CLASSES):
                        logger.exception(
                            "[%s] Falha de permissão no grupo alvo ao convidar @%s; "
                            "a sessão vai parar para não queimar a fila.",
                            session_name,
                            uname,
                        )
                        await record_event(
                            session_name,
                            'target_invite_permission_failed',
                            str(e)[:280],
                            username=uname,
                            user_id=user_id,
                            extra={'err': str(e), 'target': TARGET_GROUP},
                        )
                        await update_user_status(user_id, 'pending')
                        return
                    if _is_generic_member_add_failed(e):
                        logger.info(
                            "[%s] @%s não pôde ser adicionado (CHAT_MEMBER_ADD_FAILED). A remover da fila.",
                            session_name,
                            uname,
                        )
                        await record_event(
                            session_name,
                            'invite_member_add_failed',
                            str(e)[:240],
                            username=uname,
                            user_id=user_id,
                            extra={'status': 'not_addable', 'err': str(e)},
                        )
                        await metrics_bump(dk, session_name, 'err_other')
                        await update_user_status(user_id, 'not_addable', session_name)
                        await asyncio.sleep(random.randint(30, 120))
                    elif 'too many' in err or 'limit' in err:
                        logger.error(f"[{session_name}] Erro ao adicionar @{uname}: {e}")
                        await record_event(
                            session_name,
                            'invite_rate_limit',
                            str(e)[:220],
                            username=uname,
                            user_id=user_id,
                        )
                        await metrics_bump(dk, session_name, 'err_rate_limit')
                        await update_user_status(user_id, 'pending')
                        wait = random.randint(60 * 60, 120 * 60)
                        logger.warning(f"[{session_name}] Limite de pedidos provável. A aguardar {wait}s; utilizador volta à fila.")
                        await asyncio.sleep(wait)
                    else:
                        logger.error(f"[{session_name}] Erro ao adicionar @{uname}: {e}")
                        await record_event(
                            session_name,
                            'invite_other_error',
                            str(e)[:280],
                            username=uname,
                            user_id=user_id,
                        )
                        await metrics_bump(dk, session_name, 'err_other')
                        await update_user_status(user_id, 'error', session_name)
                        await asyncio.sleep(random.randint(90, 360))

            tot_day = await total_project_adds_ok_for_day(current_date.isoformat())
            my_day = await session_adds_ok_for_day(current_date.isoformat(), session_name)
            session_quota_reached = my_day >= session_fair_daily_cap()
            project_capped = (
                added_today < daily_target
                and tot_day >= MAX_ADDS_PROJECT_PER_DAY
            )

            # Esta conta já fez a sua parte do dia → dorme até à meia-noite (evita ciclo rápido
            # quando o alvo aleatório é maior que a quota da conta).
            if session_quota_reached and added_today < daily_target:
                now = datetime.datetime.now(TZ)
                tomorrow = (now + datetime.timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                seconds_until_midnight = (tomorrow - now).total_seconds()
                nap = random.randint(120, 900)
                logger.info(
                    "[%s] Quota do dia desta conta atingida (%d). A dormir até à meia-noite (%ds).",
                    session_name,
                    my_day,
                    int(seconds_until_midnight),
                )
                await record_event(
                    session_name,
                    "day_session_quota_met",
                    f"my={my_day}",
                    extra={"my_day": my_day, "cap": session_fair_daily_cap()},
                )
                await asyncio.sleep(seconds_until_midnight + nap)
                continue

            if added_today < daily_target:
                await record_event(
                    session_name,
                    'day_incomplete',
                    f'{added_today}/{daily_target}',
                    extra={'added_today': added_today, 'target': daily_target},
                )

            if added_today >= daily_target:
                dk_done = today_local().isoformat()
                await metrics_mark_target_met(dk_done, session_name)
                await record_event(
                    session_name,
                    'day_target_met',
                    f'{added_today}/{daily_target}',
                    extra={'added_today': added_today, 'target': daily_target},
                )
                now = datetime.datetime.now(TZ)
                tomorrow = (now + datetime.timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                seconds_until_midnight = (tomorrow - now).total_seconds()
                nap = random.randint(120, 900)
                logger.info(
                    f"[{session_name}] Meta diária atingida! A dormir até após meia-noite em Lisboa "
                    f"({int(seconds_until_midnight)}s + folga {nap}s)."
                )
                await asyncio.sleep(seconds_until_midnight + nap)
            elif project_capped:
                my_ok_end = await session_adds_ok_for_day(
                    current_date.isoformat(), session_name
                )
                fair_end = session_fair_daily_cap()
                if my_ok_end < fair_end:
                    wait_end = random.randint(35 * 60, 55 * 60)
                    logger.info(
                        "[%s] Teto global (%d) mas só fiz %d convites (quota justa ~%d) — "
                        "pausa %d min e reabro o ciclo (a outra conta não bloqueia até meia-noite).",
                        session_name,
                        MAX_ADDS_PROJECT_PER_DAY,
                        my_ok_end,
                        fair_end,
                        wait_end // 60,
                    )
                    await record_event(
                        session_name,
                        "day_wait_project_cap_retry",
                        f"tot_ok={tot_day} my_ok={my_ok_end}",
                        extra={
                            "tot_ok": tot_day,
                            "my_ok": my_ok_end,
                            "cap": MAX_ADDS_PROJECT_PER_DAY,
                        },
                    )
                    await asyncio.sleep(wait_end)
                else:
                    now = datetime.datetime.now(TZ)
                    tomorrow = (now + datetime.timedelta(days=1)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    seconds_until_midnight = (tomorrow - now).total_seconds()
                    nap = random.randint(120, 900)
                    logger.info(
                        "[%s] Teto global (%d convites OK/dia) — pausa até após meia-noite em Lisboa (%ds + folga %ds).",
                        session_name,
                        MAX_ADDS_PROJECT_PER_DAY,
                        int(seconds_until_midnight),
                        nap,
                    )
                    await record_event(
                        session_name,
                        "day_sleep_project_cap",
                        f"tot_ok={tot_day}",
                        extra={"tot_ok": tot_day, "cap": MAX_ADDS_PROJECT_PER_DAY},
                    )
                    await asyncio.sleep(seconds_until_midnight + nap)
    finally:
        await _telethon_disconnect(client, session_name)


async def adder_worker_guarded(account, start_stagger_sec: float = 0):
    """Isola falhas: uma conta a saltar não rebenta o processo inteiro nem a outra conta."""
    session_name = account["session"]
    try:
        await adder_worker(account, start_stagger_sec)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception(
            "[%s] Trabalhador terminou com erro — a outra conta mantém-se. "
            "Vê o traceback; `pm2 restart` para voltar a tentar esta sessão.",
            session_name,
        )
        try:
            await record_event(
                session_name,
                "worker_crashed",
                repr(e)[:260],
                extra={"err": str(e)},
            )
        except Exception:
            pass


# ==========================================
# ENTRY POINT
# ==========================================
async def main():
    await init_db()
    if TELEGRAM_REGION_SPLIT:
        await migrate_pending_user_regions()
    free_b = _disk_free_bytes(_SCRIPT_DIR)
    if free_b >= 0 and free_b < DISK_WARN_FREE_MB * 1024 * 1024:
        logging.warning(
            "Pouco espaço em disco (~%d MiB livres em %s). O Telethon pode falhar; liberta espaço.",
            free_b // 1024 // 1024,
            _SCRIPT_DIR,
        )
    logging.info(
        "Modo: activo=%s | regiões=%s | convites=%s | scrape=%s | scrape_todas_as_contas=%s | contas_extra_também_global_pt_es=%s | "
        "excluir_admins_origem=%s | cap_projeto=%s/dia | horário_humano=%s | horário_humano_unificado=%s | fila_partição=%s | "
        "metas_equilíbrio=%s | pause_convite_x=%.2f",
        TELEGRAM_ACTIVE_MODE,
        TELEGRAM_REGION_SPLIT,
        TELEGRAM_INVITES_ENABLED,
        SCRAPE_ENABLED,
        SCRAPE_ALL_ACCOUNTS,
        SCRAPE_EXTRA_ACCOUNTS_ALSO_GLOBAL,
        EXCLUDE_SOURCE_GROUP_ADMINS,
        MAX_ADDS_PROJECT_PER_DAY,
        TELEGRAM_HUMAN_SCHEDULE,
        TELEGRAM_UNIFIED_HUMAN_SCHEDULE,
        TELEGRAM_QUEUE_PARTITION,
        TELEGRAM_BALANCE_DAILY_TARGETS,
        TELEGRAM_INVITE_PAUSE_FACTOR,
    )
    if TELEGRAM_REGION_SPLIT:
        for acc in ACCOUNTS:
            sn = acc["session"]
            reg = session_region(sn)
            pend = await count_pending_users(reg)
            label = "PT+ES (Joana/conta1)" if reg == REGION_PT_ES else "Europa (Jessy Pink/conta2)"
            logging.info(
                "[%s] região=%s (%s) | fila pending desta região=%d",
                sn,
                reg,
                label,
                pend,
            )
    _fx = _fixed_scrape_group_usernames()
    if len(ACCOUNTS) > 1 and not SCRAPE_ALL_ACCOUNTS and not TELEGRAM_REGION_SPLIT:
        logging.info(
            "Scrape contas extra (não a 1.ª): %s",
            ", ".join("@" + u for u in _fx) if _fx else "desativado — define TELEGRAM_FIXED_SCRAPE_GROUPS=grupo1,grupo2",
        )
    loop = asyncio.get_running_loop()

    def _asyncio_error_handler(_loop, context):
        msg = context.get("message", "")
        exc = context.get("exception")
        if exc:
            logger.error("asyncio (tarefa em segundo plano): %s", msg, exc_info=exc)
        else:
            logger.error("asyncio: %s | %s", msg, context)

    loop.set_exception_handler(_asyncio_error_handler)
    logger.info(
        "Arranque técnico: pid=%s python=%s | cwd_script=%s | env=%s | db=%s | target=%s | contas=%d | "
        "cap_projeto=%d/dia | login_timeout=%ss | sqlite_timeout=%ss | login_stagger=%ss/conta_extra | "
        "pause_convite=%.2f | fila_partição=%s | metas_equilíbrio=%s",
        os.getpid(),
        sys.version.split()[0],
        _SCRIPT_DIR,
        ENV_DOTENV_PATH,
        USERS_DB,
        TARGET_GROUP,
        len(ACCOUNTS),
        MAX_ADDS_PROJECT_PER_DAY,
        int(TELEGRAM_START_TIMEOUT_SEC),
        int(SQLITE_BUSY_TIMEOUT),
        int(WORKER_LOGIN_STAGGER_SEC),
        TELEGRAM_INVITE_PAUSE_FACTOR,
        TELEGRAM_QUEUE_PARTITION,
        TELEGRAM_BALANCE_DAILY_TARGETS,
    )

    tasks = []
    for i, account in enumerate(ACCOUNTS):
        stagger = float(i) * WORKER_LOGIN_STAGGER_SEC
        tasks.append(asyncio.create_task(adder_worker_guarded(account, start_stagger_sec=stagger)))
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    def _on_sigterm(signum, _frame):
        try:
            name = signal.Signals(signum).name
        except (ValueError, AttributeError):
            name = str(signum)
        logger.warning("Sinal %s (normal no `pm2 stop`/`restart`) — a sair.", name)
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _on_sigterm)
    except ValueError:
        pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Processo terminado (Ctrl+C).")
    except BaseException:
        logger.exception("Erro fatal no main — traceback completo acima.")
        raise