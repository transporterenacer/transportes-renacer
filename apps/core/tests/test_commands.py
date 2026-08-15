from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase


class SetupGroupsTests(TestCase):
    def test_groups_are_created(self):
        call_command("setup_groups")
        names = set(Group.objects.values_list("name", flat=True))
        self.assertEqual(names, {"Admin", "Secretaria", "Gerencia"})

    def test_command_is_idempotent(self):
        call_command("setup_groups")
        call_command("setup_groups")
        self.assertEqual(Group.objects.count(), 3)
