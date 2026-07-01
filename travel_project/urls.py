from django.contrib import admin
from django.urls import path
from travel_app import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),

    path('recommendation/', views.recommendation, name='recommendation'),
    path('explore/', views.explore, name='explore'),
    path('contact/', views.contact, name='contact'),
    path('place/<int:id>/', views.place_detail, name='place_detail'),
    path('all-places/', views.all_places, name='all_places')
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)