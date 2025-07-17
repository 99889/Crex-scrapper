import requests
from bs4 import BeautifulSoup
import logging
import time
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import IntegrityError, transaction
from .models import Match, Team
import re

logger = logging.getLogger(__name__)


class CREXScraper:
    """Main scraper class for CREX cricket data."""
    
    def __init__(self):
        self.base_url = "https://crex.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def get_page(self, url, retries=3):
        """Get page content with retry logic."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Failed to get page after {retries} attempts: {url}")
                    raise

    def parse_match_date(self, date_str, time_str):
        """Parse match date and time from scraped strings."""
        try:
            # Handle different date formats
            if "today" in date_str.lower():
                match_date = timezone.now().date()
            elif "tomorrow" in date_str.lower():
                match_date = (timezone.now() + timedelta(days=1)).date()
            else:
                # Parse date formats like "Wed, 16 Jul 2025"
                date_parts = date_str.split(',')
                if len(date_parts) > 1:
                    date_part = date_parts[1].strip()
                    match_date = datetime.strptime(date_part, "%d %b %Y").date()
                else:
                    match_date = timezone.now().date()

            # Parse time
            time_match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_str.upper())
            if time_match:
                hour, minute, ampm = time_match.groups()
                hour = int(hour)
                minute = int(minute)
                
                if ampm == 'PM' and hour != 12:
                    hour += 12
                elif ampm == 'AM' and hour == 12:
                    hour = 0
                
                match_time = datetime.combine(match_date, datetime.min.time().replace(hour=hour, minute=minute))
                return timezone.make_aware(match_time)
            
            return timezone.make_aware(datetime.combine(match_date, datetime.min.time()))
        except Exception as e:
            logger.error(f"Error parsing date/time: {date_str}, {time_str} - {e}")
            return timezone.now()

    def scrape_match_list(self):
        """Scrape the main match list page."""
        logger.info("Starting to scrape match list")
        
        try:
            response = self.get_page(f"{self.base_url}/fixtures/match-list")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            matches_scraped = 0
            
            # Look for match containers (adjust selectors based on actual HTML structure)
            match_containers = soup.find_all('div', class_=['match-item', 'fixture-item'])
            
            if not match_containers:
                # Fallback: look for any div that might contain match info
                match_containers = soup.find_all('div', string=re.compile(r'vs|V/s', re.IGNORECASE))
                
            for container in match_containers:
                try:
                    match_data = self.extract_match_data(container)
                    if match_data:
                        self.save_match_data(match_data)
                        matches_scraped += 1
                except Exception as e:
                    logger.error(f"Error processing match container: {e}")
                    continue
            
            logger.info(f"Scraped {matches_scraped} matches from match list")
            return matches_scraped
            
        except Exception as e:
            logger.error(f"Error scraping match list: {e}")
            return 0

    def extract_match_data(self, container):
        """Extract match data from a container element."""
        try:
            # Extract team names (adjust selectors based on actual HTML)
            team_elements = container.find_all('span', class_=['team-name', 'team'])
            
            if len(team_elements) < 2:
                # Fallback: look for text patterns
                text = container.get_text()
                vs_match = re.search(r'([A-Za-z\s]+)\s+vs\s+([A-Za-z\s]+)', text, re.IGNORECASE)
                if vs_match:
                    home_team = vs_match.group(1).strip()
                    away_team = vs_match.group(2).strip()
                else:
                    return None
            else:
                home_team = team_elements[0].get_text().strip()
                away_team = team_elements[1].get_text().strip()
            
            # Extract date and time
            date_element = container.find('span', class_=['match-date', 'date'])
            time_element = container.find('span', class_=['match-time', 'time'])
            
            date_str = date_element.get_text().strip() if date_element else ""
            time_str = time_element.get_text().strip() if time_element else ""
            
            # Extract location
            location_element = container.find('span', class_=['location', 'venue'])
            location = location_element.get_text().strip() if location_element else "TBD"
            
            # Extract match URL for detailed scraping
            match_link = container.find('a', href=True)
            match_url = match_link['href'] if match_link else ""
            
            if match_url and not match_url.startswith('http'):
                match_url = self.base_url + match_url
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'match_date': self.parse_match_date(date_str, time_str),
                'location': location,
                'status': 'Scheduled',
                'match_url': match_url
            }
            
        except Exception as e:
            logger.error(f"Error extracting match data: {e}")
            return None

    def save_match_data(self, match_data):
        """Save match data to database."""
        try:
            with transaction.atomic():
                # Get or create teams
                home_team, _ = Team.objects.get_or_create(name=match_data['home_team'])
                away_team, _ = Team.objects.get_or_create(name=match_data['away_team'])
                
                # Create or update match
                match, created = Match.objects.get_or_create(
                    home_team=home_team,
                    away_team=away_team,
                    match_date=match_data['match_date'],
                    defaults={
                        'location': match_data['location'],
                        'status': match_data['status']
                    }
                )
                
                if created:
                    logger.info(f"Created new match: {match}")
                else:
                    logger.info(f"Updated existing match: {match}")
                
                return match
                
        except Exception as e:
            logger.error(f"Error saving match data: {e}")
            return None

    def scrape_match_details(self, match_url):
        """Scrape detailed match information."""
        logger.info(f"Scraping match details from: {match_url}")
        
        try:
            response = self.get_page(match_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            details = {}
            
            # Scrape Match Info tab
            details['match_info'] = self.scrape_match_info(soup)
            
            # Scrape Squads tab
            details['squads'] = self.scrape_squads(soup)
            
            # Scrape Live tab (if match is live)
            details['live'] = self.scrape_live_data(soup)
            
            # Scrape Scorecard tab
            details['scorecard'] = self.scrape_scorecard(soup)
            
            return details
            
        except Exception as e:
            logger.error(f"Error scraping match details: {e}")
            return {}

    def scrape_match_info(self, soup):
        """Scrape match information."""
        try:
            match_info = {}
            
            # Extract various match details
            info_section = soup.find('div', class_=['match-info', 'info-section'])
            if info_section:
                # Extract toss, weather, etc.
                info_items = info_section.find_all('div', class_='info-item')
                for item in info_items:
                    label = item.find('span', class_='label')
                    value = item.find('span', class_='value')
                    if label and value:
                        match_info[label.get_text().strip()] = value.get_text().strip()
            
            return match_info
            
        except Exception as e:
            logger.error(f"Error scraping match info: {e}")
            return {}

    def scrape_squads(self, soup):
        """Scrape team squads."""
        try:
            squads = {}
            
            squad_sections = soup.find_all('div', class_=['squad-section', 'team-squad'])
            for section in squad_sections:
                team_name = section.find('h3', class_='team-name')
                if team_name:
                    team = team_name.get_text().strip()
                    players = []
                    
                    player_elements = section.find_all('div', class_=['player', 'player-name'])
                    for player in player_elements:
                        players.append(player.get_text().strip())
                    
                    squads[team] = players
            
            return squads
            
        except Exception as e:
            logger.error(f"Error scraping squads: {e}")
            return {}

    def scrape_live_data(self, soup):
        """Scrape live match data."""
        try:
            live_data = {}
            
            # Extract live scores, overs, etc.
            live_section = soup.find('div', class_=['live-section', 'live-score'])
            if live_section:
                # Current score
                score_elements = live_section.find_all('div', class_='score')
                for score in score_elements:
                    team = score.find('span', class_='team')
                    runs = score.find('span', class_='runs')
                    if team and runs:
                        live_data[team.get_text().strip()] = runs.get_text().strip()
                
                # Current over
                over_element = live_section.find('div', class_='current-over')
                if over_element:
                    live_data['current_over'] = over_element.get_text().strip()
            
            return live_data
            
        except Exception as e:
            logger.error(f"Error scraping live data: {e}")
            return {}

    def scrape_scorecard(self, soup):
        """Scrape match scorecard."""
        try:
            scorecard = {}
            
            # Extract innings data
            innings_sections = soup.find_all('div', class_=['innings', 'innings-section'])
            for i, innings in enumerate(innings_sections):
                innings_data = {}
                
                # Batting scorecard
                batting_table = innings.find('table', class_=['batting-table', 'scorecard-table'])
                if batting_table:
                    batting_data = []
                    rows = batting_table.find_all('tr')[1:]  # Skip header
                    
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            batting_data.append({
                                'player': cols[0].get_text().strip(),
                                'dismissal': cols[1].get_text().strip(),
                                'runs': cols[2].get_text().strip(),
                                'balls': cols[3].get_text().strip(),
                                'fours': cols[4].get_text().strip() if len(cols) > 4 else '0',
                                'sixes': cols[5].get_text().strip() if len(cols) > 5 else '0'
                            })
                    
                    innings_data['batting'] = batting_data
                
                # Bowling scorecard
                bowling_table = innings.find('table', class_=['bowling-table', 'bowling-scorecard'])
                if bowling_table:
                    bowling_data = []
                    rows = bowling_table.find_all('tr')[1:]  # Skip header
                    
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            bowling_data.append({
                                'player': cols[0].get_text().strip(),
                                'overs': cols[1].get_text().strip(),
                                'maidens': cols[2].get_text().strip(),
                                'runs': cols[3].get_text().strip(),
                                'wickets': cols[4].get_text().strip() if len(cols) > 4 else '0'
                            })
                    
                    innings_data['bowling'] = bowling_data
                
                scorecard[f'innings_{i+1}'] = innings_data
            
            return scorecard
            
        except Exception as e:
            logger.error(f"Error scraping scorecard: {e}")
            return {}

    def check_live_matches(self):
        """Check for live matches and update their data."""
        logger.info("Checking for live matches")
        
        try:
            # Get matches that should be live or starting soon
            now = timezone.now()
            recent_matches = Match.objects.filter(
                match_date__lte=now + timedelta(hours=1),
                match_date__gte=now - timedelta(hours=6)
            )
            
            live_matches_updated = 0
            
            for match in recent_matches:
                # In a real implementation, you'd have the match URL stored
                # For now, we'll construct a URL pattern
                match_url = f"{self.base_url}/match/{match.id}"  # Adjust based on actual URL structure
                
                try:
                    details = self.scrape_match_details(match_url)
                    if details:
                        # Update match status based on scraped data
                        if details.get('live'):
                            match.status = 'Live'
                            match.save()
                            live_matches_updated += 1
                            logger.info(f"Updated live match: {match}")
                            
                except Exception as e:
                    logger.error(f"Error updating live match {match}: {e}")
                    continue
            
            logger.info(f"Updated {live_matches_updated} live matches")
            return live_matches_updated
            
        except Exception as e:
            logger.error(f"Error checking live matches: {e}")
            return 0