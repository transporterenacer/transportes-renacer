from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.catalogos.models import CargoGenerator, Port


class DashboardViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.client.force_login(self.user)

    def test_inicio_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(response.status_code, 302)

    def test_inicio_renderiza_kpis(self):
        response = self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operaciones activas")
        self.assertContains(response, "Información registrada hasta")

    def test_navbar_tiene_enlaces_a_dashboards(self):
        response = self.client.get(reverse("dashboard:inicio"))
        self.assertContains(response, reverse("dashboard:vencimientos"))
        self.assertContains(response, reverse("dashboard:nomina"))
        self.assertContains(response, reverse("dashboard:operativo"))
        self.assertContains(response, reverse("dashboard:financiero"))
        self.assertContains(response, reverse("dashboard:historial"))

    def test_vencimientos_renderiza(self):
        response = self.client.get(reverse("dashboard:vencimientos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vencimientos")

    def test_nomina_renderiza(self):
        response = self.client.get(reverse("dashboard:nomina"))
        self.assertEqual(response.status_code, 200)

    def test_operativo_renderiza(self):
        response = self.client.get(reverse("dashboard:operativo"))
        self.assertEqual(response.status_code, 200)

    def test_financiero_renderiza(self):
        response = self.client.get(reverse("dashboard:financiero"))
        self.assertEqual(response.status_code, 200)

    def test_historial_renderiza(self):
        response = self.client.get(reverse("dashboard:historial"))
        self.assertEqual(response.status_code, 200)
