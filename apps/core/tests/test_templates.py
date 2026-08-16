from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class TemplateTests(SimpleTestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Iniciar sesión")

    def test_base_template_has_css_tokens(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "tokens.css")


class InicioPageTests(TestCase):
    def test_inicio_page_renders(self):
        User.objects.create_user(username="ana", password="x")
        self.client.force_login(User.objects.get(username="ana"))
        response = self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel de control")
