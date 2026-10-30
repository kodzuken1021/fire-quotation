# Fire Protection Quotation and Inspection Request System

A Flask web application where clients browse fire protection products and services (prices are not shown), submit a quote request with an optional free inspection, and receive a formal quotation by email. Admins review requests, schedule inspections, set prices and send the PDF quotation.

**Tech stack:** Flask (Python), MySQL/MariaDB, HTML5, CSS3, Bootstrap 5, JavaScript, Flask-WTF, Flask-Mail

## Setup (Windows, PowerShell)

1. **Clone and enter the project**
   ```powershell
   git clone https://github.com/kodzuken1021/fire-quotation.git
   cd fire-quotation
   ```
2. **Create and activate a virtual environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
3. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Create your settings file**
   ```powershell
   copy .env.example .env
   ```
   Open `.env` and set `SECRET_KEY`, the database values and the email (SMTP) values.
5. **Create the database** (start MySQL in the XAMPP Control Panel first)
   ```powershell
   C:\xampp\mysql\bin\mysql.exe -u root < database\schema.sql
   ```
   Or open phpMyAdmin, go to Import, and choose `database/schema.sql`.
6. **Create an admin account**
   ```powershell
   flask --app run create-admin
   ```
7. **Run the app**
   ```powershell
   python run.py
   ```
   Open http://127.0.0.1:5000

## Project structure

```
run.py                 entry point
config.py              settings loaded from .env
database/schema.sql    MySQL schema + sample catalog data
app/
  __init__.py          app factory, blueprints, error pages
  db.py                database connection helper (parameterized queries only)
  decorators.py        login_required, admin_required
  main/ auth/ client/ admin/   blueprints (routes)
  models/              OOP classes
  templates/ static/   Bootstrap UI
```

## Client documentation
Add the client's name, requirements discussion notes and sign-off here or in a `docs/` folder.
