import sqlite3
import time
import re
import os
import shutil
import calendar as cal_module
from datetime import datetime, timedelta
from functools import lru_cache

import flask
import jwt


def get_default_database_path():
    env_database_path = os.getenv('DATABASE_PATH')
    if env_database_path:
        return env_database_path

    # Vercel serverless functions can only write to /tmp.
    if os.getenv('VERCEL'):
        return '/tmp/user_data.db'

    return 'user_data.db'


app = flask.Flask(__name__, template_folder='.')
DATABASE_PATH = get_default_database_path()
LEGACY_DATABASE_PATH = 'weekly_tracker.db'
DEFAULT_TASK_COLOR = '#007bff'
DEFAULT_DAY_START_HOUR = 2
DEFAULT_WEEK_START_DAY = 'sunday'
HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
VALID_WEEK_START_DAYS = {
    'sunday': 6,
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
}


@lru_cache(maxsize=1)
def get_supabase_jwks_client():
    supabase_url = str(os.getenv('SUPABASE_URL', '')).strip().rstrip('/')
    jwks_url = str(os.getenv('SUPABASE_JWKS_URL', '')).strip()
    if not jwks_url:
        if not supabase_url:
            raise RuntimeError('Missing SUPABASE_URL or SUPABASE_JWKS_URL')
        jwks_url = f'{supabase_url}/auth/v1/.well-known/jwks.json'
    return jwt.PyJWKClient(jwks_url)


@lru_cache(maxsize=1)
def get_supabase_issuer():
    env_issuer = str(os.getenv('SUPABASE_ISSUER', '')).strip()
    if env_issuer:
        return env_issuer
    supabase_url = str(os.getenv('SUPABASE_URL', '')).strip().rstrip('/')
    if not supabase_url:
        raise RuntimeError('Missing SUPABASE_URL or SUPABASE_ISSUER')
    return f'{supabase_url}/auth/v1'


def parse_bearer_token(auth_header):
    if not auth_header:
        return None
    auth_value = str(auth_header).strip()
    if not auth_value.lower().startswith('bearer '):
        return None
    token = auth_value[7:].strip()
    return token or None


def verify_supabase_token(token):
    jwks_client = get_supabase_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    issuer = get_supabase_issuer()
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=['RS256'],
        issuer=issuer,
        options={'verify_aud': False},
    )


def get_current_user_id():
    return str(flask.g.user_id)


@app.before_request
def require_api_authentication():
    if not flask.request.path.startswith('/api/'):
        return None

    token = parse_bearer_token(flask.request.headers.get('Authorization'))
    if not token:
        return flask.jsonify({'error': 'Unauthorized'}), 401

    try:
        claims = verify_supabase_token(token)
    except Exception:
        return flask.jsonify({'error': 'Unauthorized'}), 401

    user_id = str(claims.get('sub', '')).strip()
    if not user_id:
        return flask.jsonify({'error': 'Unauthorized'}), 401

    flask.g.user_id = user_id
    return None


def get_db():
    if 'db' not in flask.g:
        database_dir = os.path.dirname(DATABASE_PATH)
        if database_dir:
            os.makedirs(database_dir, exist_ok=True)
        if (not os.path.exists(DATABASE_PATH)) and os.path.exists(LEGACY_DATABASE_PATH):
            shutil.copy2(LEGACY_DATABASE_PATH, DATABASE_PATH)
        flask.g.db = sqlite3.connect(DATABASE_PATH)
        flask.g.db.row_factory = sqlite3.Row
        flask.g.db.execute('PRAGMA foreign_keys = ON')
    return flask.g.db


