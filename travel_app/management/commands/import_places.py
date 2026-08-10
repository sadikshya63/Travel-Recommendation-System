import csv
import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from travel_app.models import Place

class Command(BaseCommand):
    help = "Import places from places.csv"

    def handle(self, *args, **kwargs):
        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )
        )

        csv_file = os.path.join(base_dir, "data", "places.csv")

        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f"places.csv not found at: {csv_file}"))
            return

        count = 0

        # utf-8-sig removes Byte Order Mark (BOM) automatically
        with open(csv_file, newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:
                place_id_val = int(row["place_id"].strip())
                Place.objects.update_or_create(
                    place_id=place_id_val,
                    defaults={
                        "place_name": row["place_name"].strip(),
                        "category": row["category"].strip(),
                        "city": row["city"].strip(),
                        "activities": row["activities"].strip(),
                        "province": row["province"].strip(),
                        "duration": row["duration"].strip(),
                        "budget_level": row["budget_level"].strip(),
                        "tourist_type": row.get("tourist_type", "Both").strip(),
                        "description": row["description"].strip(),
                        "latitude": Decimal(row["latitude"].strip()),
                        "longitude": Decimal(row["longitude"].strip()),
                        "image": row["image"].strip(),
                        "featured": place_id_val in [5, 18, 26, 28, 35, 43],
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"{count} places imported successfully!"))