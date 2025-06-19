from flask import Flask, render_template, request, redirect, url_for, jsonify
import calendar
from datetime import datetime, date
import json
import os

app = Flask(__name__)

# Simple file-based storage for journeys
JOURNEYS_FILE = 'journeys.json'
JOURNEY_TEMPLATES_FILE = 'journey_templates.json'

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
    month_name = calendar.month_name[month]
    
    # Get unique journey names from both daily data and templates
    all_journeys = set()
    for day_data in journeys.values():
        all_journeys.update(day_data.keys())
    
    # Add journey templates
    templates = load_journey_templates()
    all_journeys.update(templates)
    
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
                         all_journeys=sorted(all_journeys),
                         templates=templates)

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
    
    return render_template('journeys.html', all_journeys=sorted(all_journeys))

@app.route('/add_template', methods=['POST'])
def add_template():
    journey_name = request.form.get('journey_name')
    
    if not journey_name:
        return redirect(url_for('home'))
    
    templates = load_journey_templates()
    
    if journey_name not in templates:
        templates.append(journey_name)
        save_journey_templates(templates)
    
    return redirect(url_for('home'))

@app.route('/journey/<journey_name>')
@app.route('/journey/<journey_name>/<view_type>')
def journey_detail(journey_name, view_type='yearly'):
    journeys = load_journeys()
    
    # Get all data for this specific journey
    journey_data = {}
    for date_key, day_data in journeys.items():
        if journey_name in day_data and day_data[journey_name]:
            journey_data[date_key] = True
    
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
            
            current_week.append({
                'date': date_key,
                'has_contribution': has_contribution,
                'day': day
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
                             current_month_data={
                                 'month': current_month,
                                 'month_name': month_name,
                                 'weeks': month_weeks,
                                 'year': current_year
                             },
                             view_type='monthly',
                             year=now.year)
    
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
                
                current_week.append({
                    'date': date_key,
                    'has_contribution': has_contribution,
                    'day': day
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
                             monthly_data=monthly_data,
                             view_type='yearly',
                             year=now.year)

@app.route('/journey')
def journey():
    today = datetime.now().day
    return render_template('journey.html', today=today)

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

if __name__ == '__main__':
    app.run(debug=True)
