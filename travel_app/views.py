from django.shortcuts import render, get_object_or_404
from .models import Place   # IMPORTANT

# Home page
def home(request):
    places = Place.objects.all()   # GET DATA
    return render(request, 'home.html', {'places': places})

# Recommendation page
def recommendation(request):
    return render(request, 'recommendation.html')

# ✅ Place Detail Page (NEW)
def place_detail(request, place_id):
    place = get_object_or_404(Place, place_id=place_id)

    return render(request, 'place_details.html', {
        'place': place
    })