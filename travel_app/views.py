import re
import pandas as pd
import requests
from django.conf import settings
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import (
    FAQ,
    EmergencyContact,
    Hotel,
    Hotspot,
    Place,
    RecommendationHistory,
    VisitorCounter,
)
from .utils import haversine


# =========================
# HOME
# =========================
def home(request):
    places = Place.objects.filter(featured=True, is_active=True)
    counter, created = VisitorCounter.objects.get_or_create(pk=1)

    # Increment counter ONLY ONCE per browser session
    if not request.session.get("has_visited"):
        request.session["has_visited"] = True
        counter.total_visits += 1
        counter.save()

    places = Place.objects.filter(is_active=True)[:6]

    return render(request, "home.html", {"places": places})


# =========================
# PLACE DETAIL
# =========================
def place_detail(request, place_id):
    place = get_object_or_404(Place, place_id=place_id)
    hotels = Hotel.objects.filter(place=place)

    weather_data = get_weather(place.latitude, place.longitude)
    alert = weather_alert(weather_data)

    # Get hotspots from database
    hotspots = list(Hotspot.objects.filter(place=place))

    # Calculate distance using Haversine
    for hotspot in hotspots:
        hotspot.distance = haversine(
            place.latitude, place.longitude, hotspot.latitude, hotspot.longitude
        )

    # Sort by nearest hotspot
    hotspots = sorted(hotspots, key=lambda x: x.distance)

    # Show only first 8
    hotspots = hotspots[:8]

    return render(
        request,
        "place_details.html",
        {
            "place": place,
            "hotels": hotels,
            "weather": weather_data,
            "alert": alert,
            "hotspots": hotspots,
        },
    )
