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
    

class Hotel(models.Model):
    hotel_id = models.IntegerField(primary_key=True)
    place_id = models.IntegerField()
    hotel_name = models.CharField(max_length=100)
    price_range = models.CharField(max_length=50)
    contact = models.CharField(max_length=20)
    image = models.CharField(max_length=100)  # IMPORTANT