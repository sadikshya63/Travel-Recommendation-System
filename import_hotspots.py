import csv
from travel_app.models import Place, Hotspot

with open("travel_app/data/hotspots.csv", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        place = Place.objects.get(place_id=row["place_id"])

        Hotspot.objects.create(
            place=place,
            hotspot_name=row["hotspot_name"],
            category=row["category"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            description=row["description"],
            image=row["image"],
            google_map=row["google_map"],
        )

print("Hotspots imported successfully!")