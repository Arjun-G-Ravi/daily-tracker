import sqlite3
import time
import re
import os
import shutil
from datetime import datetime, timedelta

import flask

app = flask.Flask(__name__, template_folder='.')
DATABASE_PATH = 'user_data.db'
LEGACY_DATABASE_PATH = 'weekly_tracker.db'
DEFAULT_TASK_COLOR = '#007bff'
DEFAULT_DAY_START_HOUR = 2
HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def get_db():
    if 'db' not in flask.g:
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
    columns = db.execute("PRAGMA table_info(tasks)").fetchall()
    column_names = {column['name'] for column in columns}
    if 'task_color' not in column_names:
        db.execute(
            "ALTER TABLE tasks ADD COLUMN task_color TEXT NOT NULL DEFAULT '#007bff'"
        )
    existing_day_start = db.execute(
        "SELECT value FROM app_settings WHERE key = 'day_start_hour'"
    ).fetchone()
    if not existing_day_start:
        db.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            ('day_start_hour', str(DEFAULT_DAY_START_HOUR)),
        )
    db.commit()


def get_day_start_hour():
    db = get_db()
    row = db.execute(
        "SELECT value FROM app_settings WHERE key = 'day_start_hour'"
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
        'elapsed': base_elapsed,
        'running': running,
    }


def get_today_color_breakdown():
    db = get_db()
    day_start_hour = get_day_start_hour()
    today = get_logical_now(day_start_hour).date().isoformat()

    totals = {}

    logged_rows = db.execute(
        '''
        SELECT t.task_color, COALESCE(SUM(w.seconds), 0) AS total_seconds
        FROM work_logs w
        JOIN tasks t ON t.id = w.task_id
        WHERE w.work_date = ?
        GROUP BY t.task_color
        ''',
        (today,),
    ).fetchall()

    for row in logged_rows:
        color = row['task_color'] or DEFAULT_TASK_COLOR
        totals[color] = totals.get(color, 0) + int(row['total_seconds'])

    running_rows = db.execute(
        'SELECT started_at, task_color FROM tasks WHERE running = 1 AND started_at IS NOT NULL'
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
    day_start_hour = get_day_start_hour()
    today = get_logical_now(day_start_hour).date().isoformat()
    row = db.execute(
        'SELECT COALESCE(SUM(seconds), 0) AS total FROM work_logs WHERE work_date = ?',
        (today,),
    ).fetchone()
    logged_total = int(row['total']) if row else 0

    running_rows = db.execute(
        'SELECT started_at FROM tasks WHERE running = 1 AND started_at IS NOT NULL'
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
    day_start_hour = get_day_start_hour()
    today = get_logical_now(day_start_hour).date().isoformat()

    rows = db.execute(
        'SELECT task_id, COALESCE(SUM(seconds), 0) AS total FROM work_logs WHERE work_date = ? GROUP BY task_id',
        (today,),
    ).fetchall()

    result = {}
    for row in rows:
        result[int(row['task_id'])] = int(row['total'])

    running_rows = db.execute(
        'SELECT id, started_at FROM tasks WHERE running = 1 AND started_at IS NOT NULL'
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
    day_start_hour = get_day_start_hour()
    today_date = get_logical_now(day_start_hour).date()
    days_since_sunday = (today_date.weekday() + 1) % 7
    week_start = today_date - timedelta(days=days_since_sunday)
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
        WHERE w.work_date BETWEEN ? AND ?
        GROUP BY w.work_date, t.task_color
        ''',
        (week_start.isoformat(), week_end.isoformat()),
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
        'SELECT started_at, task_color FROM tasks WHERE running = 1 AND started_at IS NOT NULL'
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
        }
        month_order.append(month_key)

    logged_rows = db.execute(
        '''
        SELECT substr(work_date, 1, 7) AS month_key, COALESCE(SUM(seconds), 0) AS total_seconds
        FROM work_logs
        WHERE work_date >= ?
        GROUP BY substr(work_date, 1, 7)
        ''',
        (oldest_month_start.isoformat(),),
    ).fetchall()

    for row in logged_rows:
        month_key = row['month_key']
        if month_key in month_map:
            month_map[month_key]['total_seconds'] = int(row['total_seconds'])

    running_rows = db.execute(
        'SELECT started_at FROM tasks WHERE running = 1 AND started_at IS NOT NULL'
    ).fetchall()

    now_ts = int(time.time())
    logical_day_start_ts = get_logical_day_start_timestamp(now_ts, day_start_hour)
    current_month_key = logical_today.strftime('%Y-%m')
    if current_month_key in month_map:
        for row in running_rows:
            started_at = int(row['started_at'])
            month_map[current_month_key]['total_seconds'] += max(
                0, now_ts - max(started_at, logical_day_start_ts)
            )

    return [month_map[month_key] for month_key in month_order]


@app.route('/')
def hello():
    return flask.render_template('index.html')


@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    db = get_db()
    rows = db.execute(
        'SELECT id, name, task_type, task_color, elapsed_seconds, running, started_at FROM tasks ORDER BY created_at DESC, id DESC'
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
    cursor = db.execute(
        'INSERT INTO tasks (name, task_type, task_color, elapsed_seconds) VALUES (?, ?, ?, ?)',
        (name, task_type, task_color, initial_seconds),
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
    task = db.execute(
        'SELECT id, running FROM tasks WHERE id = ?',
        (task_id,),
    ).fetchone()

    if not task:
        return flask.jsonify({'error': 'Task not found'}), 404
    if task['running']:
        return flask.jsonify({'ok': True})

    db.execute(
        'UPDATE tasks SET running = 1, started_at = ? WHERE id = ?',
        (int(time.time()), task_id),
    )
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>/stop', methods=['POST'])
def stop_task(task_id):
    db = get_db()
    task = db.execute(
        'SELECT id, elapsed_seconds, running, started_at FROM tasks WHERE id = ?',
        (task_id,),
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
        'UPDATE tasks SET elapsed_seconds = ?, running = 0, started_at = NULL WHERE id = ?',
        (new_elapsed, task_id),
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
    task = db.execute(
        'SELECT id, elapsed_seconds FROM tasks WHERE id = ?',
        (task_id,),
    ).fetchone()

    if not task:
        return flask.jsonify({'error': 'Task not found'}), 404

    new_elapsed = int(task['elapsed_seconds']) + seconds
    db.execute(
        'UPDATE tasks SET elapsed_seconds = ? WHERE id = ?',
        (new_elapsed, task_id),
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
    db.execute(
        '''
        INSERT INTO app_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ''',
        ('day_start_hour', str(day_start_hour)),
    )
    db.commit()
    return flask.jsonify({'ok': True, 'day_start_hour': day_start_hour})


@app.route('/api/tasks/<int:task_id>/color', methods=['PUT'])
def update_task_color(task_id):
    data = flask.request.get_json(silent=True) or {}
    task_color = str(data.get('task_color', '')).strip()

    if not HEX_COLOR_RE.match(task_color):
        return flask.jsonify({'error': 'Invalid task color'}), 400

    db = get_db()
    task = db.execute('SELECT id FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        return flask.jsonify({'error': 'Task not found'}), 404

    db.execute('UPDATE tasks SET task_color = ? WHERE id = ?', (task_color, task_id))
    db.commit()
    return flask.jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    db = get_db()
    db.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    db.commit()
    return flask.jsonify({'ok': True})


with app.app_context():
    init_db()


if __name__ == '__main__':
    app.run(debug=True)