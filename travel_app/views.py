from django.shortcuts import render, get_object_or_404
from .models import Place

import csv
import os
from django.conf import settings

# Home page
def home(request):
    places = Place.objects.all()[:6]
    return render(request, 'home.html', {'places': places})

# Recommendation page
def recommendation(request):
    return render(request, 'recommendation.html')

# Explore page
def explore(request):
    featured_places = Place.objects.filter(place_id__in=[1, 4, 8, 13, 15, 16])
    return render(request, "explore.html", {"featured_places": featured_places})

# Contact page
def contact(request):
    return render(request, 'contact.html')

# All places
def all_places(request):
    places = Place.objects.all()
    return render(request, "all_places.html", {"places": places})

# Place detail page
def place_detail(request, id):
    place = get_object_or_404(Place, place_id=id)

    hotels = []
    csv_path = os.path.join(settings.BASE_DIR, 'hotels.csv')

    with open(csv_path, newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row['place_id'].strip() == str(place.place_id):

                hotels.append({
                    "name": row["hotel_name"],
                    "price_range": row["price_range"],
                    "contact": row["contact"],
                    "image": f"images/hotels/hotel_{row['hotel_id']}.jpg"
                })

    return render(request, 'place_details.html', {
        'place': place,
        'hotels': hotels
    })