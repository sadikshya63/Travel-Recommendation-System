import csv
from travel_app.models import Place

with open('places.csv', newline='', encoding='utf-8') as file:
    reader = csv.DictReader(file)

    for row in reader:
        Place.objects.create(
            place_id=row['place_id'],
            place_name=row['place_name'],
            category=row['category'],
            activities=row['activities'],
            province=row['province'],
            duration=row['duration'],
            budget_level=row['budget_level'],
            tourist_type=row['tourist_type'],
            description=row['description'],
            latitude=row['latitude'],
            longitude=row['longitude'],
            image=row['image']
        )