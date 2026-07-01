import os
import pandas as pd
from django.shortcuts import render
from .models import Place

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def home(request):
    return render(request, "home.html")


def recommendation(request):

    recommendations = []
    message = ""

    if request.method == "POST":

        # ==========================
        # USER INPUT
        # ==========================

        category = request.POST.get("category")
        activities = request.POST.getlist("activities")
        province = request.POST.get("province")
        budget = request.POST.get("budget_level")
        duration = request.POST.get("duration")
        tourist = request.POST.get("tourist_type")

        # ==========================
        # LOAD CSV
        # ==========================

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(BASE_DIR, "travel_app", "data", "places.csv")

        df = pd.read_csv(csv_path)

        df.columns = df.columns.str.strip()
        df = df.fillna("")

        result = df.copy()

        # ==========================
        # CATEGORY FILTER
        # ==========================

        if category:
            result = result[
                result["category"].str.lower() == category.lower()
            ]

        # ==========================
        # PROVINCE FILTER
        # ==========================

        if province and province != "Any Province":
            result = result[
                result["province"].str.lower() == province.lower()
            ]

        # ==========================
        # BUDGET FILTER
        # ==========================

        if budget:
            result = result[
                result["budget_level"].str.lower() == budget.lower()
            ]

        # ==========================
        # DURATION FILTER
        # ==========================

        if duration:

            numbers = result["duration"].str.extract(r'(\d+)(?:-(\d+))?')

            min_days = numbers[0].astype(int)
            max_days = numbers[1].fillna(numbers[0]).astype(int)

            if duration == "1-3 Days":
                result = result[max_days <= 3]

            elif duration == "4-6 Days":
                result = result[
                    (max_days >= 4) &
                    (min_days <= 6)
                ]

            elif duration == "7-9 Days":
                result = result[
                    (max_days >= 7) &
                    (min_days <= 9)
                ]

            elif duration == "10+ Days":
                result = result[max_days >= 10]

        # ==========================
        # TOURIST FILTER
        # ==========================

        if tourist:
            result = result[
                (result["tourist_type"].str.lower() == tourist.lower()) |
                (result["tourist_type"].str.lower() == "both")
            ]

        # ==========================
        # ACTIVITIES FILTER
        # ==========================

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
                message = "Exact activities not found. Showing similar destinations."

        # ==========================
        # IF NOTHING FOUND
        # ==========================

        if result.empty:

            message = "No exact destination found. Showing similar destinations."

            result = df.copy()

            if category:
                result = result[
                    result["category"].str.lower() == category.lower()
                ]

        # ==========================
        # CREATE FEATURES
        # ==========================

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

        documents = [user_features] + result["features"].tolist()

        vectorizer = TfidfVectorizer()

        tfidf = vectorizer.fit_transform(documents)
        similarity = cosine_similarity(
         tfidf[0:1],
         tfidf[1:]
)
        result["similarity"] = similarity.flatten()
        result["match"] = (result["similarity"] * 100).round().astype(int)

        result = result.sort_values(
        by="similarity",
        ascending=False)
        for index, row in result.iterrows():

         reasons = []

         if row["category"].lower() == category.lower():
          reasons.append("Category Match")

         if budget and row["budget_level"].lower() == budget.lower():
           reasons.append("Budget Match")

         if province != "Any Province" and row["province"].lower() == province.lower():
          reasons.append("Province Match")

         result.at[index, "reason"] = ", ".join(reasons)

        recommendations = result.head(5).to_dict("records")
        

    return render(
        request,
        "recommendation.html",
        {
            "recommendations": recommendations,
            "message": message
        }
    )


def explore(request):
    featured_places = Place.objects.filter(
        place_id__in=[1, 4, 8, 13, 15, 16]
    )
    return render(
        request,
        "explore.html",
        {
            "featured_places": featured_places
        }
    )


def contact(request):
    return render(request, "contact.html")


def all_places(request):
    places = Place.objects.all()
    return render(
        request,
        "all_places.html",
        {
            "places": places
        }
    )