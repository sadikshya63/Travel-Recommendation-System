import os
import csv
import pandas as pd
import requests

from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Case, When, Value, IntegerField
from dotenv import load_dotenv

from rapidfuzz import process, fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Place, EmergencyContact, FAQ, Hotel

# =========================
# HOME
# =========================
def home(request):
    places = Place.objects.filter(is_active=True)[:6]

    return render(request, "home.html", {
        "places": places
    })


# =========================
# PLACE DETAIL
# =========================
def place_detail(request, place_id):

    place = get_object_or_404(Place, place_id=place_id)

    place = get_object_or_404(Place, place_id=place_id)

    hotels = Hotel.objects.filter(place=place)

    weather_data = get_weather(place.latitude, place.longitude)
    alert = weather_alert(weather_data)
    

    return render(request, "place_details.html", {
        "place": place,
        "hotels": hotels,
        "weather": weather_data,
        "alert": alert,
    })


# =========================
# RECOMMENDATION
# =========================
def recommendation(request):

    recommendations = []
    message = ""

    if request.method == "POST":

        category = request.POST.get("category")
        activities = request.POST.getlist("activities")
        province = request.POST.get("province")
        budget = request.POST.get("budget_level")
        duration = request.POST.get("duration")
        tourist = request.POST.get("tourist_type")

        csv_path = os.path.join(
            settings.BASE_DIR,
            "travel_app",
            "data",
            "places.csv"
        )

        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        df = df.fillna("")

        result = df.copy()

        # Category filter
        if category:
            result = result[result["category"].str.lower() == category.lower()]

        # Province filter
        if province and province != "Any Province":
            result = result[result["province"].str.lower() == province.lower()]

        # Budget filter
        if budget:
            result = result[result["budget_level"].str.lower() == budget.lower()]

        # Duration filter
        if duration:
            numbers = result["duration"].str.extract(r"(\d+)")
            min_days = numbers[0].fillna(0).astype(int)
            max_days = min_days

            if duration == "1-3 Days":
                result = result[max_days <= 3]
            elif duration == "4-6 Days":
                result = result[(max_days >= 4) & (min_days <= 6)]
            elif duration == "7-9 Days":
                result = result[(max_days >= 7) & (min_days <= 9)]
            elif duration == "10+ Days":
                result = result[max_days >= 10]

        # Tourist type filter
        if tourist:
            result = result[
                (result["tourist_type"].str.lower() == tourist.lower()) |
                (result["tourist_type"].str.lower() == "both")
            ]

        # Activities filter
        if activities:
            pattern = "|".join(activities)

            activity_result = result[
                result["activities"].str.contains(pattern, case=False, na=False, regex=True)
            ]

            if not activity_result.empty:
                result = activity_result
            else:
                message = "Exact activities not found. Showing similar destinations."

        # fallback
        if result.empty:
            message = "No exact destination found. Showing similar destinations."
            result = df.copy()

        # similarity scoring
        if not result.empty:

            result["features"] = (
                result["category"] + " " +
                result["activities"] + " " +
                result["province"] + " " +
                result["budget_level"] + " " +
                result["duration"] + " " +
                result["tourist_type"]
            )

            activity_text = " ".join(activities) if activities else ""

            user_features = (
                f"{category} {activity_text} {province} {budget} {duration} {tourist}"
            )

            documents = [user_features] + result["features"].tolist()

            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf = vectorizer.fit_transform(documents)

            similarity = cosine_similarity(tfidf[0:1], tfidf[1:])

            result["similarity"] = similarity.flatten()
            result["match"] = (result["similarity"] * 100).round().astype(int)

            result = result.sort_values(by="similarity", ascending=False)

            recommendations = result.head(5).to_dict("records")

    return render(request, "recommendation.html", {
        "recommendations": recommendations,
        "message": message,
    })


