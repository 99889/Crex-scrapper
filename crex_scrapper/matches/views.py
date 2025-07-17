from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from .models import Match, Team
from .scraper import CREXScraper
from .tasks import update_match_list, check_live_matches, scrape_match_details
import logging

logger = logging.getLogger(__name__)


def match_list(request):
    """Display paginated list of matches."""
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    team_filter = request.GET.get('team', '')
    date_filter = request.GET.get('date', 'all')
    
    # Base queryset
    matches = Match.objects.select_related('home_team', 'away_team').order_by('-match_date')
    
    # Apply filters
    if status_filter != 'all':
        matches = matches.filter(status=status_filter)
    
    if team_filter:
        matches = matches.filter(
            Q(home_team__name__icontains=team_filter) | 
            Q(away_team__name__icontains=team_filter)
        )
    
    if date_filter == 'today':
        today = timezone.now().date()
        matches = matches.filter(match_date__date=today)
    elif date_filter == 'upcoming':
        now = timezone.now()
        matches = matches.filter(match_date__gte=now)
    elif date_filter == 'past':
        now = timezone.now()
        matches = matches.filter(match_date__lt=now)
    
    # Pagination
    paginator = Paginator(matches, 20)  # 20 matches per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all teams for filter dropdown
    teams = Team.objects.all().order_by('name')
    
    context = {
        'matches': page_obj,
        'teams': teams,
        'status_filter': status_filter,
        'team_filter': team_filter,
        'date_filter': date_filter,
        'total_matches': matches.count(),
    }
    
    return render(request, 'matches/match_list.html', context)


def match_detail(request, match_id):
    """Display detailed information for a specific match."""
    match = get_object_or_404(Match, id=match_id)
    
    # Trigger detailed scraping for this match
    scrape_match_details.delay(match_id)
    
    context = {
        'match': match,
    }
    
    return render(request, 'matches/match_detail.html', context)


def live_matches(request):
    """Display currently live matches."""
    live_matches = Match.objects.filter(status='Live').select_related('home_team', 'away_team')
    
    context = {
        'live_matches': live_matches,
    }
    
    return render(request, 'matches/live_matches.html', context)


def api_matches(request):
    """API endpoint to get matches in JSON format."""
    status_filter = request.GET.get('status', 'all')
    limit = min(int(request.GET.get('limit', 50)), 100)  # Max 100 matches
    
    matches = Match.objects.select_related('home_team', 'away_team').order_by('-match_date')
    
    if status_filter != 'all':
        matches = matches.filter(status=status_filter)
    
    matches = matches[:limit]
    
    data = []
    for match in matches:
        data.append({
            'id': match.id,
            'home_team': match.home_team.name,
            'away_team': match.away_team.name,
            'match_date': match.match_date.isoformat(),
            'location': match.location,
            'status': match.status,
        })
    
    return JsonResponse({
        'matches': data,
        'count': len(data),
        'total_matches': Match.objects.count(),
    })


def trigger_scraping(request):
    """Manually trigger scraping tasks."""
    if request.method == 'POST':
        task_type = request.POST.get('task_type')
        
        try:
            if task_type == 'match_list':
                update_match_list.delay()
                message = "Match list scraping task triggered successfully."
            elif task_type == 'live_matches':
                check_live_matches.delay()
                message = "Live matches check task triggered successfully."
            else:
                message = "Invalid task type."
                
            return JsonResponse({'success': True, 'message': message})
        except Exception as e:
            logger.error(f"Error triggering scraping task: {e}")
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Only POST requests are allowed.'})


def dashboard(request):
    """Display dashboard with match statistics."""
    total_matches = Match.objects.count()
    live_matches = Match.objects.filter(status='Live').count()
    scheduled_matches = Match.objects.filter(status='Scheduled').count()
    completed_matches = Match.objects.filter(status='Completed').count()
    
    # Recent matches (last 10)
    recent_matches = Match.objects.select_related('home_team', 'away_team').order_by('-match_date')[:10]
    
    # Today's matches
    today = timezone.now().date()
    today_matches = Match.objects.filter(match_date__date=today).select_related('home_team', 'away_team')
    
    context = {
        'total_matches': total_matches,
        'live_matches': live_matches,
        'scheduled_matches': scheduled_matches,
        'completed_matches': completed_matches,
        'recent_matches': recent_matches,
        'today_matches': today_matches,
    }
    
    return render(request, 'matches/dashboard.html', context)


def test_scraper(request):
    """Test the scraper functionality."""
    if request.method == 'POST':
        try:
            scraper = CREXScraper()
            
            # Test scraping match list
            matches_scraped = scraper.scrape_match_list()
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully scraped {matches_scraped} matches',
                'matches_scraped': matches_scraped
            })
            
        except Exception as e:
            logger.error(f"Error testing scraper: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return render(request, 'matches/test_scraper.html')