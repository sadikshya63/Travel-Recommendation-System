import csv
from django.core.management.base import BaseCommand
from travel_app.models import Place, Hotel


class Command(BaseCommand):
    help = "Import hotels from CSV"

    def handle(self, *args, **kwargs):
        csv_file = "travel_app/data/hotels.csv"
        count = 0

        with open(csv_file, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                try:
                    place = Place.objects.get(place_id=int(row["place_id"]))

                    Hotel.objects.update_or_create(
                        hotel_id=int(row["hotel_id"]),
                        defaults={
                            "place": place,
                            "hotel_name": row["hotel_name"].strip(),
                            "price_range": row["price_range"].strip(),
                            "rating": float(row["rating"]),
                            "contact": row["contact"].strip(),
                            "image": row["image"].strip(),
                        },
                    )

                    count += 1

                except Place.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Place ID {row['place_id']} not found."
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported {count} hotels.")
        )