@app.teardown_appcontext
def close_db(exception):
    db = flask.g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL DEFAULT 'legacy',
            name TEXT NOT NULL,
            task_type TEXT NOT NULL CHECK(task_type IN ('weekly', 'monthly')),
            task_color TEXT NOT NULL DEFAULT '#007bff',
            elapsed_seconds INTEGER NOT NULL DEFAULT 0,
            running INTEGER NOT NULL DEFAULT 0,
            started_at INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS work_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            work_date TEXT NOT NULL,
            seconds INTEGER NOT NULL,
            entry_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS user_settings (
            owner_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY(owner_id, key)
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS daily_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL DEFAULT 'legacy',
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'daily',
            task_kind TEXT NOT NULL DEFAULT 'checkbox',
            target_minutes INTEGER,
            task_unit TEXT NOT NULL DEFAULT '',
            weekly_target_minutes INTEGER,
            color TEXT NOT NULL DEFAULT '#007bff',
            no_expiry INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS daily_task_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            daily_task_id INTEGER NOT NULL,
            completion_date TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            done_minutes INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(daily_task_id, completion_date),
            FOREIGN KEY(daily_task_id) REFERENCES daily_tasks(id) ON DELETE CASCADE
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS daily_task_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            daily_task_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            value INTEGER,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(daily_task_id) REFERENCES daily_tasks(id) ON DELETE CASCADE
        )
        '''
    )
    columns = db.execute("PRAGMA table_info(tasks)").fetchall()
    column_names = {column['name'] for column in columns}
    if 'task_color' not in column_names:
        db.execute(
            "ALTER TABLE tasks ADD COLUMN task_color TEXT NOT NULL DEFAULT '#007bff'"
        )
    if 'owner_id' not in column_names:
        db.execute(
            "ALTER TABLE tasks ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'legacy'"
        )
    if 'is_work' not in column_names:
        db.execute(
            "ALTER TABLE tasks ADD COLUMN is_work INTEGER NOT NULL DEFAULT 0"
        )
    # Migrate daily_tasks table for recurrence-based design
    dt_columns = db.execute("PRAGMA table_info(daily_tasks)").fetchall()
    dt_column_names = {col['name'] for col in dt_columns}
    if 'owner_id' not in dt_column_names:
        db.execute("ALTER TABLE daily_tasks ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'legacy'")
    if 'recurrence' not in dt_column_names:
        db.execute("ALTER TABLE daily_tasks ADD COLUMN recurrence TEXT NOT NULL DEFAULT 'daily'")
        db.execute("UPDATE daily_tasks SET recurrence = 'none' WHERE no_expiry = 1")
        db.execute("UPDATE daily_tasks SET recurrence = 'weekly' WHERE category = 'weekly'")
    if 'persistent_done' not in dt_column_names:
        db.execute("ALTER TABLE daily_tasks ADD COLUMN persistent_done INTEGER NOT NULL DEFAULT 0")
    if 'persistent_done_minutes' not in dt_column_names:
        db.execute("ALTER TABLE daily_tasks ADD COLUMN persistent_done_minutes INTEGER NOT NULL DEFAULT 0")
    if 'due_date' not in dt_column_names:
        db.execute("ALTER TABLE daily_tasks ADD COLUMN due_date TEXT")
    if 'task_unit' not in dt_column_names:
        db.execute("ALTER TABLE daily_tasks ADD COLUMN task_unit TEXT NOT NULL DEFAULT ''")

    db.execute("UPDATE daily_tasks SET recurrence = 'one_time' WHERE recurrence = 'none'")
    db.execute("UPDATE daily_tasks SET task_kind = 'integer' WHERE task_kind = 'timed'")
    db.execute('CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_tasks_owner_running ON tasks(owner_id, running)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_daily_tasks_owner ON daily_tasks(owner_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_work_logs_task_date ON work_logs(task_id, work_date)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_daily_logs_task_date ON daily_task_logs(daily_task_id, log_date)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_daily_completions_task_date ON daily_task_completions(daily_task_id, completion_date)')
    db.commit()


def get_day_start_hour():
    db = get_db()
    user_id = get_current_user_id()
    row = db.execute(
        "SELECT value FROM user_settings WHERE owner_id = ? AND key = 'day_start_hour'",
        (user_id,),
    ).fetchone()
    if not row:
        return DEFAULT_DAY_START_HOUR
    try:
        value = int(row['value'])
    except (TypeError, ValueError):
        return DEFAULT_DAY_START_HOUR
    if value < 0 or value > 23:
        return DEFAULT_DAY_START_HOUR
    return value


def get_logical_now(day_start_hour):
    return datetime.now() - timedelta(hours=day_start_hour)


def get_week_start_day():
    db = get_db()
    user_id = get_current_user_id()
    row = db.execute(
        "SELECT value FROM user_settings WHERE owner_id = ? AND key = 'week_start_day'",
        (user_id,),
    ).fetchone()
    if not row:
        return DEFAULT_WEEK_START_DAY

    value = str(row['value']).strip().lower()
    if value not in VALID_WEEK_START_DAYS:
        return DEFAULT_WEEK_START_DAY
    return value


def get_week_start_date(date_obj, week_start_day):
    start_weekday = VALID_WEEK_START_DAYS.get(week_start_day, VALID_WEEK_START_DAYS[DEFAULT_WEEK_START_DAY])
    days_since_start = (date_obj.weekday() - start_weekday) % 7
    return date_obj - timedelta(days=days_since_start)


def normalize_daily_task_recurrence(value):
    recurrence = str(value or 'daily').strip().lower()
    if recurrence == 'none':
        recurrence = 'one_time'
    if recurrence not in ('daily', 'weekly', 'monthly', 'one_time'):
        recurrence = 'daily'
    return recurrence


def normalize_daily_task_kind(value):
    task_kind = str(value or 'checkbox').strip().lower()
    if task_kind == 'timed':
        task_kind = 'integer'
    if task_kind not in ('checkbox', 'integer'):
        task_kind = 'checkbox'
    return task_kind


def parse_iso_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def get_monthly_due_date(today_date, due_date_obj):
    if not due_date_obj:
        last_day = cal_module.monthrange(today_date.year, today_date.month)[1]
        return today_date.replace(day=last_day)

    due_day = due_date_obj.day

    this_last_day = cal_module.monthrange(today_date.year, today_date.month)[1]
    this_due_day = min(due_day, this_last_day)
    this_due_date = today_date.replace(day=this_due_day)
    if today_date <= this_due_date:
        return this_due_date

    next_month_start = shift_month(today_date.replace(day=1), 1)
    next_last_day = cal_module.monthrange(next_month_start.year, next_month_start.month)[1]
    next_due_day = min(due_day, next_last_day)
    return next_month_start.replace(day=next_due_day)


def get_task_period_key_and_end(recurrence, today_date, week_start_day, due_date_obj=None):
    if recurrence == 'daily':
        return today_date.isoformat(), today_date
    if recurrence == 'weekly':
        week_start = get_week_start_date(today_date, week_start_day)
        week_end = week_start + timedelta(days=6)
        return week_start.isoformat(), week_end
    if recurrence == 'monthly':
        monthly_due = get_monthly_due_date(today_date, due_date_obj)
        period_key = f"monthly:{monthly_due.isoformat()}"
        return period_key, monthly_due
    return 'one_time', due_date_obj


def compute_ends_in_days(recurrence, period_end_date, due_date_obj, today_date):
    if recurrence in ('daily', 'weekly', 'monthly') and period_end_date:
        return (period_end_date - today_date).days
    if recurrence == 'one_time' and due_date_obj:
        return (due_date_obj - today_date).days
    return None


def get_logical_date_for_timestamp(timestamp_seconds, day_start_hour):
    return (datetime.fromtimestamp(timestamp_seconds) - timedelta(hours=day_start_hour)).date()


def get_logical_day_start_timestamp(now_ts, day_start_hour):
    logical_date = get_logical_date_for_timestamp(now_ts, day_start_hour)
    day_start = datetime.combine(logical_date, datetime.min.time()) + timedelta(hours=day_start_hour)
    return int(day_start.timestamp())


def shift_month(date_obj, months_delta):
    month_index = (date_obj.year * 12 + (date_obj.month - 1)) + months_delta
    year = month_index // 12
    month = (month_index % 12) + 1
    return date_obj.replace(year=year, month=month, day=1)


def task_to_dict(task_row):
    now_ts = int(time.time())
    base_elapsed = int(task_row['elapsed_seconds'])
    running = bool(task_row['running'])
    started_at = task_row['started_at']

    if running and started_at:
        base_elapsed += max(0, now_ts - int(started_at))

    return {
        'id': int(task_row['id']),
        'name': task_row['name'],
        'task_type': task_row['task_type'],
        'task_color': task_row['task_color'] or DEFAULT_TASK_COLOR,
        'is_work': bool(task_row['is_work']),
        'elapsed': base_elapsed,
        'running': running,
    }


def get_today_color_breakdown():
    db = get_db()
    user_id = get_current_user_id()
    day_start_hour = get_day_start_hour()
    today = get_logical_now(day_start_hour).date().isoformat()

    totals = {}

    logged_rows = db.execute(
        '''
        SELECT t.task_color, COALESCE(SUM(w.seconds), 0) AS total_seconds
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.work_date = ? AND t.owner_id = ?
        GROUP BY t.task_color
        ''',
        (today, user_id),
    ).fetchall()

    for row in logged_rows:
        color = row['task_color'] or DEFAULT_TASK_COLOR
        totals[color] = totals.get(color, 0) + int(row['total_seconds'])

    running_rows = db.execute(
        'SELECT started_at, task_color FROM tasks WHERE owner_id = ? AND running = 1 AND started_at IS NOT NULL',
        (user_id,),
    ).fetchall()

    now_ts = int(time.time())
    logical_day_start_ts = get_logical_day_start_timestamp(now_ts, day_start_hour)
    for running_row in running_rows:
        color = running_row['task_color'] or DEFAULT_TASK_COLOR
        started_at = int(running_row['started_at'])
        duration = max(0, now_ts - max(started_at, logical_day_start_ts))
        totals[color] = totals.get(color, 0) + duration

    breakdown = []
    for color, seconds in totals.items():
        if seconds > 0:
            breakdown.append({'color': color, 'seconds': seconds})

    breakdown.sort(key=lambda entry: entry['seconds'], reverse=True)
    return breakdown


def get_today_total_seconds():
    db = get_db()
    user_id = get_current_user_id()
    day_start_hour = get_day_start_hour()
    today = get_logical_now(day_start_hour).date().isoformat()
    row = db.execute(
        '''
        SELECT COALESCE(SUM(w.seconds), 0) AS total
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.work_date = ? AND t.owner_id = ?
        ''',
        (today, user_id),
    ).fetchone()
    logged_total = int(row['total']) if row else 0

    running_rows = db.execute(
        'SELECT started_at FROM tasks WHERE owner_id = ? AND running = 1 AND started_at IS NOT NULL',
        (user_id,),
    ).fetchall()

    now_ts = int(time.time())
    logical_day_start_ts = get_logical_day_start_timestamp(now_ts, day_start_hour)
    running_total = 0
    for running_row in running_rows:
        started_at = int(running_row['started_at'])
        running_total += max(0, now_ts - max(started_at, logical_day_start_ts))

    return logged_total + running_total


def get_today_task_seconds():
    db = get_db()
    user_id = get_current_user_id()
    day_start_hour = get_day_start_hour()
    today = get_logical_now(day_start_hour).date().isoformat()

    rows = db.execute(
        '''
        SELECT w.task_id, COALESCE(SUM(w.seconds), 0) AS total
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.work_date = ? AND t.owner_id = ?
        GROUP BY w.task_id
        ''',
        (today, user_id),
    ).fetchall()

    result = {}
    for row in rows:
        result[int(row['task_id'])] = int(row['total'])

    running_rows = db.execute(
        'SELECT id, started_at FROM tasks WHERE owner_id = ? AND running = 1 AND started_at IS NOT NULL',
        (user_id,),
    ).fetchall()

    now_ts = int(time.time())
    logical_day_start_ts = get_logical_day_start_timestamp(now_ts, day_start_hour)
    for row in running_rows:
        task_id = int(row['id'])
        started_at = int(row['started_at'])
        duration = max(0, now_ts - max(started_at, logical_day_start_ts))
        result[task_id] = result.get(task_id, 0) + duration

    return result


def get_weekly_color_breakdown():
    db = get_db()
    user_id = get_current_user_id()
    day_start_hour = get_day_start_hour()
    week_start_day = get_week_start_day()
    today_date = get_logical_now(day_start_hour).date()
    week_start = get_week_start_date(today_date, week_start_day)
    week_end = week_start + timedelta(days=6)

    day_data = {}
    for i in range(7):
        date_obj = week_start + timedelta(days=i)
        date_key = date_obj.isoformat()
        day_data[date_key] = {
            'date': date_key,
            'weekday': date_obj.strftime('%a'),
            'total_seconds': 0,
            'colors': {},
        }

    logged_rows = db.execute(
        '''
        SELECT w.work_date, t.task_color, COALESCE(SUM(w.seconds), 0) AS total_seconds
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.work_date BETWEEN ? AND ? AND t.is_work = 1 AND t.owner_id = ?
        GROUP BY w.work_date, t.task_color
        ''',
        (week_start.isoformat(), week_end.isoformat(), user_id),
    ).fetchall()

    for row in logged_rows:
        work_date = row['work_date']
        if work_date not in day_data:
            continue
        color = row['task_color'] or DEFAULT_TASK_COLOR
        seconds = int(row['total_seconds'])
        day_data[work_date]['colors'][color] = day_data[work_date]['colors'].get(color, 0) + seconds
        day_data[work_date]['total_seconds'] += seconds

    running_rows = db.execute(
        'SELECT started_at, task_color FROM tasks WHERE owner_id = ? AND running = 1 AND started_at IS NOT NULL AND is_work = 1',
        (user_id,),
    ).fetchall()

    today_key = today_date.isoformat()
    now_ts = int(time.time())
    logical_day_start_ts = get_logical_day_start_timestamp(now_ts, day_start_hour)
    for running_row in running_rows:
        started_at = int(running_row['started_at'])
        duration = max(0, now_ts - max(started_at, logical_day_start_ts))
        if duration <= 0 or today_key not in day_data:
            continue
        color = running_row['task_color'] or DEFAULT_TASK_COLOR
        day_data[today_key]['colors'][color] = day_data[today_key]['colors'].get(color, 0) + duration
        day_data[today_key]['total_seconds'] += duration

    breakdown = []
    for i in range(7):
        date_obj = week_start + timedelta(days=i)
        date_key = date_obj.isoformat()
        entry = day_data[date_key]
        colors = [
            {'color': color, 'seconds': seconds}
            for color, seconds in entry['colors'].items()
            if seconds > 0
        ]
        colors.sort(key=lambda color_entry: color_entry['seconds'], reverse=True)
        breakdown.append(
            {
                'date': entry['date'],
                'weekday': entry['weekday'],
                'total_seconds': entry['total_seconds'],
                'colors': colors,
            }
        )

    return breakdown


def get_monthly_overview(month_count=6):
    db = get_db()
    user_id = get_current_user_id()
    day_start_hour = get_day_start_hour()
    logical_today = get_logical_now(day_start_hour).date()
    current_month_start = logical_today.replace(day=1)
    oldest_month_start = shift_month(current_month_start, -(month_count - 1))

    month_map = {}
    month_order = []
    for offset in range(month_count):
        month_start = shift_month(oldest_month_start, offset)
        month_key = month_start.strftime('%Y-%m')
        month_map[month_key] = {
            'month_key': month_key,
            'label': month_start.strftime('%b %Y'),
            'total_seconds': 0,
            'colors': {},
        }
        month_order.append(month_key)

    logged_rows = db.execute(
        '''
        SELECT substr(w.work_date, 1, 7) AS month_key, t.task_color,
               COALESCE(SUM(w.seconds), 0) AS total_seconds
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.work_date >= ? AND t.is_work = 1 AND t.owner_id = ?
        GROUP BY substr(w.work_date, 1, 7), t.task_color
        ''',
        (oldest_month_start.isoformat(), user_id),
    ).fetchall()

    for row in logged_rows:
        month_key = row['month_key']
        if month_key in month_map:
            color = row['task_color'] or DEFAULT_TASK_COLOR
            secs = int(row['total_seconds'])
            month_map[month_key]['total_seconds'] += secs
            month_map[month_key]['colors'][color] = month_map[month_key]['colors'].get(color, 0) + secs

    running_rows = db.execute(
        'SELECT started_at, task_color FROM tasks WHERE owner_id = ? AND running = 1 AND started_at IS NOT NULL AND is_work = 1',
        (user_id,),
    ).fetchall()

    now_ts = int(time.time())
    logical_day_start_ts = get_logical_day_start_timestamp(now_ts, day_start_hour)
    current_month_key = logical_today.strftime('%Y-%m')
    if current_month_key in month_map:
        for row in running_rows:
            started_at = int(row['started_at'])
            color = row['task_color'] or DEFAULT_TASK_COLOR
            duration = max(0, now_ts - max(started_at, logical_day_start_ts))
            if duration > 0:
                month_map[current_month_key]['total_seconds'] += duration
                month_map[current_month_key]['colors'][color] = month_map[current_month_key]['colors'].get(color, 0) + duration

    result = []
    for month_key in month_order:
        entry = month_map[month_key]
        colors = [{'color': c, 'seconds': s} for c, s in entry['colors'].items() if s > 0]
        colors.sort(key=lambda x: x['seconds'], reverse=True)
        result.append({
            'month_key': entry['month_key'],
            'label': entry['label'],
            'total_seconds': entry['total_seconds'],
            'colors': colors,
        })
    return result


@app.route('/')
def hello():
    return flask.render_template(
        'index.html',
        supabase_url=str(os.getenv('SUPABASE_URL', '')).strip(),
        supabase_anon_key=str(os.getenv('SUPABASE_ANON_KEY', '')).strip(),
    )


@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    db = get_db()
    user_id = get_current_user_id()
    rows = db.execute(
        'SELECT id, name, task_type, task_color, is_work, elapsed_seconds, running, started_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC',
        (user_id,),
    ).fetchall()

    day_start_hour = get_day_start_hour()
    response = {
        'weekly': [],
        'monthly': [],
        'today_total_seconds': get_today_total_seconds(),
        'today_color_breakdown': get_today_color_breakdown(),
        'today_task_seconds': get_today_task_seconds(),
        'weekly_color_breakdown': get_weekly_color_breakdown(),
        'weekly_chart_max_seconds': 14 * 3600,
        'monthly_overview': get_monthly_overview(),
        'day_start_hour': day_start_hour,
        'week_start_day': get_week_start_day(),
        'current_logical_date': get_logical_now(day_start_hour).date().isoformat(),
    }

    for row in rows:
        task_data = task_to_dict(row)
        response[task_data['task_type']].append(task_data)

    return flask.jsonify(response)


@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = flask.request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    task_type = data.get('task_type')
    initial_seconds = int(data.get('initial_seconds', 0) or 0)
    task_color = str(data.get('task_color', DEFAULT_TASK_COLOR)).strip() or DEFAULT_TASK_COLOR

    if not name:
        return flask.jsonify({'error': 'Task name is required'}), 400
    if task_type not in ('weekly', 'monthly'):
        return flask.jsonify({'error': 'Invalid task type'}), 400
    if initial_seconds < 0:
        return flask.jsonify({'error': 'Initial time cannot be negative'}), 400
    if not HEX_COLOR_RE.match(task_color):
        return flask.jsonify({'error': 'Invalid task color'}), 400

    db = get_db()
    user_id = get_current_user_id()
    cursor = db.execute(
        'INSERT INTO tasks (owner_id, name, task_type, task_color, elapsed_seconds) VALUES (?, ?, ?, ?, ?)',
        (user_id, name, task_type, task_color, initial_seconds),
    )
    task_id = cursor.lastrowid

    if initial_seconds > 0:
        day_start_hour = get_day_start_hour()
        today = get_logical_now(day_start_hour).date().isoformat()
        db.execute(
            'INSERT INTO work_logs (task_id, work_date, seconds, entry_type) VALUES (?, ?, ?, ?)',
            (task_id, today, initial_seconds, 'manual_create'),
        )

    db.commit()
    return flask.jsonify({'ok': True, 'task_id': task_id}), 201


@app.route('/api/tasks/<int:task_id>/start', methods=['POST'])
def start_task(task_id):
    db = get_db()
    user_id = get_current_user_id()
    task = db.execute(
        'SELECT id, running FROM tasks WHERE id = ? AND owner_id = ?',
        (task_id, user_id),
    ).fetchone()

    if not task:
        return flask.jsonify({'error': 'Task not found'}), 404
    if task['running']:
        return flask.jsonify({'ok': True})

    db.execute(
        'UPDATE tasks SET running = 1, started_at = ? WHERE id = ? AND owner_id = ?',
        (int(time.time()), task_id, user_id),
    )
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>/stop', methods=['POST'])
def stop_task(task_id):
    db = get_db()
    user_id = get_current_user_id()
    task = db.execute(
        'SELECT id, elapsed_seconds, running, started_at FROM tasks WHERE id = ? AND owner_id = ?',
        (task_id, user_id),
    ).fetchone()

    if not task:
        return flask.jsonify({'error': 'Task not found'}), 404
    if not task['running']:
        return flask.jsonify({'ok': True})

    now_ts = int(time.time())
    started_at = int(task['started_at']) if task['started_at'] else now_ts
    duration = max(0, now_ts - started_at)
    new_elapsed = int(task['elapsed_seconds']) + duration

    db.execute(
        'UPDATE tasks SET elapsed_seconds = ?, running = 0, started_at = NULL WHERE id = ? AND owner_id = ?',
        (new_elapsed, task_id, user_id),
    )

    if duration > 0:
        day_start_hour = get_day_start_hour()
        today = get_logical_date_for_timestamp(now_ts, day_start_hour).isoformat()
        db.execute(
            'INSERT INTO work_logs (task_id, work_date, seconds, entry_type) VALUES (?, ?, ?, ?)',
            (task_id, today, duration, 'timer'),
        )

    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>/manual_time', methods=['POST'])
def add_manual_time(task_id):
    data = flask.request.get_json(silent=True) or {}
    seconds = int(data.get('seconds', 0) or 0)
    work_date = str(data.get('work_date', '')).strip()

    if seconds <= 0:
        return flask.jsonify({'error': 'Seconds must be greater than 0'}), 400

    if work_date:
        try:
            datetime.strptime(work_date, '%Y-%m-%d')
        except ValueError:
            return flask.jsonify({'error': 'Invalid work_date format. Use YYYY-MM-DD'}), 400
    else:
        day_start_hour = get_day_start_hour()
        work_date = get_logical_now(day_start_hour).date().isoformat()

    db = get_db()
    user_id = get_current_user_id()
    task = db.execute(
        'SELECT id, elapsed_seconds FROM tasks WHERE id = ? AND owner_id = ?',
        (task_id, user_id),
    ).fetchone()

    if not task:
        return flask.jsonify({'error': 'Task not found'}), 404

    new_elapsed = int(task['elapsed_seconds']) + seconds
    db.execute(
        'UPDATE tasks SET elapsed_seconds = ? WHERE id = ? AND owner_id = ?',
        (new_elapsed, task_id, user_id),
    )

    db.execute(
        'INSERT INTO work_logs (task_id, work_date, seconds, entry_type) VALUES (?, ?, ?, ?)',
        (task_id, work_date, seconds, 'manual_add'),
    )
    db.commit()

    return flask.jsonify({'ok': True})


@app.route('/api/settings/day_start', methods=['PUT'])
def update_day_start_hour():
    data = flask.request.get_json(silent=True) or {}
    day_start_hour = int(data.get('day_start_hour', DEFAULT_DAY_START_HOUR) or 0)

    if day_start_hour < 0 or day_start_hour > 23:
        return flask.jsonify({'error': 'day_start_hour must be between 0 and 23'}), 400

    db = get_db()
    user_id = get_current_user_id()
    db.execute(
        '''
        INSERT INTO user_settings (owner_id, key, value) VALUES (?, ?, ?)
        ON CONFLICT(owner_id, key) DO UPDATE SET value = excluded.value
        ''',
        (user_id, 'day_start_hour', str(day_start_hour)),
    )
    db.commit()
    return flask.jsonify({'ok': True, 'day_start_hour': day_start_hour})


@app.route('/api/settings/week_start', methods=['PUT'])
def update_week_start_day():
    data = flask.request.get_json(silent=True) or {}
    week_start_day = str(data.get('week_start_day', DEFAULT_WEEK_START_DAY)).strip().lower()

    if week_start_day not in VALID_WEEK_START_DAYS:
        return flask.jsonify({'error': 'week_start_day must be one of sunday..saturday'}), 400

    db = get_db()
    user_id = get_current_user_id()
    db.execute(
        '''
        INSERT INTO user_settings (owner_id, key, value) VALUES (?, ?, ?)
        ON CONFLICT(owner_id, key) DO UPDATE SET value = excluded.value
        ''',
        (user_id, 'week_start_day', week_start_day),
    )
    db.commit()
    return flask.jsonify({'ok': True, 'week_start_day': week_start_day})


@app.route('/api/tasks/<int:task_id>/is_work', methods=['PUT'])
def update_task_is_work(task_id):
    data = flask.request.get_json(silent=True) or {}
    is_work = 1 if data.get('is_work') else 0

    db = get_db()
    user_id = get_current_user_id()
    task = db.execute('SELECT id FROM tasks WHERE id = ? AND owner_id = ?', (task_id, user_id)).fetchone()
    if not task:
        return flask.jsonify({'error': 'Task not found'}), 404

    db.execute('UPDATE tasks SET is_work = ? WHERE id = ? AND owner_id = ?', (is_work, task_id, user_id))
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>/color', methods=['PUT'])
def update_task_color(task_id):
    data = flask.request.get_json(silent=True) or {}
    task_color = str(data.get('task_color', '')).strip()

    if not HEX_COLOR_RE.match(task_color):
        return flask.jsonify({'error': 'Invalid task color'}), 400

    db = get_db()
    user_id = get_current_user_id()
    task = db.execute('SELECT id FROM tasks WHERE id = ? AND owner_id = ?', (task_id, user_id)).fetchone()
    if not task:
        return flask.jsonify({'error': 'Task not found'}), 404

    db.execute('UPDATE tasks SET task_color = ? WHERE id = ? AND owner_id = ?', (task_color, task_id, user_id))
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    db = get_db()
    user_id = get_current_user_id()
    db.execute('DELETE FROM tasks WHERE id = ? AND owner_id = ?', (task_id, user_id))
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/day_logs', methods=['GET'])
def get_day_logs():
    work_date = flask.request.args.get('date', '').strip()
    if not work_date:
        return flask.jsonify({'error': 'date parameter is required'}), 400
    try:
        datetime.strptime(work_date, '%Y-%m-%d')
    except ValueError:
        return flask.jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    db = get_db()
    user_id = get_current_user_id()
    rows = db.execute(
        '''
        SELECT w.id, w.task_id, w.work_date, w.seconds, w.entry_type, w.created_at,
               t.name AS task_name, t.task_color
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.work_date = ? AND t.owner_id = ?
        ORDER BY w.created_at DESC, w.id DESC
        ''',
        (work_date, user_id),
    ).fetchall()

    logs = []
    for row in rows:
        logs.append({
            'id': int(row['id']),
            'task_id': int(row['task_id']),
            'task_name': row['task_name'],
            'task_color': row['task_color'] or DEFAULT_TASK_COLOR,
            'work_date': row['work_date'],
            'seconds': int(row['seconds']),
            'entry_type': row['entry_type'],
            'created_at': row['created_at'],
        })

    return flask.jsonify({'logs': logs, 'work_date': work_date})


@app.route('/api/work_logs/<int:log_id>', methods=['PUT'])
def update_work_log(log_id):
    data = flask.request.get_json(silent=True) or {}
    seconds = int(data.get('seconds', 0) or 0)

    if seconds <= 0:
        return flask.jsonify({'error': 'Seconds must be greater than 0'}), 400

    db = get_db()
    user_id = get_current_user_id()
    log = db.execute(
        '''
        SELECT w.id, w.task_id, w.seconds
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.id = ? AND t.owner_id = ?
        ''',
        (log_id, user_id),
    ).fetchone()
    if not log:
        return flask.jsonify({'error': 'Work log not found'}), 404

    old_seconds = int(log['seconds'])
    diff = seconds - old_seconds
    db.execute('UPDATE work_logs SET seconds = ? WHERE id = ?', (seconds, log_id))
    db.execute(
        'UPDATE tasks SET elapsed_seconds = MAX(0, elapsed_seconds + ?) WHERE id = ? AND owner_id = ?',
        (diff, int(log['task_id']), user_id),
    )
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/work_logs/<int:log_id>', methods=['DELETE'])
def delete_work_log(log_id):
    db = get_db()
    user_id = get_current_user_id()
    log = db.execute(
        '''
        SELECT w.id, w.task_id, w.seconds
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.id = ? AND t.owner_id = ?
        ''',
        (log_id, user_id),
    ).fetchone()
    if not log:
        return flask.jsonify({'error': 'Work log not found'}), 404

    seconds = int(log['seconds'])
    db.execute('DELETE FROM work_logs WHERE id = ?', (log_id,))
    db.execute(
        'UPDATE tasks SET elapsed_seconds = MAX(0, elapsed_seconds - ?) WHERE id = ? AND owner_id = ?',
        (seconds, int(log['task_id']), user_id),
    )
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/monthly_calendar', methods=['GET'])
def get_monthly_calendar():
    year_str = flask.request.args.get('year', '').strip()
    month_str = flask.request.args.get('month', '').strip()

    day_start_hour = get_day_start_hour()
    logical_today = get_logical_now(day_start_hour).date()

    try:
        year = int(year_str) if year_str else logical_today.year
        month = int(month_str) if month_str else logical_today.month
        if not (1 <= month <= 12):
            raise ValueError('Invalid month')
        month_start = logical_today.replace(year=year, month=month, day=1)
    except ValueError:
        return flask.jsonify({'error': 'Invalid year/month'}), 400

    import calendar as cal_module
    days_in_month = cal_module.monthrange(year, month)[1]
    month_end = month_start.replace(day=days_in_month)

    db = get_db()
    user_id = get_current_user_id()
    rows = db.execute(
        '''
        SELECT w.work_date, t.task_color, COALESCE(SUM(w.seconds), 0) AS total_seconds
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.work_date BETWEEN ? AND ? AND t.owner_id = ?
        GROUP BY w.work_date, t.task_color
        ORDER BY w.work_date
        ''',
        (month_start.isoformat(), month_end.isoformat(), user_id),
    ).fetchall()

    day_map = {}
    for row in rows:
        d = row['work_date']
        if d not in day_map:
            day_map[d] = {'total_seconds': 0, 'colors': {}}
        color = row['task_color'] or DEFAULT_TASK_COLOR
        secs = int(row['total_seconds'])
        day_map[d]['total_seconds'] += secs
        day_map[d]['colors'][color] = day_map[d]['colors'].get(color, 0) + secs

    days = []
    for day_num in range(1, days_in_month + 1):
        d = month_start.replace(day=day_num).isoformat()
        entry = day_map.get(d, {'total_seconds': 0, 'colors': {}})
        colors = [{'color': c, 'seconds': s} for c, s in entry['colors'].items() if s > 0]
        colors.sort(key=lambda x: x['seconds'], reverse=True)
        days.append({
            'date': d,
            'day': day_num,
            'total_seconds': entry['total_seconds'],
            'colors': colors,
        })

    return flask.jsonify({
        'year': year,
        'month': month,
        'month_label': month_start.strftime('%B %Y'),
        'days': days,
        'today': logical_today.isoformat(),
    })


# ── Daily Tasks ────────────────────────────────────────────────────────────────

def daily_task_to_dict(row):
    keys = row.keys()
    raw_recurrence = row['recurrence'] if 'recurrence' in keys else ('one_time' if row['no_expiry'] else 'daily')
    recurrence = normalize_daily_task_recurrence(raw_recurrence)
    task_kind = normalize_daily_task_kind(row['task_kind'])
    return {
        'id': int(row['id']),
        'name': row['name'],
        'recurrence': recurrence,
        'task_kind': task_kind,
        'target_minutes': row['target_minutes'],
        'task_unit': str(row['task_unit'] or '').strip(),
        'color': row['color'] or DEFAULT_TASK_COLOR,
        'sort_order': int(row['sort_order']),
        'due_date': row['due_date'] if 'due_date' in keys else None,
    }


@app.route('/api/daily_tasks', methods=['GET'])
def get_daily_tasks():
    db = get_db()
    user_id = get_current_user_id()
    day_start_hour = get_day_start_hour()
    week_start_day = get_week_start_day()
    today_date = get_logical_now(day_start_hour).date()
    today = today_date.isoformat()
    week_start = get_week_start_date(today_date, week_start_day).isoformat()

    rows = db.execute('SELECT * FROM daily_tasks WHERE owner_id = ? ORDER BY sort_order, id', (user_id,)).fetchall()
    task_ids = [int(r['id']) for r in rows]

    completions_by_task = {}
    if task_ids:
        placeholders = ','.join('?' * len(task_ids))
        comp_rows = db.execute(
            f'SELECT * FROM daily_task_completions WHERE daily_task_id IN ({placeholders})',
            task_ids,
        ).fetchall()
        for c in comp_rows:
            tid = int(c['daily_task_id'])
            key = c['completion_date']
            if tid not in completions_by_task:
                completions_by_task[tid] = {}
            completions_by_task[tid][key] = {
                'done': bool(c['done']),
                'done_minutes': int(c['done_minutes'] or 0),
            }

    items = []
    for row in rows:
        d = daily_task_to_dict(row)
        tid = d['id']
        recurrence = d['recurrence']
        task_kind = d['task_kind']
        due_date_obj = parse_iso_date(d.get('due_date'))
        period_key, period_end_date = get_task_period_key_and_end(
            recurrence,
            today_date,
            week_start_day,
            due_date_obj,
        )

        comp = completions_by_task.get(tid, {}).get(period_key, {})
        done_minutes = int(comp.get('done_minutes', 0) or 0)
        done = bool(comp.get('done', False))

        if recurrence == 'one_time' and not comp:
            done = bool(row['persistent_done'])
            done_minutes = int(row['persistent_done_minutes'] or 0)

        target = int(d['target_minutes'] or 0)
        if task_kind == 'integer' and target > 0:
            done = done_minutes >= target

        d['period_key'] = period_key
        d['period_end_date'] = period_end_date.isoformat() if period_end_date else None
        d['ends_in_days'] = compute_ends_in_days(recurrence, period_end_date, due_date_obj, today_date)
        d['done'] = done
        d['done_minutes'] = done_minutes
        items.append(d)

    items.sort(
        key=lambda item: (
            item['ends_in_days'] is None,
            item['ends_in_days'] if item['ends_in_days'] is not None else 10**9,
            item['name'].lower(),
        )
    )

    return flask.jsonify({
        'items': items,
        'weekly': [i for i in items if i['recurrence'] == 'weekly'],
        'daily': [i for i in items if i['recurrence'] == 'daily'],
        'monthly': [i for i in items if i['recurrence'] == 'monthly'],
        'one_time': [i for i in items if i['recurrence'] == 'one_time'],
        'no_expiry': [i for i in items if i['recurrence'] == 'one_time' and not i.get('due_date')],
        'today': today,
        'week_start': week_start,
        'week_start_day': week_start_day,
    })


@app.route('/api/daily_tasks', methods=['POST'])
def create_daily_task():
    data = flask.request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return flask.jsonify({'error': 'name required'}), 400

    recurrence = normalize_daily_task_recurrence(data.get('recurrence', 'daily'))

    task_kind = normalize_daily_task_kind(data.get('task_kind', 'checkbox'))
    if task_kind not in ('checkbox', 'integer'):
        return flask.jsonify({'error': 'task_kind must be checkbox or integer'}), 400

    target_minutes = data.get('target_minutes')
    if target_minutes is not None:
        target_minutes = max(1, int(target_minutes))

    task_unit = str(data.get('task_unit', '')).strip()
    if len(task_unit) > 20:
        task_unit = task_unit[:20]

    due_date_raw = data.get('due_date', '')
    due_date = '' if due_date_raw is None else str(due_date_raw).strip()
    due_date_value = None
    if due_date:
        parsed_due_date = parse_iso_date(due_date)
        if not parsed_due_date:
            return flask.jsonify({'error': 'due_date must be YYYY-MM-DD'}), 400
        due_date_value = parsed_due_date.isoformat()

    color = str(data.get('color', DEFAULT_TASK_COLOR)).strip() or DEFAULT_TASK_COLOR
    if not HEX_COLOR_RE.match(color):
        return flask.jsonify({'error': 'Invalid color'}), 400

    no_expiry = 1 if recurrence == 'one_time' else 0
    db = get_db()
    user_id = get_current_user_id()
    max_order = db.execute('SELECT COALESCE(MAX(sort_order), -1) FROM daily_tasks WHERE owner_id = ?', (user_id,)).fetchone()[0]
    cursor = db.execute(
          '''INSERT INTO daily_tasks (owner_id, name, category, task_kind, target_minutes, task_unit, color, no_expiry, recurrence, sort_order, due_date)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
          (user_id, name, recurrence, task_kind, target_minutes, task_unit, color, no_expiry, recurrence, int(max_order) + 1, due_date_value),
    )
    db.commit()
    return flask.jsonify({'ok': True, 'id': cursor.lastrowid}), 201


