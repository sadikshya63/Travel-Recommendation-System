import os
import csv
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "travel_project.settings")
django.setup()

from travel_app.models import Place, Hotel

csv_file = "travel_app/data/hotels.csv"

with open(csv_file, newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    count = 0

    for row in reader:
        try:
            place = Place.objects.get(place_id=int(row["place_id"]))

            Hotel.objects.update_or_create(
                hotel_id=int(row["hotel_id"]),
                defaults={
                    "place": place,
                    "hotel_name": row["hotel_name"].strip(),
                    "price_range": row["price_range"].strip(),
                    "contact": row["contact"].strip(),
                    "image": row["image"].strip(),
                }
            )

            count += 1

        except Place.DoesNotExist:
            print(f"Place ID {row['place_id']} not found.")

print(f"Successfully imported {count} hotels.")