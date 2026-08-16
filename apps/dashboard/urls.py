from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_inicio, name="inicio"),
    path("vencimientos/", views.dashboard_vencimientos, name="vencimientos"),
    path("nomina/", views.dashboard_nomina, name="nomina"),
    path("operativo/", views.dashboard_operativo, name="operativo"),
    path("financiero/", views.dashboard_financiero, name="financiero"),
    path("historial/", views.dashboard_historial, name="historial"),
    path("gantt/<int:pk>/", views.dashboard_gantt, name="gantt"),
    path("gantt/<int:pk>/datos/", views.gantt_datos, name="gantt_datos"),
]