@app.route('/api/daily_tasks/<int:task_id>', methods=['PUT'])
def update_daily_task(task_id):
    data = flask.request.get_json(silent=True) or {}
    db = get_db()
    user_id = get_current_user_id()
    row = db.execute('SELECT * FROM daily_tasks WHERE id = ? AND owner_id = ?', (task_id, user_id)).fetchone()
    if not row:
        return flask.jsonify({'error': 'Not found'}), 404

    name = str(data.get('name', row['name'])).strip() or row['name']
    existing_recurrence = normalize_daily_task_recurrence(
        row['recurrence'] if row['recurrence'] else ('one_time' if row['no_expiry'] else 'daily')
    )
    recurrence = normalize_daily_task_recurrence(data.get('recurrence', existing_recurrence))
    task_kind = normalize_daily_task_kind(data.get('task_kind', row['task_kind']))

    target_minutes = data.get('target_minutes', row['target_minutes'])
    if target_minutes is not None:
        target_minutes = max(1, int(target_minutes))

    task_unit = str(data.get('task_unit', row['task_unit'])).strip()
    if len(task_unit) > 20:
        task_unit = task_unit[:20]

    current_due = row['due_date']
    due_date_raw = data.get('due_date', current_due)
    if due_date_raw is None:
        due_date_raw = ''
    due_date_value = None
    if due_date_raw:
        parsed_due_date = parse_iso_date(due_date_raw)
        if not parsed_due_date:
            return flask.jsonify({'error': 'due_date must be YYYY-MM-DD'}), 400
        due_date_value = parsed_due_date.isoformat()

    color = str(data.get('color', row['color'])).strip() or row['color']
    if not HEX_COLOR_RE.match(color):
        color = row['color']

    no_expiry = 1 if recurrence == 'one_time' else 0
    db.execute(
        'UPDATE daily_tasks SET name=?, recurrence=?, task_kind=?, target_minutes=?, task_unit=?, color=?, no_expiry=?, due_date=? WHERE id=? AND owner_id = ?',
        (name, recurrence, task_kind, target_minutes, task_unit, color, no_expiry, due_date_value, task_id, user_id),
    )
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/daily_tasks/<int:task_id>', methods=['DELETE'])
def delete_daily_task(task_id):
    db = get_db()
    user_id = get_current_user_id()
    db.execute('DELETE FROM daily_tasks WHERE id = ? AND owner_id = ?', (task_id, user_id))
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/daily_tasks/<int:task_id>/complete', methods=['POST'])
def complete_daily_task(task_id):
    return update_daily_task_progress(task_id)


