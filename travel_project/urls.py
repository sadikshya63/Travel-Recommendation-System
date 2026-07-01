from django.contrib import admin
from django.urls import path
from travel_app import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.home, name='home'),
    path('recommendation/', views.recommendation, name='recommendation'),
    path('explore/', views.explore, name='explore'),
    path('contact/', views.contact, name='contact'),
    path('places/', views.all_places, name='all_places'),

    # LIVE SEARCH
    path('search-suggestions/', views.search_suggestions, name='search_suggestions'),

    # ✅ FIXED: DETAIL PAGE (IMPORTANT)
    path('place/<int:place_id>/', views.place_detail, name='place_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)