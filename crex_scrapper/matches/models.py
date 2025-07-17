
from django.db import models


class Team(models.Model):
    """Model representing a cricket team."""
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Match(models.Model):
    """Model representing a cricket match."""
    home_team = models.ForeignKey(Team, related_name='home_matches', on_delete=models.CASCADE)
    away_team = models.ForeignKey(Team, related_name='away_matches', on_delete=models.CASCADE)
    match_date = models.DateTimeField()
    location = models.CharField(max_length=255)
    status = models.CharField(max_length=20)  

    def __str__(self):
        return f"{self.home_team} vs {self.away_team}"