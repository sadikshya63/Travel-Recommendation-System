from django.shortcuts import render
from django.contrib import messages
from django.db.models import Q, Case, When, Value, IntegerField
from django.http import JsonResponse
from rapidfuzz import process, fuzz

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
    return render(request, "recommendation.html")


# =========================
# EXPLORE (SMART SEARCH)
# =========================
def explore(request):

    search = request.GET.get("search", "").strip()
    categories = request.GET.getlist("category")
    activities = request.GET.getlist("activity")

    suggestion = None
    filter_notice = False

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

        # ====================================================
        # SEARCH MODE
        # ====================================================
        if search:

            featured_places = Place.objects.filter(

                Q(place_name__icontains=search) |
                Q(category__icontains=search) |
                Q(province__icontains=search) |
                Q(activities__icontains=search)

            )

            # -------------------------------
            # Nothing found -> Fuzzy Suggestion
            # -------------------------------
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

                # -------------------------------
                # Relevance Ranking
                # -------------------------------
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
                        output_field=IntegerField()

                    )

                ).order_by("-relevance")

                # ----------------------------------------
                # OPTIONAL CATEGORY BOOST
                # (does NOT remove destinations)
                # ----------------------------------------
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
                            output_field=IntegerField()

                        )

                    ).order_by(
                        "-category_boost",
                        "-relevance"
                    )

                # ----------------------------------------
                # OPTIONAL ACTIVITY BOOST
                # (does NOT remove destinations)
                # ----------------------------------------
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
                            output_field=IntegerField()

                        )

                    ).order_by(
                        "-activity_boost",
                        "-category_boost",
                        "-relevance"
                    )
                   
                                   # ----------------------------------------
                # FILTER NOTICE
                # ----------------------------------------

                top_place = featured_places.first()

                if top_place:

                    category_mismatch = False
                    activity_mismatch = False

                    if categories:
                        category_mismatch = top_place.category not in categories

                    if activities:

                        place_activities = [
                            activity.strip()
                            for activity in top_place.activities.split(",")
                        ]

                        activity_mismatch = any(
                            activity not in place_activities
                            for activity in activities
                        )

                    if category_mismatch or activity_mismatch:
                        filter_notice = True

    return render(
        request,
        "explore.html",
        {
            "featured_places": featured_places,
            "search": search,
            "selected_categories": categories,
            "selected_activities": activities,
            "suggestion": suggestion,
            "filter_notice": filter_notice,
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

            Q(place_name__icontains=search) |
            Q(category__icontains=search) |
            Q(province__icontains=search) |
            Q(activities__icontains=search)

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
                output_field=IntegerField()

            )

        ).order_by("-relevance")

        # Fuzzy suggestion if nothing found
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
        }
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

        Q(place_name__icontains=query) |
        Q(category__icontains=query) |
        Q(province__icontains=query) |
        Q(activities__icontains=query)

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
            output_field=IntegerField()

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

        safe=False

    )
