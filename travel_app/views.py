import os
import pandas as pd
from django.shortcuts import render


def home(request):
    return render(request, "home.html")


def recommendation(request):

    recommendations = []
    message = ""

    if request.method == "POST":

        category = request.POST.get("category")
        activities = request.POST.get("activities")
        region = request.POST.get("region")
        budget = request.POST.get("budget_level")
        duration = request.POST.get("duration")
        tourist = request.POST.get("tourist_type")

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(BASE_DIR, "places.csv")

        df = pd.read_csv(csv_path)

        # -----------------------------
        # Exact Match
        # -----------------------------

        result = df[
            (df["category"] == category) &
            (df["budget_level"] == budget) &
            (df["duration"] == duration)
        ]

        # Region
        if region != "Any Region":
            result = result[result["region"] == region]

        # Tourist Type
        result = result[
            (result["tourist_type"] == tourist) |
            (result["tourist_type"] == "Both")
        ]

        # Activity
        result = result[
            result["activities"].str.contains(
                activities,
                case=False,
                na=False,
                regex=False
            )
        ]

        # ======================================
        # STEP 1
        # Ignore Duration
        # ======================================

        if result.empty:

            message = "No exact match found. Showing similar places."

            result = df[
                (df["category"] == category) &
                (df["budget_level"] == budget)
            ]

            if region != "Any Region":
                result = result[result["region"] == region]

            result = result[
                (result["tourist_type"] == tourist) |
                (result["tourist_type"] == "Both")
            ]

            result = result[
                result["activities"].str.contains(
                    activities,
                    case=False,
                    na=False,
                    regex=False
                )
            ]

        # ======================================
        # STEP 2
        # Ignore Activity
        # ======================================

        if result.empty:

            message = "No exact match found. Activity preference was relaxed."

            result = df[
                (df["category"] == category) &
                (df["budget_level"] == budget)
            ]

            if region != "Any Region":
                result = result[result["region"] == region]

            result = result[
                (result["tourist_type"] == tourist) |
                (result["tourist_type"] == "Both")
            ]

        # ======================================
        # STEP 3
        # Ignore Region
        # ======================================

        if result.empty:

            message = "No exact match found. Showing places from other provinces."

            result = df[
                (df["category"] == category) &
                (df["budget_level"] == budget)
            ]

            result = result[
                (result["tourist_type"] == tourist) |
                (result["tourist_type"] == "Both")
            ]

        # ======================================
        # STEP 4
        # Show same category
        # ======================================

        if result.empty:

            message = "No similar destination found. Showing places from the same category."

            result = df[
                df["category"] == category
            ]

        recommendations = result.to_dict("records")

    return render(
        request,
        "recommendation.html",
        {
            "recommendations": recommendations,
            "message": message
        }
    )