# =========================
# RECOMMENDATION
# =========================
def recommendation(request):

    recommendations = []
    message = ""

    # Store selected values
    category = ""
    activities = []
    province = "Any Province"
    budget = ""
    duration = ""

    # 1. Fixed 5 main categories
    categories = ["Nature", "Wildlife", "Adventure", "Trekking", "Cultural"]

    provinces = Place.objects.values_list("province", flat=True).distinct()

    activity_set = set()

    for item in Place.objects.values_list("activities", flat=True):
        if item:
            for activity in item.split(","):
                activity_set.add(activity.strip())

    activities_list = sorted(activity_set)

    if request.method == "POST":

        category = request.POST.get("category")
        activities = request.POST.getlist("activities")
        province = request.POST.get("province")
        budget = request.POST.get("budget_level")
        duration = request.POST.get("duration")

        # Category is required
        if not category:
            message = "Please select a category."

            return render(
                request,
                "recommendation.html",
                {
                    "recommendations": [],
                    "message": message,
                    "categories": categories,
                    "activities_list": activities_list,
                    "provinces": provinces,
                    "selected_category": category,
                    "selected_activities": activities,
                    "selected_province": province,
                    "selected_budget": budget,
                    "selected_duration": duration,
                },
            )

        # Save history
        RecommendationHistory.objects.create(
            category=category,
            activities=", ".join(activities),
            province=province,
            budget_level=budget,
            duration=duration,
        )

        # ---------------------------------------
        # Normalize Input Values
        # ---------------------------------------
        normalized_budget = budget.split("(")[0].strip() if budget else ""

        # ---------------------------------------
        # Load Place data into DataFrame
        # ---------------------------------------
        data = []

        for p in Place.objects.all():
            data.append(
                {
                    "place_id": p.place_id,
                    "place_name": p.place_name,
                    "category": p.category,
                    "activities": p.activities,
                    "province": p.province,
                    "budget_level": p.budget_level,
                    "duration": p.duration,
                    "description": p.description,
                    "image": p.image,
                }
            )

        df = pd.DataFrame(data).fillna("")
        df["duration_bucket"] = df["duration"].str.strip()

        # ---------------------------------------
        # 1. Non-Budget Filters (Category, Province, Duration)
        # ---------------------------------------
        if category:
            df = df[df["category"].str.contains(category, case=False, na=False)]

        if province and province != "Any Province":
            df = df[df["province"].str.lower() == province.lower()]

        if duration:
            df = df[df["duration_bucket"].str.lower() == duration.lower()]

        # ---------------------------------------
        # 2. Exact-Budget-First with Progressive Fallback
        # ---------------------------------------
        if normalized_budget:
            user_b = normalized_budget.lower()
            exact_df = df[df["budget_level"].str.lower() == user_b]

            if not exact_df.empty:
                # Exact matches exist: filter strictly to chosen budget
                df = exact_df
            else:
                # Zero exact matches: check if fallback pool has options
                if user_b == "low":
                    # Low is strict ceiling -> no fallback allowed
                    df = df.iloc[0:0]
                elif user_b == "medium":
                    # Medium fallback -> Low only
                    df = df[df["budget_level"].str.lower() == "low"]
                elif user_b == "high":
                    # High fallback -> Medium + Low
                    df = df[df["budget_level"].str.lower().isin(["medium", "low"])]

                # Set notice message if fallback candidates exist
                if not df.empty:
                    message = (
                        "No exact matches were found for your selected budget "
                        "and duration. Showing top recommendations with alternative budgets."
                    )

        # ---------------------------------------
        # 3. Similarity Scoring & Ranking
        # ---------------------------------------
        if df.empty:
            message = "No places found matching all selected preferences."
        else:
            result = df.copy()

            result["features"] = (
                result["category"]
                + " "
                + result["activities"]
                + " "
                + result["activities"]  # weighted twice
            )

            activity_text = " ".join(activities)
            user_features = f"{category} {activity_text} {activity_text}"

            documents = [user_features] + result["features"].tolist()

            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf_matrix = vectorizer.fit_transform(documents)

            similarity = cosine_similarity(
                tfidf_matrix[0:1], tfidf_matrix[1:]
            )

            result["similarity"] = similarity.flatten()

            

            # --- Individual filter match flags ---
            result["province_match"] = (
                (province == "Any Province") or
                (result["province"].str.lower() == province.lower())
            )

            if normalized_budget:
                result["budget_match"] = (
                    result["budget_level"].str.lower() == normalized_budget.lower()
                )
            else:
                result["budget_match"] = True

            if duration:
                result["duration_match"] = (
                    result["duration_bucket"].str.lower() == duration.lower()
                )
            else:
                result["duration_match"] = True

            # --- Weighted composite score (sums to 1.0 / 100%) ---
            SIMILARITY_WEIGHT = 0.55
            PROVINCE_WEIGHT   = 0.15
            BUDGET_WEIGHT     = 0.15
            DURATION_WEIGHT   = 0.15

            result["combined_score"] = (
                result["similarity"] * SIMILARITY_WEIGHT
                + result["province_match"].astype(int) * PROVINCE_WEIGHT
                + result["budget_match"].astype(int) * BUDGET_WEIGHT
                + result["duration_match"].astype(int) * DURATION_WEIGHT
            ).clip(lower=0, upper=1)

            result["match"] = (result["combined_score"] * 100).round(1)

            result = result.sort_values(by="combined_score", ascending=False)

            recommendations = result.head(5).to_dict("records")

    return render(
        request,
        "recommendation.html",
        {
            "recommendations": recommendations,
            "message": message,
            "categories": categories,
            "activities_list": activities_list,
            "provinces": provinces,
            "selected_category": category,
            "selected_activities": activities,
            "selected_province": province,
            "selected_budget": budget,
            "selected_duration": duration,
        },
    )
def get_activities(request):
    category = request.GET.get("category")
    activities = set()

    places = Place.objects.filter(category__iexact=category)

    for place in places:
        if place.activities:
            for activity in place.activities.split(","):
                activities.add(activity.strip())

    return JsonResponse(sorted(list(activities)), safe=False)

