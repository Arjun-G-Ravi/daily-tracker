from flask import Flask, render_template, request, redirect, url_for, jsonify
import calendar
from datetime import datetime, date
import json
import os

app = Flask(__name__)

# Simple file-based storage for journeys
JOURNEYS_FILE = 'journeys.json'

def load_journeys():
    if os.path.exists(JOURNEYS_FILE):
        with open(JOURNEYS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_journeys(journeys):
    with open(JOURNEYS_FILE, 'w') as f:
        json.dump(journeys, f, indent=2)

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
def home():
    journeys = load_journeys()
    days, month, year = get_current_month_days()
    month_name = calendar.month_name[month]
    
    # Get unique journey names
    all_journeys = set()
    for day_data in journeys.values():
        all_journeys.update(day_data.keys())
    
    return render_template('home.html', 
                         journeys=journeys, 
                         days=days, 
                         month_name=month_name, 
                         month=month,
                         year=year,
                         all_journeys=sorted(all_journeys))

@app.route('/journey')
def journey():
    today = datetime.now().day
    return render_template('journey.html', today=today)

@app.route('/add_journey', methods=['POST'])
def add_journey():
    journey_name = request.form.get('journey_name')
    day = request.form.get('day')
    completed = request.form.get('completed') == 'on'
    
    journeys = load_journeys()
    date_key = f"{datetime.now().year}-{datetime.now().month:02d}-{int(day):02d}"
    
    if date_key not in journeys:
        journeys[date_key] = {}
    
    journeys[date_key][journey_name] = completed
    save_journeys(journeys)
    
    return redirect(url_for('home'))

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
