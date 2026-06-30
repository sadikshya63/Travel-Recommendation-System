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
            self.stdout.write(
                self.style.ERROR(f"places.csv not found at: {csv_file}")
            )
            return

        Place.objects.all().delete()

        with open(csv_file, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            count = 0

            for row in reader:
                Place.objects.create(
                    place_id=int(row["place_id"]),
                    place_name=row["place_name"],
                    category=row["category"],
                    activities=row["activities"],
                    province=row["province"],
                    duration=row["duration"],
                    budget_level=row["budget_level"],
                    tourist_type=row["tourist_type"],
                    description=row["description"],
                    latitude=Decimal(row["latitude"]),
                    longitude=Decimal(row["longitude"]),
                    image=row["image"],
                )

                count += 1

        self.stdout.write(
            self.style.SUCCESS(f"{count} places imported successfully!")
        )