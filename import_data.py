import csv
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "travel_project.settings")
django.setup()

from travel_app.models import Place

with open("travel_app/data/places.csv", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        Place.objects.create(
            place_id=row["place_id"],
            place_name=row["place_name"],
            city=row["city"],
            category=row["category"],
            activities=row["activities"],
            province=row["province"],
            duration=row["duration"],
            budget_level=row["budget_level"],
            tourist_type=row["tourist_type"],
            description=row["description"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            image=row["image"],
        )

print("Data imported successfully!")