@app.route('/api/daily_tasks/<int:task_id>/progress', methods=['POST'])
def update_daily_task_progress(task_id):
    data = flask.request.get_json(silent=True) or {}
    done = 1 if data.get('done', True) else 0
    done_minutes = data.get('done_minutes')
    if done_minutes is not None:
        done_minutes = max(0, int(done_minutes))

    db = get_db()
    user_id = get_current_user_id()
    task = db.execute(
        'SELECT id, recurrence, no_expiry, task_kind, target_minutes, due_date FROM daily_tasks WHERE id = ? AND owner_id = ?',
        (task_id, user_id),
    ).fetchone()
    if not task:
        return flask.jsonify({'error': 'Not found'}), 404

    recurrence = normalize_daily_task_recurrence(task['recurrence'] if task['recurrence'] else ('one_time' if task['no_expiry'] else 'daily'))
    task_kind = normalize_daily_task_kind(task['task_kind'])
    target = int(task['target_minutes'] or 0)

    day_start_hour = get_day_start_hour()
    week_start_day = get_week_start_day()
    today_date = get_logical_now(day_start_hour).date()
    today = today_date.isoformat()

    due_date_obj = parse_iso_date(task['due_date'])
    period_key, _ = get_task_period_key_and_end(recurrence, today_date, week_start_day, due_date_obj)

    existing = db.execute(
        'SELECT done, done_minutes FROM daily_task_completions WHERE daily_task_id = ? AND completion_date = ?',
        (task_id, period_key),
    ).fetchone()

    existing_done_minutes = int(existing['done_minutes'] or 0) if existing else 0
    existing_done = bool(existing['done']) if existing else False

    new_done_minutes = existing_done_minutes if done_minutes is None else done_minutes
    new_done = bool(done)

    if task_kind == 'integer' and target > 0:
        new_done = new_done_minutes >= target

    db.execute(
        '''INSERT INTO daily_task_completions (daily_task_id, completion_date, done, done_minutes)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(daily_task_id, completion_date) DO UPDATE SET done=excluded.done, done_minutes=excluded.done_minutes''',
        (task_id, period_key, 1 if new_done else 0, new_done_minutes),
    )

    db.execute(
        'INSERT INTO daily_task_logs (daily_task_id, log_date, value, done) VALUES (?, ?, ?, ?)',
        (task_id, today, new_done_minutes, 1 if new_done else 0),
    )

    if recurrence == 'one_time':
        db.execute(
            'UPDATE daily_tasks SET persistent_done = ?, persistent_done_minutes = ? WHERE id = ?',
            (1 if new_done else 0, new_done_minutes, task_id),
        )

    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/daily_tasks_calendar', methods=['GET'])