# =========================
# EXPLORE
# =========================
def explore(request):
    search = request.GET.get("search", "").strip()
    categories = request.GET.getlist("category")
    activities = request.GET.getlist("activity")

    suggestion = None

    # If no search/filter is applied, show only featured places
    if not (search or categories or activities):
        places = Place.objects.filter(featured=True, is_active=True)

    else:
        # Search through ALL active places
        places = Place.objects.filter(is_active=True)

        if search:
            # Search only destination name and city
            destination_results = places.filter(
                Q(place_name__icontains=search) | Q(city__icontains=search)
            )

            # If destination not found, try fuzzy suggestion
            if not destination_results.exists():
                place_names = list(
                    Place.objects.filter(is_active=True).values_list(
                        "place_name", flat=True
                    )
                )

                match = process.extractOne(
                    search, place_names, scorer=fuzz.WRatio
                )

                if match and match[1] >= 75:
                    suggestion = match[0]

                # No exact destination found
                places = Place.objects.none()

            else:
                # Destination found
                places = destination_results

                # Apply category filter
                if categories:
                    places = places.filter(category__in=categories)

                # Apply activity filter
                if activities:
                    act_q = Q()
                    for act in activities:
                        act_q |= Q(activities__icontains=act)
                    places = places.filter(act_q)

                # Relevance ranking
                places = places.annotate(
                    relevance=Case(
                        When(place_name__icontains=search, then=Value(2)),
                        When(city__icontains=search, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ).order_by("-relevance", "place_name")

        else:
            # No destination search, only filters
            if categories:
                q = Q()
                for category in categories:
                    q |= Q(category__icontains=category)
                places = places.filter(q)

            if activities:
                act_q = Q()
                for act in activities:
                    act_q |= Q(activities__icontains=act)
                places = places.filter(act_q)

        # Fuzzy suggestion if nothing matched
        if search and not places.exists():
            place_names = list(
                Place.objects.filter(is_active=True).values_list(
                    "place_name", flat=True
                )
            )

            match = process.extractOne(
                search, place_names, scorer=fuzz.WRatio
            )

            if match and match[1] >= 60:
                suggestion = match[0]

        # Order results by relevance
        elif search:
            places = places.annotate(
                relevance=Case(
                    When(place_name__icontains=search, then=Value(2)),
                    When(city__icontains=search, then=Value(1)),
                    output_field=IntegerField(),
                )
            ).order_by("-relevance", "place_name")

    return render(
        request,
        "explore.html",
        {
            "featured_places": places,
            "search": search,
            "selected_categories": categories,
            "selected_activities": activities,
            "suggestion": suggestion,
        },
    )


# =========================
# ALL PLACES
# =========================
def all_places(request):
    search = request.GET.get("search", "").strip()

    places = Place.objects.filter(is_active=True)

    if search:
        places = places.filter(
            Q(place_name__icontains=search)
            | Q(city__icontains=search)
            | Q(category__icontains=search)
            | Q(province__icontains=search)
            | Q(activities__icontains=search)
            | Q(description__icontains=search)
        )

    return render(
        request,
        "all_places.html",
        {
            "places": places,
            "search": search,
        },
    )


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
        Q(place_name__icontains=query)
        | Q(city__icontains=query)
        | Q(category__icontains=query)
        | Q(province__icontains=query)
        | Q(activities__icontains=query)
        | Q(description__icontains=query)
    )[:8]

    return JsonResponse(
        [
            {
                "name": p.place_name,
                "city": p.city,
                "province": p.province,
                "category": p.category,
            }
            for p in places
        ],
        safe=False,
    )


# =========================
# CATEGORY PLACES
# =========================
def category_places(request, category):
    places = Place.objects.filter(category__icontains=category, is_active=True)

    return render(
        request,
        "category_places.html",
        {
            "category": category,
            "places": places,
        },
    )


# =========================
# SUPPORT PAGES
# =========================
def emergency(request):
    contacts = EmergencyContact.objects.all()
    return render(request, "emergency.html", {"contacts": contacts})


def faq(request):
    faqs = FAQ.objects.all()
    return render(request, "faq.html", {"faqs": faqs})


def privacy_policy(request):
    return render(request, "privacy_policy.html")


def terms_conditions(request):
    return render(request, "terms_conditions.html")


# =========================
# WEATHER API
# =========================
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


# =========================
# CUSTOM ADMIN LOGOUT VIEW
# =========================
def custom_admin_logout(request):
    from django.contrib.auth import logout

    logout(request)
    return redirect("/admin/login/")