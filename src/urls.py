from django.urls import path
from . import views

urlpatterns = [
    path('mark_as_read/', views.mark_as_read),
    path('mark_as_unread/', views.mark_as_unread),
    path('move_email/', views.move_email),
]
