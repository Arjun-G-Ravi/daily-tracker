from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# ---------- Helper functions ----------
def load_json(filename):
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

# ---------- Load initial data ----------
journeys_file = "journeys.json"
journey_order_file = "journey_order.json"
journey_start_dates_file = "journey_start_dates.json"
journey_schedules_file = "journey_schedules.json"
journey_templates_file = "journey_templates.json"
daily_tasks_file = "daily_tasks.json"
task_categories_file = "task_categories.json"

if not os.path.exists(daily_tasks_file):
    save_json(daily_tasks_file, {})

# ---------- Routes ----------
@app.route("/")
def index():
    journeys = load_json(journeys_file)
    journey_order = load_json(journey_order_file)
    journey_start_dates = load_json(journey_start_dates_file)
    journey_schedules = load_json(journey_schedules_file)
    journey_templates = load_json(journey_templates_file)
    daily_tasks = load_json(daily_tasks_file)
    categories = load_json(task_categories_file)

    ordered_journeys = [(jid, journeys[jid]) for jid in journey_order if jid in journeys]
    return render_template(
        "index.html",
        journeys=ordered_journeys,
        journey_start_dates=journey_start_dates,
        journey_schedules=journey_schedules,
        journey_templates=journey_templates,
        daily_tasks=daily_tasks,
        categories=categories
    )

@app.route("/journey/<journey_id>")
def view_journey(journey_id):
    journeys = load_json(journeys_file)
    journey_start_dates = load_json(journey_start_dates_file)
    journey_schedules = load_json(journey_schedules_file)
    journey_templates = load_json(journey_templates_file)

    if journey_id not in journeys:
        return "Journey not found", 404

    journey_name = journeys[journey_id]
    start_date = datetime.strptime(journey_start_dates[journey_id], "%Y-%m-%d")
    schedule = journey_schedules.get(journey_id, {})
    template = journey_templates.get(journey_id, {})

    return render_template(
        "journey.html",
        journey_id=journey_id,
        journey_name=journey_name,
        start_date=start_date,
        schedule=schedule,
        template=template
    )

@app.route("/journey/<journey_id>/tasks/<date>")
def journey_tasks(journey_id, date):
    journeys = load_json(journeys_file)
    journey_start_dates = load_json(journey_start_dates_file)
    journey_schedules = load_json(journey_schedules_file)
    daily_tasks = load_json(daily_tasks_file)
    categories = load_json(task_categories_file)

    if journey_id not in journeys:
        return "Journey not found", 404

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD.", 400

    schedule = journey_schedules.get(journey_id, {})
    day_offset = (date_obj - datetime.strptime(journey_start_dates[journey_id], "%Y-%m-%d")).days
    day_key = str(day_offset + 1)  # Day numbering starts at 1

    tasks_for_day = schedule.get(day_key, [])
    tasks_with_status = []
    for task in tasks_for_day:
        status = daily_tasks.get(date, {}).get(task, False)
        tasks_with_status.append({"name": task, "status": status})

    return render_template(
        "journey_tasks.html",
        journey_id=journey_id,
        journey_name=journeys[journey_id],
        date=date,
        tasks=tasks_with_status,
        categories=categories
    )

@app.route("/update_task", methods=["POST"])
def update_task():
    data = request.json
    date = data.get("date")
    task = data.get("task")
    status = data.get("status")

    if not date or not task:
        return jsonify({"success": False, "error": "Missing date or task"}), 400

    daily_tasks = load_json(daily_tasks_file)
    if date not in daily_tasks:
        daily_tasks[date] = {}
    daily_tasks[date][task] = status

    save_json(daily_tasks_file, daily_tasks)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)
