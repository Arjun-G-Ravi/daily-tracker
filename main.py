from flask import Flask, render_template, request, redirect, url_for, jsonify
import calendar
from datetime import datetime, date
import json
import os

app = Flask(__name__)

# Simple file-based storage for journeys
JOURNEYS_FILE = 'journeys.json'
JOURNEY_TEMPLATES_FILE = 'journey_templates.json'
JOURNEY_ORDER_FILE = 'journey_order.json'
JOURNEY_SCHEDULES_FILE = 'journey_schedules.json'
JOURNEY_START_DATES_FILE = 'journey_start_dates.json'
SETTINGS_FILE = 'settings.json'
DAILY_TASKS_FILE = 'daily_tasks.json'  # For storing daily tasks

def load_journeys():
    if os.path.exists(JOURNEYS_FILE):
        with open(JOURNEYS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_journeys(journeys):
    with open(JOURNEYS_FILE, 'w') as f:
        json.dump(journeys, f, indent=2)

def load_journey_templates():
    if os.path.exists(JOURNEY_TEMPLATES_FILE):
        with open(JOURNEY_TEMPLATES_FILE, 'r') as f:
            return json.load(f)
    return []

def save_journey_templates(templates):
    with open(JOURNEY_TEMPLATES_FILE, 'w') as f:
        json.dump(templates, f, indent=2)

def load_journey_order():
    if os.path.exists(JOURNEY_ORDER_FILE):
        with open(JOURNEY_ORDER_FILE, 'r') as f:
            return json.load(f)
    return []

def save_journey_order(order):
    with open(JOURNEY_ORDER_FILE, 'w') as f:
        json.dump(order, f, indent=2)

def load_journey_schedules():
    if os.path.exists(JOURNEY_SCHEDULES_FILE):
        with open(JOURNEY_SCHEDULES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_journey_schedules(schedules):
    with open(JOURNEY_SCHEDULES_FILE, 'w') as f:
        json.dump(schedules, f, indent=2)

def load_journey_start_dates():
    if os.path.exists(JOURNEY_START_DATES_FILE):
        with open(JOURNEY_START_DATES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_journey_start_dates(start_dates):
    with open(JOURNEY_START_DATES_FILE, 'w') as f:
        json.dump(start_dates, f, indent=2)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {"display_mode": "missed", "theme": "dark"}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def load_daily_tasks():
    if os.path.exists(DAILY_TASKS_FILE):
        with open(DAILY_TASKS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_daily_tasks(tasks):
    with open(DAILY_TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)

def get_current_month_days():
    now = datetime.now()
    cal = calendar.monthcalendar(now.year, now.month)
    days = []
    for week in cal:
        for day in week:
            if day != 0:
                days.append(day)
    return days, now.month, now.year

@app.route('/')
@app.route('/<int:year>/<int:month>')
def home(year=None, month=None):
    if year is None or month is None:
        now = datetime.now()
        year, month = now.year, now.month
    
    # Get days for the specified month/year
    cal = calendar.monthcalendar(year, month)
    days = []
    for week in cal:
        for day in week:
            if day != 0:
                days.append(day)
    
    # Get the number of days in the current month
    days_in_month = calendar.monthrange(year, month)[1]
    
    journeys = load_journeys()
    schedules = load_journey_schedules()
    start_dates = load_journey_start_dates()
    settings = load_settings()
    month_name = calendar.month_name[month]
    
    # Calculate missed days for each journey
    missed_days = {}
    scheduled_days = {}  # New: track which days are scheduled for each journey
    today = date.today()
    
    # Get unique journey names from both daily data and templates
    all_journeys = set()
    for day_data in journeys.values():
        all_journeys.update(day_data.keys())
    
    # Add journey templates
    templates = load_journey_templates()
    all_journeys.update(templates)
    
    # Calculate missed days and scheduled days for each journey
    for journey in all_journeys:
        journey_schedule = schedules.get(journey, [])
        journey_start_date = start_dates.get(journey)
        missed_days[journey] = set()
        scheduled_days[journey] = set()
        
        # Parse start date if it exists
        start_date_obj = None
        if journey_start_date:
            try:
                start_date_obj = datetime.strptime(journey_start_date, '%Y-%m-%d').date()
            except:
                start_date_obj = None
        
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            day_of_week = current_date.weekday()
            date_key = f"{year}-{month:02d}-{day:02d}"
            
            # Only consider dates from start date onwards and up to today
            if start_date_obj and current_date < start_date_obj:
                continue
            if current_date > today:
                continue
            
            is_scheduled = day_of_week in journey_schedule
            is_completed = journeys.get(date_key, {}).get(journey, False)
            is_past = current_date < today
            
            if is_scheduled:
                scheduled_days[journey].add(day)
            
            if is_past and is_scheduled and not is_completed:
                missed_days[journey].add(day)
    
    # Apply saved journey order
    journey_order = load_journey_order()
    if journey_order:
        # Sort journeys according to saved order, with new journeys at the end
        ordered_journeys = []
        for journey in journey_order:
            if journey in all_journeys:
                ordered_journeys.append(journey)
                all_journeys.discard(journey)
        # Add any new journeys that weren't in the saved order
        ordered_journeys.extend(sorted(all_journeys))
        all_journeys = ordered_journeys
    else:
        all_journeys = sorted(all_journeys)
    
    # Calculate previous and next month/year
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year
    
    return render_template('home.html', 
                         journeys=journeys, 
                         days=days, 
                         days_in_month=days_in_month,
                         month_name=month_name, 
                         month=month,
                         year=year,
                         prev_month=prev_month,
                         prev_year=prev_year,
                         next_month=next_month,
                         next_year=next_year,
                         all_journeys=all_journeys,  # Use ordered journeys instead of sorted
                         templates=templates,
                         schedules=schedules,
                         start_dates=start_dates,
                         missed_days=missed_days,
                         scheduled_days=scheduled_days,
                         today=today.strftime('%Y-%m-%d'),
                         settings=settings)

@app.route('/journeys')
def journeys():
    all_journeys_data = load_journeys()
    
    # Get unique journey names from daily data
    all_journeys = set()
    for day_data in all_journeys_data.values():
        all_journeys.update(day_data.keys())
    
    # Add journey templates
    templates = load_journey_templates()
    all_journeys.update(templates)
    
    # Load start dates
    start_dates = load_journey_start_dates()
    
    # Load settings for theme
    settings = load_settings()
    
    return render_template('journeys.html', all_journeys=sorted(all_journeys), start_dates=start_dates, settings=settings)

@app.route('/add_template', methods=['POST'])
def add_template():
    journey_name = request.form.get('journey_name')
    
    if not journey_name:
        return redirect(url_for('home'))
    
    templates = load_journey_templates()
    
    if journey_name not in templates:
        templates.append(journey_name)
        save_journey_templates(templates)
        
        # Set schedule to all days (Monday=0 to Sunday=6)
        schedules = load_journey_schedules()
        schedules[journey_name] = [0, 1, 2, 3, 4, 5, 6]
        save_journey_schedules(schedules)
        
        # Set start date to today
        start_dates = load_journey_start_dates()
        start_dates[journey_name] = date.today().strftime('%Y-%m-%d')
        save_journey_start_dates(start_dates)
    
    return redirect(url_for('home'))

@app.route('/journey/<journey_name>')
@app.route('/journey/<journey_name>/<view_type>')
def journey_detail(journey_name, view_type='yearly'):
    journeys = load_journeys()
    schedules = load_journey_schedules()
    start_dates = load_journey_start_dates()
    
    # Get all data for this specific journey
    journey_data = {}
    for date_key, day_data in journeys.items():
        if journey_name in day_data and day_data[journey_name]:
            journey_data[date_key] = True
    
    # Get schedule and start date for this journey
    journey_schedule = schedules.get(journey_name, [])
    journey_start_date = start_dates.get(journey_name)
    
    # Parse start date
    start_date_obj = None
    if journey_start_date:
        try:
            start_date_obj = datetime.strptime(journey_start_date, '%Y-%m-%d').date()
        except:
            start_date_obj = None
    
    now = datetime.now()

    if view_type == 'monthly':
        # Generate current month calendar view
        current_month = now.month
        current_year = now.year
        month_name = calendar.month_name[current_month]
        days_in_month = calendar.monthrange(current_year, current_month)[1]
        
        # Create weeks for current month
        first_day = date(current_year, current_month, 1)
        start_weekday = first_day.weekday()
        # Convert to Sunday=0 format
        start_weekday = (start_weekday + 1) % 7
        
        month_weeks = []
        current_week = [None] * start_weekday  # Empty cells before month starts
        
        for day in range(1, days_in_month + 1):
            date_key = f"{current_year}-{current_month:02d}-{day:02d}"
            has_contribution = journey_data.get(date_key, False)
            current_date = date(current_year, current_month, day)
            
            # Only consider dates from start date onwards and up to today
            if start_date_obj and current_date < start_date_obj:
                current_week.append(None)
                continue
            if current_date > date.today():
                current_week.append(None)
                continue
            
            # Check if this day should be scheduled
            day_of_week = current_date.weekday()
            is_scheduled = day_of_week in journey_schedule
            
            # Check if this is a past day that was missed
            is_past = current_date < date.today()
            is_missed = is_past and is_scheduled and not has_contribution
            
            current_week.append({
                'date': date_key,
                'has_contribution': has_contribution,
                'day': day,
                'is_scheduled': is_scheduled,
                'is_missed': is_missed
            })
            
            # If we've filled a week (7 days), start a new week
            if len(current_week) == 7:
                month_weeks.append(current_week)
                current_week = []
        
        # Fill remaining days in last week with None
        while len(current_week) < 7:
            current_week.append(None)
        if current_week != [None] * 7:
            month_weeks.append(current_week)
        
        return render_template('journey_detail.html', 
                             journey_name=journey_name,
                             journey_data=journey_data,
                             journey_schedule=journey_schedule,
                             journey_start_date=journey_start_date,
                             current_month_data={
                                 'month': current_month,
                                 'month_name': month_name,
                                 'weeks': month_weeks,
                                 'year': current_year
                             },
                             view_type='monthly',
                             year=now.year,
                             settings=load_settings())
    
    else:  # yearly view - show all months in grid
        # Generate monthly data for all 12 months
        monthly_data = []
        for month in range(1, 13):
            month_name = calendar.month_name[month]
            days_in_month = calendar.monthrange(now.year, month)[1]
            
            # Create weeks for this month
            first_day = date(now.year, month, 1)
            # Get the day of week for first day (0=Monday, 6=Sunday)
            start_weekday = first_day.weekday()
            # Convert to Sunday=0 format
            start_weekday = (start_weekday + 1) % 7
            
            month_weeks = []
            current_week = [None] * start_weekday  # Empty cells before month starts
            
            for day in range(1, days_in_month + 1):
                date_key = f"{now.year}-{month:02d}-{day:02d}"
                has_contribution = journey_data.get(date_key, False)
                current_date = date(now.year, month, day)
                
                # Only consider dates from start date onwards and up to today
                if start_date_obj and current_date < start_date_obj:
                    current_week.append(None)
                    continue
                if current_date > date.today():
                    current_week.append(None)
                    continue
                
                # Check if this day should be scheduled
                day_of_week = current_date.weekday()
                is_scheduled = day_of_week in journey_schedule
                
                # Check if this is a past day that was missed
                is_past = current_date < date.today()
                is_missed = is_past and is_scheduled and not has_contribution
                
                current_week.append({
                    'date': date_key,
                    'has_contribution': has_contribution,
                    'day': day,
                    'is_scheduled': is_scheduled,
                    'is_missed': is_missed
                })
                
                # If we've filled a week (7 days), start a new week
                if len(current_week) == 7:
                    month_weeks.append(current_week)
                    current_week = []
            
            # Fill remaining days in last week with None
            while len(current_week) < 7:
                current_week.append(None)
            if current_week != [None] * 7:
                month_weeks.append(current_week)
            
            monthly_data.append({
                'month': month,
                'month_name': month_name,
                'weeks': month_weeks
            })
        
        return render_template('journey_detail.html', 
                             journey_name=journey_name,
                             journey_data=journey_data,
                             journey_schedule=journey_schedule,
                             journey_start_date=journey_start_date,
                             monthly_data=monthly_data,
                             view_type='yearly',
                             year=now.year,
                             settings=load_settings())

@app.route('/journey')
def journey():
    today = datetime.now().day
    settings = load_settings()
    return render_template('journey.html', today=today, settings=settings)

@app.route('/add_journey', methods=['POST'])
def add_journey():
    journey_name = request.form.get('journey_name')
    day = request.form.get('day')
    month = request.form.get('month')
    year = request.form.get('year')
    completed = request.form.get('completed') == 'on'
    
    journeys = load_journeys()
    
    # Use provided month/year or default to current
    if not month or not year:
        now = datetime.now()
        month = month or now.month
        year = year or now.year
    
    date_key = f"{int(year)}-{int(month):02d}-{int(day):02d}"
    
    if date_key not in journeys:
        journeys[date_key] = {}
    
    journeys[date_key][journey_name] = completed
    save_journeys(journeys)
    
    return redirect(url_for('home', year=year, month=month))

@app.route('/toggle_journey', methods=['POST'])
def toggle_journey():
    try:
        data = request.get_json()
        journey_name = data.get('journey')
        date_key = data.get('date_key')
        completed = data.get('completed')
        
        if not journey_name or not date_key:
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        journeys = load_journeys()
        
        if date_key not in journeys:
            journeys[date_key] = {}
        
        if completed:
            journeys[date_key][journey_name] = True
        else:
            # Remove the journey if it's being uncompleted
            if journey_name in journeys[date_key]:
                del journeys[date_key][journey_name]
            # Clean up empty date entries
            if not journeys[date_key]:
                del journeys[date_key]
        
        save_journeys(journeys)
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/save_journey_order', methods=['POST'])
def save_journey_order_route():
    try:
        data = request.get_json()
        order = data.get('order')
        
        if not order:
            return jsonify({'success': False, 'error': 'Missing order data'})
        
        save_journey_order(order)
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/set_start_date/<journey_name>', methods=['POST'])
def set_start_date(journey_name):
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        
        if not start_date:
            return jsonify({'success': False, 'error': 'Missing start date'})
        
        # Validate date format
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
        except:
            return jsonify({'success': False, 'error': 'Invalid date format'})
        
        start_dates = load_journey_start_dates()
        start_dates[journey_name] = start_date
        save_journey_start_dates(start_dates)
        
        return jsonify({'success': True, 'message': 'Start date updated successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/set_schedule/<journey_name>', methods=['POST'])
def set_schedule(journey_name):
    try:
        data = request.get_json()
        days = data.get('days', [])  # List of weekday numbers (0=Monday, 6=Sunday)
        
        schedules = load_journey_schedules()
        schedules[journey_name] = days
        save_journey_schedules(schedules)
        
        return jsonify({'success': True, 'message': 'Schedule updated successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_journey/<journey_name>', methods=['POST'])
def delete_journey(journey_name):
    try:
        # Remove from all journey data
        journeys = load_journeys()
        for date_key in list(journeys.keys()):
            if journey_name in journeys[date_key]:
                del journeys[date_key][journey_name]
                # Clean up empty date entries
                if not journeys[date_key]:
                    del journeys[date_key]
        save_journeys(journeys)
        
        # Remove from templates
        templates = load_journey_templates()
        if journey_name in templates:
            templates.remove(journey_name)
            save_journey_templates(templates)
        
        # Remove from order
        order = load_journey_order()
        if journey_name in order:
            order.remove(journey_name)
            save_journey_order(order)
        
        # Remove from schedules
        schedules = load_journey_schedules()
        if journey_name in schedules:
            del schedules[journey_name]
            save_journey_schedules(schedules)
        
        # Remove from start dates
        start_dates = load_journey_start_dates()
        if journey_name in start_dates:
            del start_dates[journey_name]
            save_journey_start_dates(start_dates)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        display_mode = request.form.get('display_mode', 'missed')
        theme = request.form.get('theme', 'dark')
        settings_data = load_settings()
        settings_data['display_mode'] = display_mode
        settings_data['theme'] = theme
        save_settings(settings_data)
        return redirect(url_for('home'))
    
    settings_data = load_settings()
    return render_template('settings.html', settings=settings_data)

@app.route('/save_theme', methods=['POST'])
def save_theme():
    try:
        data = request.get_json()
        theme = data.get('theme', 'dark')
        
        if theme not in ['dark', 'light']:
            return jsonify({'success': False, 'error': 'Invalid theme'})
        
        settings_data = load_settings()
        settings_data['theme'] = theme
        save_settings(settings_data)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/rename_journey/<journey_name>', methods=['POST'])
def rename_journey(journey_name):
    try:
        data = request.get_json()
        new_name = data.get('new_name', '').strip()
        
        if not new_name:
            return jsonify({'success': False, 'error': 'New name cannot be empty'})
        
        if new_name == journey_name:
            return jsonify({'success': False, 'error': 'New name must be different from current name'})
        
        # Check if new name already exists
        templates = load_journey_templates()
        if new_name in templates:
            return jsonify({'success': False, 'error': 'A journey with this name already exists'})
        
        # Update all journey data
        journeys = load_journeys()
        for date_key in journeys:
            if journey_name in journeys[date_key]:
                journeys[date_key][new_name] = journeys[date_key][journey_name]
                del journeys[date_key][journey_name]
        save_journeys(journeys)
        
        # Update templates
        if journey_name in templates:
            templates = [new_name if j == journey_name else j for j in templates]
            save_journey_templates(templates)
        
        # Update order
        order = load_journey_order()
        if journey_name in order:
            order = [new_name if j == journey_name else j for j in order]
            save_journey_order(order)
        
        # Update schedules
        schedules = load_journey_schedules()
        if journey_name in schedules:
            schedules[new_name] = schedules[journey_name]
            del schedules[journey_name]
            save_journey_schedules(schedules)
        
        # Update start dates
        start_dates = load_journey_start_dates()
        if journey_name in start_dates:
            start_dates[new_name] = start_dates[journey_name]
            del start_dates[journey_name]
            save_journey_start_dates(start_dates)
        
        return jsonify({'success': True, 'new_name': new_name})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Daily Task Tracker Routes
@app.route('/daily_tasks')
def daily_tasks():
    """Main daily tasks page with list view only"""
    tasks = load_daily_tasks()
    settings = load_settings()
    
    # Get unique journey names for the class dropdown
    templates = load_journey_templates()
    
    # Sort tasks by date (newest first)
    sorted_tasks = sorted(tasks, key=lambda x: x['date'], reverse=True)
    
    # Group tasks by date and convert dates to dd/mm/yyyy format for display
    tasks_by_date = {}
    display_dates = {}  # Maps internal date to display format
    
    for task in sorted_tasks:
        date_key = task['date']  # Internal format: yyyy-mm-dd
        
        # Convert to dd/mm/yyyy for display
        try:
            year, month, day = date_key.split('-')
            display_date = f"{day}/{month}/{year}"
        except:
            display_date = date_key  # Fallback to original
        
        display_dates[date_key] = display_date
        
        if display_date not in tasks_by_date:
            tasks_by_date[display_date] = []
        tasks_by_date[display_date].append(task)
    
    # Get ordered dates for template (display format)
    ordered_dates = list(tasks_by_date.keys())
    
    return render_template('daily_tasks_list.html',
                         tasks=sorted_tasks,
                         tasks_by_date=tasks_by_date,
                         ordered_dates=ordered_dates,
                         journey_classes=templates,
                         settings=settings)

@app.route('/add_daily_task', methods=['POST'])
def add_daily_task():
    """Add a new daily task"""
    try:
        data = request.get_json()
        task_name = data.get('task', '').strip()
        description = data.get('description', '').strip()
        journey_class = data.get('journey_class', '').strip()
        task_date = data.get('date', date.today().strftime('%d/%m/%Y'))
        
        # Convert date from dd/mm/yyyy to yyyy-mm-dd for internal storage
        if '/' in task_date:
            day, month, year = task_date.split('/')
            internal_date = f"{year}-{month:0>2}-{day:0>2}"
        else:
            internal_date = task_date
        
        if not task_name:
            return jsonify({'success': False, 'error': 'Task name is required'})
        
        tasks = load_daily_tasks()
        
        # Create new task
        new_task = {
            'id': len(tasks) + 1,  # Simple ID system
            'task': task_name,
            'description': description,
            'journey_class': journey_class,
            'date': internal_date,
            'timestamp': datetime.now().isoformat()
        }
        
        tasks.append(new_task)
        save_daily_tasks(tasks)
        
        # If journey_class is specified, also mark it as completed in the main journey tracker
        if journey_class:
            journeys = load_journeys()
            if internal_date not in journeys:
                journeys[internal_date] = {}
            journeys[internal_date][journey_class] = True
            save_journeys(journeys)
        
        return jsonify({'success': True, 'task': new_task})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_daily_task/<int:task_id>', methods=['POST'])
def delete_daily_task(task_id):
    """Delete a daily task"""
    try:
        tasks = load_daily_tasks()
        
        # Find and remove the task
        task_to_remove = None
        for i, task in enumerate(tasks):
            if task['id'] == task_id:
                task_to_remove = tasks.pop(i)
                break
        
        if not task_to_remove:
            return jsonify({'success': False, 'error': 'Task not found'})
        
        save_daily_tasks(tasks)
        
        # If this task was linked to a journey class, we might want to unmark it
        # For now, we'll leave the journey completion as is since other tasks might have contributed
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/edit_daily_task/<int:task_id>', methods=['POST'])
def edit_daily_task(task_id):
    """Edit a daily task"""
    try:
        data = request.get_json()
        task_name = data.get('task', '').strip()
        description = data.get('description', '').strip()
        journey_class = data.get('journey_class', '').strip()
        
        if not task_name:
            return jsonify({'success': False, 'error': 'Task name is required'})
        
        tasks = load_daily_tasks()
        
        # Find and update the task
        task_updated = False
        for task in tasks:
            if task['id'] == task_id:
                old_journey_class = task.get('journey_class', '')
                task['task'] = task_name
                task['description'] = description
                task['journey_class'] = journey_class
                task_updated = True
                
                # Handle journey class changes
                if old_journey_class != journey_class:
                    # This is complex - for now we'll leave journey completions as is
                    pass
                
                break
        
        if not task_updated:
            return jsonify({'success': False, 'error': 'Task not found'})
        
        save_daily_tasks(tasks)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/journey_tasks/<journey_name>')
def journey_tasks(journey_name):
    """View all tasks for a specific journey"""
    tasks = load_daily_tasks()
    settings = load_settings()
    
    # Filter tasks for this journey
    journey_tasks = [task for task in tasks if task.get('journey_class') == journey_name]
    
    # Sort by date (newest first)
    journey_tasks = sorted(journey_tasks, key=lambda x: x['date'], reverse=True)
    
    # Group by date and convert to dd/mm/yyyy format for display
    tasks_by_date = {}
    for task in journey_tasks:
        date_key = task['date']  # Internal format: yyyy-mm-dd
        
        # Convert to dd/mm/yyyy for display
        try:
            year, month, day = date_key.split('-')
            display_date = f"{day}/{month}/{year}"
        except:
            display_date = date_key  # Fallback to original
        
        if display_date not in tasks_by_date:
            tasks_by_date[display_date] = []
        tasks_by_date[display_date].append(task)
    
    return render_template('journey_tasks.html',
                         journey_name=journey_name,
                         tasks=journey_tasks,
                         tasks_by_date=tasks_by_date,
                         settings=settings)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
