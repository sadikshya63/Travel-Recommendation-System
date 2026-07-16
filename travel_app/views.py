import pandas as pd
import requests

from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Case, When, Value, IntegerField

from rapidfuzz import process, fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .utils import haversine
from .models import Place, EmergencyContact, FAQ, Hotel, RecommendationHistory,VisitorCounter, Hotspot

# =========================
# HOME
# =========================
def home(request):
    places = Place.objects.filter(
        featured=True,
        is_active=True
    )
    counter, created = VisitorCounter.objects.get_or_create(pk=1)
    counter.total_visits += 1
    counter.save()

    places = Place.objects.filter(is_active=True)[:6]

    return render(request, "home.html", {
        "places": places
    })

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
            place.latitude,
            place.longitude,
            hotspot.latitude,
            hotspot.longitude
        )

    # Sort by nearest hotspot
    hotspots = sorted(
        hotspots,
        key=lambda x: x.distance
    )

    # Show only first 8
    hotspots = hotspots[:8]

    return render(request, "place_details.html", {
        "place": place,
        "hotels": hotels,
        "weather": weather_data,
        "alert": alert,
        "hotspots": hotspots,
    })


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
    tourist = ""

    # Dynamic dropdown data
    categories = Place.objects.values_list(
        "category",
        flat=True
    ).distinct()

    provinces = Place.objects.values_list(
        "province",
        flat=True
    ).distinct()

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
        tourist = request.POST.get("tourist_type")

        # Validate required category
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
            "selected_tourist": tourist,
        }
        )
 
        # Save recommendation history
        RecommendationHistory.objects.create(
            category=category,
            activities=", ".join(activities),
            province=province,
            budget_level=budget,
            duration=duration,
            tourist_type=tourist,
        )

        # Load database into dataframe
        data = []

        for p in Place.objects.all():
            data.append({
                "place_id": p.place_id,
                "place_name": p.place_name,
                "category": p.category,
                "activities": p.activities,
                "province": p.province,
                "budget_level": p.budget_level,
                "duration": p.duration,
                "tourist_type": p.tourist_type,
                "description": p.description,
                "image": p.image,
            })

        df = pd.DataFrame(data).fillna("")

        result = df.copy()

        # -------------------------
        # Rule-Based Filtering
        # -------------------------

        # Category
        result = result[
            result["category"].str.lower() == category.lower()
        ]
        category_result = result.copy()

        # Province
        if province and province != "Any Province":
            result = result[
                result["province"].str.lower() == province.lower()
            ]
        if result.empty:
         message = "No place found in this province. Showing all places from selected category."
         result = category_result.copy()
        province_result = result.copy()
        # Budget
        if budget:
            result = result[
                result["budget_level"].str.lower() == budget.lower()
            ]
        if result.empty:
         message = " No place matched your selected budget. Showing the closest destinations."
         result = province_result.copy()
         
        budget_result = result.copy()
        # Duration
        if duration:

    # Extract minimum and maximum days
          numbers = result["duration"].str.extract(r"(\d+)(?:-(\d+))?")

          min_days = numbers[0].astype(int)

    
          max_days = numbers[1].fillna(numbers[0]).astype(int)

          if duration == "1-3 Days":
           result = result[(min_days <= 3)]

          elif duration == "4-6 Days":
           result = result[(max_days >= 4) & (min_days <= 6)]

          elif duration == "7-9 Days":
           result = result[(max_days >= 7) & (min_days <= 9)]

          elif duration == "10+ Days":
           result = result[(max_days >= 10)]
 
          if result.empty:
           message = "No place matched your selected duration. Showing similar destinations."
           result = budget_result.copy()

        duration_result = result.copy()
        
        
            
        # Tourist Type
        if tourist:
            result = result[
                (result["tourist_type"].str.lower() == tourist.lower()) |
                (result["tourist_type"].str.lower() == "both")
            ]
            if result.empty:
             message = "Tourist type relaxed."
             result = duration_result.copy()

        # Save filtered result before activity filtering
        filtered_places = result.copy()

        # -------------------------
        # Activity Filter
        # -------------------------

        if activities:

            pattern = "|".join(activities)

            activity_result = result[
                result["activities"].str.contains(
                    pattern,
                    case=False,
                    na=False,
                    regex=True
                )
            ]

            if not activity_result.empty:
                result = activity_result

            else:
                message = (
                    "No destination has the selected activity. "
                    "Showing similar destinations based on your other preferences."
                )
                result = filtered_places
                        # -------------------------
        # No place after rule-based filtering
        # -------------------------

        if result.empty:

            message = "No destination matches your selected preferences."

        else:

            # -------------------------
            # TF-IDF Feature Construction
            # -------------------------

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
                f"{category} "
                f"{activity_text} "
                f"{province} "
                f"{budget} "
                f"{duration} "
                f"{tourist}"
            )

            documents = [user_features] + result["features"].tolist()

            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf_matrix = vectorizer.fit_transform(documents)

            similarity = cosine_similarity(
                tfidf_matrix[0:1],
                tfidf_matrix[1:]
            )

            result["similarity"] = similarity.flatten()

            result["match"] = (
                result["similarity"] * 100
            ).round().astype(int)

            result = result.sort_values(
                by="similarity",
                ascending=False
            )

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
           "selected_tourist": tourist,
        }
    )
                
from django.http import JsonResponse

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

    featured_places = Place.objects.filter(
    featured=True,
    is_active=True
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

    places = Place.objects.filter(is_active=True)

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

    places = Place.objects.filter(
        category__iexact=category,
        is_active=True
    )

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
    




    
