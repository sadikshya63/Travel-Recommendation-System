from django.shortcuts import render
from .models import Place

# Create your views here.


def home(request):
    return render(request, 'home.html')
def recommendation(request):
    return render(request, 'recommendation.html')
def explore(request):
    featured_places = Place.objects.filter(place_id__in=[1,4,8,13,15,16])
    return render(request, "explore.html", {"featured_places": featured_places})

def contact(request):
    return render(request, 'contact.html')

def all_places(request):
    places = Place.objects.all()
    return render(request, "all_places.html", {"places": places})