def get_daily_tasks_calendar():
    year_str = flask.request.args.get('year', '').strip()
    month_str = flask.request.args.get('month', '').strip()

    day_start_hour = get_day_start_hour()
    logical_today = get_logical_now(day_start_hour).date()

    try:
        year = int(year_str) if year_str else logical_today.year
        month = int(month_str) if month_str else logical_today.month
        if not (1 <= month <= 12):
            raise ValueError('Invalid month')
        month_start = logical_today.replace(year=year, month=month, day=1)
    except ValueError:
        return flask.jsonify({'error': 'Invalid year/month'}), 400

    days_in_month = cal_module.monthrange(year, month)[1]
    month_end = month_start.replace(day=days_in_month)

    db = get_db()
    user_id = get_current_user_id()
    rows = db.execute(
        '''
        SELECT l.log_date, l.done, dt.color
        FROM daily_task_logs l
        JOIN daily_tasks dt ON dt.id = l.daily_task_id
        WHERE l.log_date BETWEEN ? AND ? AND dt.owner_id = ?
        ORDER BY l.log_date
        ''',
        (month_start.isoformat(), month_end.isoformat(), user_id),
    ).fetchall()

    day_map = {}
    for row in rows:
        date_key = row['log_date']
        if date_key not in day_map:
            day_map[date_key] = {
                'log_count': 0,
                'done_count': 0,
                'colors': {},
            }
        day_map[date_key]['log_count'] += 1
        if row['done']:
            day_map[date_key]['done_count'] += 1
        color = row['color'] or DEFAULT_TASK_COLOR
        day_map[date_key]['colors'][color] = day_map[date_key]['colors'].get(color, 0) + 1

    days = []
    for day_num in range(1, days_in_month + 1):
        date_key = month_start.replace(day=day_num).isoformat()
        entry = day_map.get(date_key, {'log_count': 0, 'done_count': 0, 'colors': {}})
        colors = [{'color': c, 'count': cnt} for c, cnt in entry['colors'].items() if cnt > 0]
        colors.sort(key=lambda x: x['count'], reverse=True)
        days.append({
            'date': date_key,
            'day': day_num,
            'log_count': entry['log_count'],
            'done_count': entry['done_count'],
            'colors': colors,
        })

    return flask.jsonify({
        'year': year,
        'month': month,
        'month_label': month_start.strftime('%B %Y'),
        'days': days,
        'today': logical_today.isoformat(),
    })


