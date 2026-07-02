from django.db import models


class Place(models.Model):
    place_id = models.IntegerField(unique=True)
    place_name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    activities = models.TextField()
    province = models.CharField(max_length=100)
    duration = models.CharField(max_length=50)
    budget_level = models.CharField(max_length=20)
    tourist_type = models.CharField(max_length=50)
    description = models.TextField()
    latitude = models.DecimalField(max_digits=10, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)
    image = models.CharField(max_length=100)

    featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.place_name


# -------------------------
# HOTEL MODEL
# -------------------------
class Hotel(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='hotels')
    hotel_name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True, null=True)
    price_range = models.CharField(max_length=100)   # Low / Medium / High
    rating = models.DecimalField(max_digits=2, decimal_places=1, blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.hotel_name


# -------------------------
# EMERGENCY CONTACT MODEL
# -------------------------
class EmergencyContact(models.Model):
    title = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title


# -------------------------
# FAQ MODEL
# -------------------------
class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()

    def __str__(self):
        return self.question
    
    #history model
class RecommendationHistory(models.Model):
    category = models.CharField(max_length=100)
    activities = models.TextField()
    province = models.CharField(max_length=100)
    budget_level = models.CharField(max_length=20)
    duration = models.CharField(max_length=50)
    tourist_type = models.CharField(max_length=50)
    searched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.searched_at.strftime('%Y-%m-%d %H:%M')}"
    
class VisitorCounter(models.Model):
    total_visits = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Total Visitors: {self.total_visits}"