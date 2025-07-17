
from django.contrib import admin
from .models import Team, Match


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('home_team', 'away_team', 'match_date', 'location', 'status')
    list_filter = ('status', 'match_date', 'location')
    search_fields = ('home_team__name', 'away_team__name', 'location')
    ordering = ('-match_date',)
    list_per_page = 25
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('home_team', 'away_team')