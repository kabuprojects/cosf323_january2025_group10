from flask import Flask, render_template, request, session, redirect, url_for, flash
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import os
import logging
from bson import ObjectId
from jinja2 import Environment
from werkzeug.utils import secure_filename
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Replace with a secure key

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# MongoDB setup
try:
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    client.server_info()
    db = client['nist_compliance']
    users = db['users']
    tasks = db['tasks']
    audit_logs = db['audit_logs']
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    exit(1)

# Email configuration
EMAIL_ADDRESS = "Millianofranco@gmail.com"  # Replace with your Gmail address
EMAIL_PASSWORD = "fzsh adhn yafc fjmh"   # Replace with your Gmail App Password

# File upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'credentials.json'

def get_google_calendar_service():
    creds = None
    if 'google_token' in session:
        creds = Credentials(**session['google_token'])
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        session['google_token'] = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
    return build('calendar', 'v3', credentials=creds)

# Jinja2 filter for date formatting
def datetimeformat(value):
    if value is None:
        return "N/A"
    return value.strftime('%Y-%m-%d')
app.jinja_env.filters['datetimeformat'] = datetimeformat

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.start()

def send_reminder_email(email, task_name, frequency, compliance_ref, due_date):
    subject = f"Compliance {frequency} Reminder ({compliance_ref})"
    body = f"Reminder: Please complete '{task_name}' by {due_date.strftime('%Y-%m-%d')} as per {compliance_ref} requirements. Acknowledge in the portal."
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp_server.send_message(msg)
        logger.info(f"Sent email to {email} for task {task_name} ({compliance_ref})")
        audit_logs.insert_one({
            'action': 'sent_reminder',
            'task_name': task_name,
            'email': email,
            'timestamp': datetime.now()
        })
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def add_to_google_calendar(email, task_name, due_date, compliance_ref):
    service = get_google_calendar_service()
    event = {
        'summary': f"Compliance Task: {task_name} ({compliance_ref})",
        'description': f"Complete {task_name} as per {compliance_ref} requirements.",
        'start': {'date': due_date.strftime('%Y-%m-%d')},
        'end': {'date': due_date.strftime('%Y-%m-%d')},
        'attendees': [{'email': email}],
        'reminders': {'useDefault': True}
    }
    try:
        service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Added task {task_name} to Google Calendar for {email}")
        audit_logs.insert_one({
            'action': 'calendar_add',
            'task_name': task_name,
            'email': email,
            'timestamp': datetime.now()
        })
    except Exception as e:
        logger.error(f"Failed to add to Google Calendar: {e}")

def check_and_send_reminders():
    today = datetime.now()
    logger.debug("Checking reminders...")
    for task in tasks.find():
        due_date = task.get('due_date')
        frequency = task['frequency']
        completed = task.get('completed', False)
        acknowledged = task.get('acknowledged', False)

        if not due_date:
            if frequency == 'monthly':
                due_date = today.replace(day=1, month=today.month + 1 if today.month < 12 else 1, year=today.year + 1 if today.month == 12 else today.year)
            elif frequency == 'yearly':
                due_date = today.replace(month=1, day=1, year=today.year + 1)
            tasks.update_one({'_id': task['_id']}, {'$set': {'due_date': due_date}})
            add_to_google_calendar(task['assigned_to'], task['name'], due_date, task['compliance_ref'])

        if not completed and today >= due_date - timedelta(days=1):
            send_reminder_email(task['assigned_to'], task['name'], frequency, task['compliance_ref'], due_date)
            tasks.update_one({'_id': task['_id']}, {'$set': {'last_sent': today}})
            if today > due_date + timedelta(days=5):
                send_reminder_email('millianofranco@gmain.com', task['name'], frequency, task['compliance_ref'], due_date)

