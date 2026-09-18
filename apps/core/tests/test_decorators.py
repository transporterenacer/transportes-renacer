from django.contrib.auth.models import Group, User
from django.test import TestCase, RequestFactory

from apps.core.decorators import role_required


class RoleRequiredTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.group = Group.objects.create(name="Jefe Mecánico")
        self.user.groups.add(self.group)

    def _dummy_view(self, request):
        return "ok"

    def test_user_in_group_can_access(self):
        decorated = role_required("Jefe Mecánico")(self._dummy_view)
        request = self.factory.get("/")
        request.user = self.user
        result = decorated(request)
        self.assertEqual(result, "ok")

    def test_user_not_in_group_gets_redirect(self):
        other_user = User.objects.create_user(username="other", password="testpass123")
        decorated = role_required("Jefe Mecánico")(self._dummy_view)
        request = self.factory.get("/")
        request.user = other_user
        result = decorated(request)
        self.assertEqual(result.status_code, 302)

    def test_user_in_multiple_groups(self):
        self.user.groups.add(Group.objects.create(name="Admin"))
        decorated = role_required("Admin", "Jefe Mecánico")(self._dummy_view)
        request = self.factory.get("/")
        request.user = self.user
        result = decorated(request)
        self.assertEqual(result, "ok")
