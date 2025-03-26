Compliance Reminder System
A web-based application designed to manage compliance tasks under NIST (e.g., NIST SP 800-53) and ISO (e.g., ISO/IEC 27001) frameworks. It sends automated monthly and yearly reminders, tracks task completion, and logs actions for audit purposes. This version includes user authentication (login/register) and a basic static interface.

Features
User Authentication: Register and log in with email, password, and role.
Task Management: Add, view, and complete tasks via forms.
Automated Reminders: Sends email notifications for tasks due monthly or yearly.
Audit Logging: Records actions (e.g., logins, task updates) in MongoDB and a log file.
Security: Password hashing with bcrypt and TLS for email/MongoDB.
Frontend: Simple HTML/CSS interface with Flask (no JavaScript).
Tech Stack
Backend: Python, Flask, Flask-Login, APScheduler, PyMongo
Database: MongoDB (with TLS)
Frontend: HTML, CSS
Security: Bcrypt (password hashing), TLS (email/MongoDB)
Logging: Python logging module
Prerequisites
Python 3.8+
MongoDB (local or MongoDB Atlas)
SMTP server access (e.g., Gmail with app-specific password)
Git (optional, for cloning)
Installation
1. Clone the Repository
bash

Collapse

Wrap

Copy
git clone https://github.com/kabuprojects/cosf323_january2025_group10.git
cd compliance-reminder-system
2. Set Up a Virtual Environment
bash

Collapse

Wrap

Copy
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
3. Install Dependencies
bash

Collapse

Wrap

Copy
pip install flask flask-login pymongo apscheduler python-dotenv bcrypt
