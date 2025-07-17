A Django-based web scraping system that monitors cricket match schedules from CREX and tracks live match data.

## Features

- **Match List Scraping**: Automatically scrapes upcoming matches from CREX
- **Live Match Tracking**: Real-time updates for live matches
- **Detailed Match Data**: Scrapes match info, squads, live scores, and scorecards
- **Web Dashboard**: User-friendly interface to view matches and data
- **Scheduled Tasks**: Automated scraping using Celery
- **API Endpoints**: RESTful API for match data

## Project Structure

```
crex_scraper/
├── crex_scraper/          # Django project settings
├── matches/               # Main application
│   ├── models.py         # Database models
│   ├── views.py          # Web views
│   ├── scraper.py        # Scraping logic
│   ├── tasks.py          # Celery tasks
│   └── templates/        # HTML templates
├── templates/            # Base templates
├── static/              # Static files
├── requirements.txt     # Python dependencies
└── manage.py           # Django management script
```

## Prerequisites

- Python 3.8+
- Redis server (for Celery)
- Git (optional)

## Installation

### 1. Clone or Download the Project

```bash
# If using Git
git clone <repository-url>
cd crex_scraper

# Or download and extract the files to crex_scraper directory
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up the Database

```bash
python manage.py makemigrations
python manage.py migrate
```