# =========================
# EXPLORE
# =========================
def explore(request):

    search = request.GET.get("search", "").strip()
    categories = request.GET.getlist("category")
    activities = request.GET.getlist("activity")

    suggestion = None

    featured_places = Place.objects.filter(
        place_id__in=[1, 4, 8, 13, 15, 16]
    )

    if search or categories or activities:

        if search:

            featured_places = Place.objects.filter(
                Q(place_name__icontains=search) |
                Q(category__icontains=search) |
                Q(province__icontains=search) |
                Q(activities__icontains=search)
            )

            if not featured_places.exists():

                place_names = list(Place.objects.values_list("place_name", flat=True))

                match = process.extractOne(
                    search,
                    place_names,
                    scorer=fuzz.WRatio
                )

                if match and match[1] >= 60:
                    suggestion = match[0]

            else:

                featured_places = featured_places.annotate(
                    relevance=Case(
                        When(place_name__icontains=search, then=Value(4)),
                        When(activities__icontains=search, then=Value(3)),
                        When(category__icontains=search, then=Value(2)),
                        When(province__icontains=search, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ).order_by("-relevance")

                if categories:
                    featured_places = featured_places.annotate(
                        category_boost=Case(
                            *[When(category=c, then=Value(1)) for c in categories],
                            default=Value(0),
                            output_field=IntegerField(),
                        )
                    ).order_by("-category_boost", "-relevance")

                if activities:
                    featured_places = featured_places.annotate(
                        activity_boost=Case(
                            *[When(activities__icontains=a, then=Value(1)) for a in activities],
                            default=Value(0),
                            output_field=IntegerField(),
                        )
                    ).order_by("-activity_boost", "-relevance")

        else:

            if categories:
                featured_places = featured_places.filter(category__in=categories)

            if activities:
                q = Q()
                for a in activities:
                    q |= Q(activities__icontains=a)
                featured_places = featured_places.filter(q)

    return render(request, "explore.html", {
        "featured_places": featured_places,
        "search": search,
        "selected_categories": categories,
        "selected_activities": activities,
        "suggestion": suggestion,
    })


# =========================
# ALL PLACES
# =========================
def all_places(request):

    search = request.GET.get("search", "").strip()

    places = Place.objects.all()

    if search:
        places = places.filter(
            Q(place_name__icontains=search) |
            Q(category__icontains=search) |
            Q(province__icontains=search) |
            Q(activities__icontains=search)
        )

    return render(request, "all_places.html", {
        "places": places,
        "search": search,
    })


# =========================
# CONTACT
# =========================
def contact(request):
    return render(request, "contact.html")


# =========================
# LIVE SEARCH API
# =========================
def search_suggestions(request):

    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse([], safe=False)

    places = Place.objects.filter(
        Q(place_name__icontains=query) |
        Q(category__icontains=query) |
        Q(province__icontains=query) |
        Q(activities__icontains=query)
    )[:8]

    return JsonResponse([
        {
            "name": p.place_name,
            "province": p.province,
            "category": p.category,
        }
        for p in places
    ], safe=False)


# =========================
# CATEGORY PLACES (FIXED)
# =========================
def category_places(request, category):

    csv_path = os.path.join(
        settings.BASE_DIR,
        "travel_app",
        "data",
        "places.csv",
    )

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    filtered = df[df["category"].str.lower() == category.lower()]
    places = filtered.to_dict(orient="records")

    return render(request, "category_places.html", {
        "category": category,
        "places": places,
    })


# =========================
# SUPPORT PAGES
# =========================
def emergency(request):
    contacts = EmergencyContact.objects.all()
    return render(request, "emergency.html", {
        "contacts": contacts
    })


def faq(request):
    faqs = FAQ.objects.all()
    return render(request, "faq.html", {
        "faqs": faqs
    })


def privacy_policy(request):
    return render(request, "privacy_policy.html")


def terms_conditions(request):
    return render(request, "terms_conditions.html")

#weather api
def get_weather(lat, lon):
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}"
        f"&appid={settings.WEATHER_API_KEY}&units=metric"
    )
    response = requests.get(url)
    return response.json()
def weather_alert(weather_data):
    main = weather_data["weather"][0]["main"].lower()

    if "rain" in main:
        return "🌧 Heavy Rain Warning"
    elif "thunderstorm" in main:
        return "⛈ Thunderstorm Alert"
    elif "fog" in main or "mist" in main:
        return "🌫 Dense Fog"
    elif "clear" in main:
        return "☀ Clear Weather"
    elif "snow" in main:
        return "❄ Snowfall Alert"
    else:
        return "🌡 Normal Weather Conditions"