@app.route('/api/daily_task_logs', methods=['GET'])
def get_daily_task_logs():
    log_date = flask.request.args.get('date', '').strip()
    if not log_date:
        return flask.jsonify({'error': 'date parameter is required'}), 400

    parsed_date = parse_iso_date(log_date)
    if not parsed_date:
        return flask.jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    db = get_db()
    user_id = get_current_user_id()
    rows = db.execute(
        '''
        SELECT l.id, l.log_date, l.value, l.done, l.created_at,
               dt.id AS task_id, dt.name AS task_name, dt.color, dt.task_kind, dt.recurrence
        FROM daily_task_logs l
        JOIN daily_tasks dt ON dt.id = l.daily_task_id
        WHERE l.log_date = ? AND dt.owner_id = ?
        ORDER BY l.created_at DESC, l.id DESC
        ''',
        (parsed_date.isoformat(), user_id),
    ).fetchall()


@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    return flask.jsonify({'user_id': get_current_user_id()})

    logs = []
    for row in rows:
        logs.append({
            'id': int(row['id']),
            'log_date': row['log_date'],
            'value': int(row['value'] or 0),
            'done': bool(row['done']),
            'task_id': int(row['task_id']),
            'task_name': row['task_name'],
            'task_kind': normalize_daily_task_kind(row['task_kind']),
            'recurrence': normalize_daily_task_recurrence(row['recurrence']),
            'color': row['color'] or DEFAULT_TASK_COLOR,
            'created_at': row['created_at'],
        })

    return flask.jsonify({'date': parsed_date.isoformat(), 'logs': logs})


with app.app_context():
    init_db()


if __name__ == '__main__':
    app.run(debug=True)