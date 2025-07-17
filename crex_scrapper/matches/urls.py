from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    # Main pages
    path('', views.dashboard, name='dashboard'),
    path('matches/', views.match_list, name='match_list'),
    path('matches/<int:match_id>/', views.match_detail, name='match_detail'),
    path('live/', views.live_matches, name='live_matches'),
    
    # API endpoints
    path('api/matches/', views.api_matches, name='api_matches'),
    path('api/trigger-scraping/', views.trigger_scraping, name='trigger_scraping'),
    
    # Admin/Testing
    path('test-scraper/', views.test_scraper, name='test_scraper'),
]