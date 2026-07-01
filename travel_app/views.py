import os
import pandas as pd

from django.shortcuts import render
from django.contrib import messages
from django.db.models import Q, Case, When, Value, IntegerField
from django.http import JsonResponse

from rapidfuzz import process, fuzz

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Place


# =========================
# HOME
# =========================
def home(request):
    return render(request, "home.html")


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

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(
            BASE_DIR,
            "travel_app",
            "data",
            "places.csv",
        )

        df = pd.read_csv(csv_path)

        df.columns = df.columns.str.strip()
        df = df.fillna("")

        result = df.copy()

        # -------------------------
        # Category
        # -------------------------

        if category:
            result = result[
                result["category"].str.lower() == category.lower()
            ]

        # -------------------------
        # Province
        # -------------------------

        if province and province != "Any Province":
            result = result[
                result["province"].str.lower() == province.lower()
            ]

        # -------------------------
        # Budget
        # -------------------------

        if budget:
            result = result[
                result["budget_level"].str.lower() == budget.lower()
            ]

        # -------------------------
        # Duration
        # -------------------------

        if duration:

            numbers = result["duration"].str.extract(
                r"(\d+)(?:-(\d+))?"
            )

            min_days = numbers[0].astype(int)
            max_days = numbers[1].fillna(numbers[0]).astype(int)

            if duration == "1-3 Days":
                result = result[max_days <= 3]

            elif duration == "4-6 Days":
                result = result[
                    (max_days >= 4)
                    & (min_days <= 6)
                ]

            elif duration == "7-9 Days":
                result = result[
                    (max_days >= 7)
                    & (min_days <= 9)
                ]

            elif duration == "10+ Days":
                result = result[
                    max_days >= 10
                ]

        # -------------------------
        # Tourist Type
        # -------------------------

        if tourist:
            result = result[
                (
                    result["tourist_type"]
                    .str.lower() == tourist.lower()
                )
                |
                (
                    result["tourist_type"]
                    .str.lower() == "both"
                )
            ]

        # -------------------------
        # Activities
        # -------------------------

        if activities:

            pattern = "|".join(activities)

            activity_result = result[
                result["activities"].str.contains(
                    pattern,
                    case=False,
                    na=False,
                    regex=True,
                )
            ]

            if not activity_result.empty:
                result = activity_result
            else:
                message = (
                    "Exact activities not found. "
                    "Showing similar destinations."
                )

        # -------------------------
        # No Result
        # -------------------------

        if result.empty:

            message = (
                "No exact destination found. "
                "Showing similar destinations."
            )

            result = df.copy()

            if category:
                result = result[
                    result["category"].str.lower()
                    == category.lower()
                ]

        # -------------------------
        # Similarity
        # -------------------------

        result = result.copy()

        result["features"] = (

            result["category"] + " " +
            result["activities"] + " " +
            result["province"] + " " +
            result["budget_level"] + " " +
            result["duration"] + " " +
            result["tourist_type"]

        )

        activity_text = " ".join(activities)

        user_features = (
            f"{category} "
            f"{activity_text} "
            f"{province} "
            f"{budget} "
            f"{duration} "
            f"{tourist}"
        )

        documents = [
            user_features
        ] + result["features"].tolist()

        vectorizer = TfidfVectorizer()

        tfidf = vectorizer.fit_transform(documents)

        similarity = cosine_similarity(
            tfidf[0:1],
            tfidf[1:]
        )

        result["similarity"] = similarity.flatten()

        result["match"] = (
            result["similarity"] * 100
        ).round().astype(int)

        result = result.sort_values(
            by="similarity",
            ascending=False
        )

        for index, row in result.iterrows():

            reasons = []

            if (
                category and
                row["category"].lower() == category.lower()
            ):
                reasons.append("Category Match")

            if (
                budget and
                row["budget_level"].lower() == budget.lower()
            ):
                reasons.append("Budget Match")

            if (
                province and
                province != "Any Province"
                and
                row["province"].lower() == province.lower()
            ):
                reasons.append("Province Match")

            result.at[index, "reason"] = ", ".join(reasons)

        recommendations = result.head(5).to_dict("records")

    return render(
        request,
        "recommendation.html",
        {
            "recommendations": recommendations,
            "message": message,
        },
    )
    # =========================
