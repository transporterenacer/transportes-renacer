from django.test import SimpleTestCase
from django.urls import reverse


class TemplateTests(SimpleTestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Iniciar sesión")

    def test_base_template_has_css_tokens(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "tokens.css")
