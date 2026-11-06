# ICT Asset Tracker

A Django website for tracking office equipment, its status, and who it is assigned to.

## Features

- Staff-only dashboard with asset totals grouped by status.
- Search assets by name, asset tag, serial number, or assigned person.
- Filter the asset list by status and category; show 10 assets per page.
- Add, view, edit, and delete assets.
- Change an asset's status from the dashboard or asset list.
- View status and assignment changes recorded by the website on an asset's detail page.
- Export the filtered asset list to CSV.
- View a printable report grouped by status.
- Manage assets and their history in Django admin.
- Import new assets from a CSV file with the `import_assets` command.

History is recorded for status and assignee changes made through the website. Changes made before history was added, or directly in the database, do not have a history entry.

## Technologies

- Python
- Django
- SQLite
- HTML and CSS
- `python-decouple` for loading settings from `.env`

## Run on Windows

Open PowerShell in the project folder (the folder containing `manage.py`).

### 1. Create and activate a virtual environment

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, open Command Prompt and run:

```cmd
venv\Scripts\activate.bat
```

### 2. Install the project packages

With the virtual environment active, run:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Create your local `.env` file

Copy the example file and open the copy:

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace the `SECRET_KEY` example value with a generated key. Generate one with:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the generated key after `SECRET_KEY=` in `.env`. Keep `.env` private; it is listed in `.gitignore` and should not be uploaded to GitHub. `DEBUG=True` is for local development only.

### 4. Create the database tables

```powershell
python manage.py migrate
```

### 5. Create a staff administrator account

```powershell
python manage.py createsuperuser
```

Follow the prompts to set a username and password. A Django superuser is a staff user and can sign in to the tracker.

### 6. Import the sample assets

The included `assets.csv` is in the project folder. Import its new asset tags with:

```powershell
python manage.py import_assets
```

Existing or repeated asset tags are skipped. To import a different CSV file, provide its path:

```powershell
python manage.py import_assets .\path\to\assets.csv
```

### 7. Start the development server

```powershell
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in your browser and sign in with your staff account.

## Screenshots
screenshots/
    dashboard.png
    asset.png
    login.png
    addasset.png