scheduler.add_job(check_and_send_reminders, 'interval', hours=24)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash("Please log in to access the dashboard.", "warning")
        return redirect(url_for('login'))
    user_doc = users.find_one({'email': session['user']})
    if not user_doc:
        flash("User not found. Please log in again.", "danger")
        session.pop('user', None)
        return redirect(url_for('login'))
    user_role = user_doc.get('role', 'Employee')  # Default to 'Employee' if role is missing
    if user_role == 'Employee':
        user_tasks = tasks.find({'assigned_to': session['user']})
    else:
        user_tasks = tasks.find()
    tasks_with_due_dates = []
    today = datetime.now()
    for task in user_tasks:
        due_date = task.get('due_date')
        if due_date is None:
            frequency = task['frequency']
            if frequency == 'monthly':
                due_date = today.replace(day=1, month=today.month + 1 if today.month < 12 else 1, year=today.year + 1 if today.month == 12 else today.year)
            elif frequency == 'yearly':
                due_date = today.replace(month=1, day=1, year=today.year + 1)
            tasks.update_one({'_id': task['_id']}, {'$set': {'due_date': due_date}})
            task['due_date'] = due_date
        tasks_with_due_dates.append(task)
    return render_template('dashboard.html', tasks=tasks_with_due_dates, role=user_role)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash("Missing email or password.", "danger")
            return redirect(url_for('login'))
        user = users.find_one({'email': email, 'password': password})
        if user:
            session['user'] = email
            logger.info(f"User {email} logged in")
            audit_logs.insert_one({'action': 'login', 'email': email, 'timestamp': datetime.now()})
            return redirect(url_for('dashboard'))
        flash("Invalid credentials.", "danger")
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        if not email or not password or not role:
            flash("Missing required fields.", "danger")
            return redirect(url_for('register'))
        if not users.find_one({'email': email}):
            users.insert_one({'email': email, 'password': password, 'role': role})
            logger.info(f"User {email} registered with role {role}")
            audit_logs.insert_one({'action': 'register', 'email': email, 'role': role, 'timestamp': datetime.now()})
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        flash("Email already exists.", "danger")
        return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if 'user' not in session:
        flash("Please log in to add tasks.", "warning")
        return redirect(url_for('login'))
    user_doc = users.find_one({'email': session['user']})
    user_role = user_doc.get('role', 'Employee') if user_doc else 'Employee'
    if user_role not in ['IT Admin', 'Compliance Officer']:
        flash("Only IT Admins and Compliance Officers can add tasks.", "danger")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        logger.debug(f"Form data received: {request.form}")
        try:
            task_name = request.form['task_name']
            frequency = request.form['frequency']
            compliance_ref = request.form['compliance_ref']
            assigned_to = request.form['assigned_to']
        except KeyError as e:
            logger.error(f"Missing form field: {e}")
            flash(f"Missing required field: {e}", "danger")
            return redirect(url_for('add_task'))
        if not task_name or not frequency or not compliance_ref or not assigned_to:
            flash("All fields must be filled.", "danger")
            return redirect(url_for('add_task'))
        tasks.insert_one({
            'name': task_name,
            'frequency': frequency,
            'compliance_ref': compliance_ref,
            'assigned_to': assigned_to,
            'last_sent': None,
            'due_date': None,
            'completed': False,
            'acknowledged': False,
            'evidence': None
        })
        logger.info(f"Task {task_name} ({compliance_ref}) added for {assigned_to}")
        audit_logs.insert_one({'action': 'add_task', 'task_name': task_name, 'assigned_to': assigned_to, 'timestamp': datetime.now()})
        flash("Task added successfully!", "success")
        return redirect(url_for('dashboard'))
    return render_template('add_task.html')

@app.route('/acknowledge_task/<task_id>', methods=['POST'])
def acknowledge_task(task_id):
    if 'user' not in session:
        flash("Please log in to acknowledge tasks.", "warning")
        return redirect(url_for('login'))
    tasks.update_one({'_id': ObjectId(task_id), 'assigned_to': session['user']},
                     {'$set': {'acknowledged': True}})
    logger.info(f"Task {task_id} acknowledged by {session['user']}")
    audit_logs.insert_one({'action': 'acknowledge_task', 'task_id': str(task_id), 'email': session['user'], 'timestamp': datetime.now()})
    flash("Task acknowledged!", "success")
    return redirect(url_for('dashboard'))

@app.route('/complete_task/<task_id>', methods=['POST'])
def complete_task(task_id):
    if 'user' not in session:
        flash("Please log in to complete tasks.", "warning")
        return redirect(url_for('login'))
    tasks.update_one({'_id': ObjectId(task_id), 'assigned_to': session['user']},
                     {'$set': {'completed': True}})
    logger.info(f"Task {task_id} marked as completed by {session['user']}")
    audit_logs.insert_one({'action': 'complete_task', 'task_id': str(task_id), 'email': session['user'], 'timestamp': datetime.now()})
    flash("Task completed! Please upload evidence if required.", "success")
    return redirect(url_for('evidence_upload', task_id=task_id))

@app.route('/evidence_upload/<task_id>', methods=['GET', 'POST'])
def evidence_upload(task_id):
    if 'user' not in session:
        flash("Please log in to upload evidence.", "warning")
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file uploaded.", "danger")
            return redirect(url_for('evidence_upload', task_id=task_id))
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            flash("Invalid file type. Allowed: pdf, png, jpg, jpeg.", "danger")
            return redirect(url_for('evidence_upload', task_id=task_id))
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        tasks.update_one({'_id': ObjectId(task_id)}, {'$set': {'evidence': filename}})
        logger.info(f"Evidence {filename} uploaded for task {task_id}")
        audit_logs.insert_one({'action': 'upload_evidence', 'task_id': str(task_id), 'filename': filename, 'email': session['user'], 'timestamp': datetime.now()})
        flash("Evidence uploaded successfully!", "success")
        return redirect(url_for('dashboard'))
    return render_template('evidence_upload.html', task_id=task_id)

@app.route('/reports')
def reports():
    if 'user' not in session:
        flash("Please log in to view reports.", "warning")
        return redirect(url_for('login'))
    user_doc = users.find_one({'email': session['user']})
    user_role = user_doc.get('role', 'Employee') if user_doc else 'Employee'
    if user_role not in ['IT Admin', 'Compliance Officer']:
        flash("Only IT Admins and Compliance Officers can view reports.", "danger")
        return redirect(url_for('dashboard'))
    logs = audit_logs.find().sort('timestamp', -1).limit(100)
    return render_template('reports.html', logs=logs)

@app.route('/logout')
def logout():
    if 'user' in session:
        logger.info(f"User {session['user']} logged out")
        audit_logs.insert_one({'action': 'logout', 'email': session['user'], 'timestamp': datetime.now()})
        session.pop('user', None)
        session.pop('google_token', None)
    return redirect(url_for('index'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)