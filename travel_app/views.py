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

    provinces = Place.objects.filter(is_active=True).values_list("province", flat=True).distinct()

    activity_set = set()

    for item in Place.objects.filter(is_active=True).values_list("activities", flat=True):
        if item:
            for activity in item.split(","):
                activity_set.add(activity.strip())

    activities_list = sorted(activity_set)

    if request.method == "POST":

        category = request.POST.get("category", "").strip()
        activities = request.POST.getlist("activities")
        province = request.POST.get("province", "").strip()
        budget = request.POST.get("budget_level", "").strip()
        duration = request.POST.get("duration", "").strip()

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
        # Helper: Exact Form Duration Bucket
        # ---------------------------------------
        def get_exact_duration_bucket(text):
            if not text:
                return ""
            t = str(text).lower().strip()

            # Handle direct form bucket strings
            if "1-4" in t or "1-3" in t or "2-4" in t or "3-4" in t:
                return "1-4 days"
            elif "5-9" in t or "4-6" in t or "7-9" in t:
                return "5-9 days"
            elif "10+" in t:
                return "10+ days"

            numbers = [int(n) for n in re.findall(r"\d+", t)]
            if not numbers:
                return ""

            max_days = max(numbers)
            if max_days <= 4:
                return "1-4 days"
            elif max_days <= 9:
                return "5-9 days"
            else:
                return "10+ days"

        # Helper: Budget Normalization
        def normalize_budget(text):
            if not text:
                return ""
            t = str(text).lower().strip().replace(" ", "").replace("-", "")
            if "lowmedium" in t:
                return "low-medium"
            elif "mediumhigh" in t:
                return "medium-high"
            elif "low" in t:
                return "low"
            elif "medium" in t:
                return "medium"
            elif "high" in t:
                return "high"
            return str(text).lower().strip()

        # ---------------------------------------
        # Load Place data into DataFrame
        # ---------------------------------------
        data = []

        for p in Place.objects.filter(is_active=True):
            img_url = p.image.url if hasattr(p.image, 'url') and p.image else str(p.image or '')
            data.append(
                {
                    "place_id": p.place_id,
                    "place_name": p.place_name,
                    "category": p.category or "",
                    "activities": p.activities or "",
                    "province": p.province or "",
                    "budget_level": p.budget_level or "",
                    "duration": p.duration or "",
                    "description": p.description or "",
                    "image": img_url,
                }
            )

        if not data:
            return render(
                request,
                "recommendation.html",
                {
                    "recommendations": [],
                    "message": "No active destinations available.",
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

        df = pd.DataFrame(data).fillna("")
        df["duration_bucket"] = df["duration"].apply(get_exact_duration_bucket)
        user_duration_bucket = get_exact_duration_bucket(duration)

        df["budget_clean"] = df["budget_level"].apply(normalize_budget)
        user_budget_clean = normalize_budget(budget)

        # ---------------------------------------
        # Rule-Based Filtering Engine (Strict Bucket Match)
        # ---------------------------------------
        def apply_filters(dataframe, cat, prov, dur_bkt, bdg_clean):
            filtered = dataframe.copy()

            if cat:
                filtered = filtered[
                    filtered["category"].str.lower().str.contains(cat.lower())
                ]

            if prov and prov != "Any Province":
                filtered = filtered[
                    filtered["province"].str.lower().str.strip() == prov.lower().strip()
                ]

            if dur_bkt:
                filtered = filtered[
                    filtered["duration_bucket"].str.lower() == dur_bkt.lower()
                ]

            if bdg_clean:
                filtered = filtered[
                    filtered["budget_clean"].str.lower() == bdg_clean.lower()
                ]

            return filtered

        # ---------------------------------------
        # Progressive Fallback Handling
        # ---------------------------------------
        # Stage 1: Exact match on Category + Province + Duration Bucket + Budget
        result = apply_filters(df, category, province, user_duration_bucket, user_budget_clean)

        if not result.empty:
            message = ""
        else:
            # Stage 2 (Impractical Combo Fallback, e.g. 10+ days with Low budget):
            # Keeps Duration Bucket strictly intact, relaxes Budget
            result_relax_budget = apply_filters(df, category, province, user_duration_bucket, None)
            
            if not result_relax_budget.empty:
                result = result_relax_budget
                message = (
                    f"No exact '{budget}' budget option found for '{duration}'. "
                    f"Showing destinations matching your selected duration ({duration}) and province in available budget tiers."
                )
            else:
                # Stage 3: Relax duration, keep budget
                result_relax_duration = apply_filters(df, category, province, None, user_budget_clean)

                if not result_relax_duration.empty:
                    result = result_relax_duration
                    message = (
                        f"No destinations found matching duration '{duration}'. "
                        f"Showing destinations matching your budget ({budget}) and province."
                    )
                else:
                    # Stage 4: Relax both budget & duration
                    result_cat_prov = apply_filters(df, category, province, None, None)

                    if not result_cat_prov.empty:
                        result = result_cat_prov
                        message = (
                            "No destinations matched all budget & duration preferences. "
                            "Showing destinations matching your category and province."
                        )
                    else:
                        # Stage 5: Relax province
                        result_cat = apply_filters(df, category, "Any Province", None, None)

                        if not result_cat.empty:
                            result = result_cat
                            message = (
                                f"No destinations found in {province}. "
                                f"Showing closest destinations in the '{category}' category."
                            )
                        else:
                            message = f"No destinations exist in the '{category}' category."
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

        # ---------------------------------------
        # STAGE 2: ACCURATE SCORING (ACTIVITY OVERLAP + TF-IDF)
        # ---------------------------------------
        result = result.copy()

        user_act_set = set([a.lower().strip() for a in activities if a.strip()])

        def calc_activity_ratio(place_act_str):
            if not user_act_set or not place_act_str:
                return 0.0
            place_acts = set([a.lower().strip() for a in str(place_act_str).split(",") if a.strip()])
            matched = user_act_set.intersection(place_acts)
            return len(matched) / len(user_act_set)

        result["activity_ratio"] = result["activities"].apply(calc_activity_ratio)

        result["features"] = (
            result["category"] + " " +
            result["activities"] + " " +
            result["activities"] + " " +
            result["description"]
        )

        activity_text = " ".join(activities) if activities else ""
        user_features = f"{category} {activity_text} {activity_text}"

        documents = [user_features] + result["features"].tolist()

        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf_matrix = vectorizer.fit_transform(documents)

            similarity = cosine_similarity(
                tfidf_matrix[0:1],
                tfidf_matrix[1:]
            )
            result["tfidf_sim"] = similarity.flatten()
        except Exception:
            result["tfidf_sim"] = 0.5

        if user_act_set:
            result["match_score"] = (
                0.55 + 
                (result["activity_ratio"] * 0.35) + 
                (result["tfidf_sim"] * 0.10)
            )
        else:
            result["match_score"] = 0.60 + (result["tfidf_sim"] * 0.40)

        result["match"] = (result["match_score"] * 100).round(1)

        if user_act_set:
            result.loc[(result["activity_ratio"] < 1.0) & (result["match"] > 95.0), "match"] = 92.5

        result["match"] = result["match"].clip(upper=100.0)

        result = result.sort_values(by="match_score", ascending=False)

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
    filter_mismatch_notice = False
    destination_results_exist = False

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
            destination_results_exist = destination_results.exists()

            # If destination not found, try fuzzy suggestion
            if not destination_results_exist:
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
            if destination_results_exist:
                filter_mismatch_notice = True
            else:
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
            "filter_mismatch_notice": filter_mismatch_notice,
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