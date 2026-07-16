import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from travel_app.models import Place, Hotspot


class Command(BaseCommand):
    help = "Import hotspots from hotspots.csv"

    def handle(self, *args, **kwargs):

        csv_file = os.path.join(
            settings.BASE_DIR,
            "travel_app",
            "data",
            "hotspots.csv"
        )

        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f"CSV not found: {csv_file}"))
            return

        imported = 0

        with open(csv_file, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                try:
                    place = Place.objects.get(place_id=row["place_id"])

                    Hotspot.objects.create(
                        place=place,
                        hotspot_name=row["hotspot_name"],
                        category=row["category"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        description=row["description"],
                        image=row["image"],
                        google_map=row["google_map"],
                    )

                    imported += 1

                except Place.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Place ID {row["place_id"]} not found.'
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported {imported} hotspots.")
        )