# EXPLORE (SMART SEARCH)
# =========================
def explore(request):

    search = request.GET.get("search", "").strip()
    categories = request.GET.getlist("category")
    activities = request.GET.getlist("activity")

    suggestion = None

    # Default featured places
    featured_places = Place.objects.filter(
        place_id__in=[1, 4, 8, 13, 15, 16]
    )

    # Empty search
    if (
        "search_btn" in request.GET
        and not search
        and not categories
        and not activities
    ):
        messages.warning(
            request,
            "Please enter a destination or select at least one category or activity."
        )

    elif search or categories or activities:

        # -----------------------------
        # SEARCH MODE
        # -----------------------------
        if search:

            featured_places = Place.objects.filter(
                Q(place_name__icontains=search)
                | Q(category__icontains=search)
                | Q(province__icontains=search)
                | Q(activities__icontains=search)
            )

            # Fuzzy suggestion
            if not featured_places.exists():

                place_names = list(
                    Place.objects.values_list(
                        "place_name",
                        flat=True
                    )
                )

                match = process.extractOne(
                    search,
                    place_names,
                    scorer=fuzz.WRatio
                )

                if match and match[1] >= 60:
                    suggestion = match[0]
                else:
                    messages.info(
                        request,
                        "No destinations found. Please try another search."
                    )

            else:

                featured_places = featured_places.annotate(

                    relevance=Case(

                        When(
                            place_name__icontains=search,
                            then=Value(4)
                        ),

                        When(
                            activities__icontains=search,
                            then=Value(3)
                        ),

                        When(
                            category__icontains=search,
                            then=Value(2)
                        ),

                        When(
                            province__icontains=search,
                            then=Value(1)
                        ),

                        default=Value(0),
                        output_field=IntegerField(),

                    )

                ).order_by("-relevance")

                # Category boost
                if categories:

                    featured_places = featured_places.annotate(

                        category_boost=Case(

                            *[
                                When(
                                    category=category,
                                    then=Value(1)
                                )
                                for category in categories
                            ],

                            default=Value(0),
                            output_field=IntegerField(),

                        )

                    ).order_by(
                        "-category_boost",
                        "-relevance",
                    )

                # Activity boost
                if activities:

                    activity_cases = [

                        When(
                            activities__icontains=activity,
                            then=Value(1)
                        )

                        for activity in activities

                    ]

                    featured_places = featured_places.annotate(

                        activity_boost=Case(

                            *activity_cases,

                            default=Value(0),
                            output_field=IntegerField(),

                        )

                    ).order_by(
                        "-activity_boost",
                        "-category_boost",
                        "-relevance",
                    )

        # -----------------------------
        # FILTER MODE
        # -----------------------------
        else:

            featured_places = Place.objects.all()

            if categories:

                featured_places = featured_places.filter(
                    category__in=categories
                )

            if activities:

                activity_query = Q()

                for activity in activities:
                    activity_query |= Q(
                        activities__icontains=activity
                    )

                featured_places = featured_places.filter(
                    activity_query
                )

    return render(
        request,
        "explore.html",
        {
            "featured_places": featured_places,
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

    places = Place.objects.all()

    if search:

        places = places.filter(

            Q(place_name__icontains=search)
            | Q(category__icontains=search)
            | Q(province__icontains=search)
            | Q(activities__icontains=search)

        ).annotate(

            relevance=Case(

                When(
                    place_name__icontains=search,
                    then=Value(4)
                ),

                When(
                    activities__icontains=search,
                    then=Value(3)
                ),

                When(
                    category__icontains=search,
                    then=Value(2)
                ),

                When(
                    province__icontains=search,
                    then=Value(1)
                ),

                default=Value(0),
                output_field=IntegerField(),

            )

        ).order_by("-relevance")

        if not places.exists():

            place_names = list(
                Place.objects.values_list(
                    "place_name",
                    flat=True
                )
            )

            match = process.extractOne(
                search,
                place_names,
                scorer=fuzz.WRatio
            )

            if match and match[1] >= 60:

                messages.info(
                    request,
                    f'No exact destination found. Did you mean "{match[0]}"?'
                )

            else:

                messages.warning(
                    request,
                    "No destinations found."
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
        | Q(category__icontains=query)
        | Q(province__icontains=query)
        | Q(activities__icontains=query)

    ).annotate(

        relevance=Case(

            When(
                place_name__icontains=query,
                then=Value(4)
            ),

            When(
                activities__icontains=query,
                then=Value(3)
            ),

            When(
                category__icontains=query,
                then=Value(2)
            ),

            When(
                province__icontains=query,
                then=Value(1)
            ),

            default=Value(0),
            output_field=IntegerField(),

        )

    ).order_by("-relevance")[:8]

    return JsonResponse(

        [
            {
                "name": place.place_name,
                "province": place.province,
                "category": place.category,
            }
            for place in places
        ],

        safe=False,

    )