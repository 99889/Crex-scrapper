"""
Celery tasks for the matches app.
"""

from celery import shared_task
from django.utils import timezone
from .scraper import CREXScraper
from .models import Match
import logging

logger = logging.getLogger(__name__)


@shared_task
def update_match_list():
    """Update the match list by scraping the main fixtures page."""
    logger.info("Starting update_match_list task")
    
    try:
        scraper = CREXScraper()
        matches_scraped = scraper.scrape_match_list()
        
        logger.info(f"update_match_list task completed. Scraped {matches_scraped} matches")
        return f"Successfully scraped {matches_scraped} matches"
        
    except Exception as e:
        logger.error(f"Error in update_match_list task: {e}")
        return f"Error: {e}"


@shared_task
def check_live_matches():
    """Check for live matches and update their data."""
    logger.info("Starting check_live_matches task")
    
    try:
        scraper = CREXScraper()
        matches_updated = scraper.check_live_matches()
        
        logger.info(f"check_live_matches task completed. Updated {matches_updated} matches")
        return f"Successfully updated {matches_updated} live matches"
        
    except Exception as e:
        logger.error(f"Error in check_live_matches task: {e}")
        return f"Error: {e}"


@shared_task
def scrape_match_details(match_id):
    """Scrape detailed information for a specific match."""
    logger.info(f"Starting scrape_match_details task for match {match_id}")
    
    try:
        match = Match.objects.get(id=match_id)
        scraper = CREXScraper()
        
        # Construct match URL (adjust based on actual URL structure)
        match_url = f"{scraper.base_url}/match/{match_id}"
        
        details = scraper.scrape_match_details(match_url)
        
        if details:
            # Here you would save the detailed match data to the database
            # For now, we'll just log it
            logger.info(f"Successfully scraped details for match {match_id}")
            
            # Update match status if live data is available
            if details.get('live'):
                match.status = 'Live'
                match.save()
                logger.info(f"Updated match {match_id} status to Live")
            
            return f"Successfully scraped details for match {match_id}"
        else:
            return f"No details found for match {match_id}"
            
    except Match.DoesNotExist:
        logger.error(f"Match with ID {match_id} not found")
        return f"Match with ID {match_id} not found"
    except Exception as e:
        logger.error(f"Error in scrape_match_details task: {e}")
        return f"Error: {e}"


@shared_task
def trigger_live_scraping():
    """Trigger live scraping for matches that are scheduled to start soon."""
    logger.info("Starting trigger_live_scraping task")
    
    try:
        from datetime import timedelta
        
        # Get matches starting within the next hour
        now = timezone.now()
        upcoming_matches = Match.objects.filter(
            match_date__gte=now,
            match_date__lte=now + timedelta(hours=1),
            status='Scheduled'
        )
        
        triggered_tasks = 0
        
        for match in upcoming_matches:
            # Schedule detailed scraping for this match
            scrape_match_details.delay(match.id)
            triggered_tasks += 1
            logger.info(f"Triggered live scraping for match {match.id}: {match}")
        
        logger.info(f"trigger_live_scraping task completed. Triggered {triggered_tasks} tasks")
        return f"Successfully triggered {triggered_tasks} live scraping tasks"
        
    except Exception as e:
        logger.error(f"Error in trigger_live_scraping task: {e}")
        return f"Error: {e}"


@shared_task
def cleanup_old_matches():
    """Clean up old matches from the database."""
    logger.info("Starting cleanup_old_matches task")
    
    try:
        from datetime import timedelta
        
        # Delete matches older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        old_matches = Match.objects.filter(match_date__lt=cutoff_date)
        
        count = old_matches.count()
        old_matches.delete()
        
        logger.info(f"cleanup_old_matches task completed. Deleted {count} old matches")
        return f"Successfully deleted {count} old matches"
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_matches task: {e}")
        return f"Error: {e}"