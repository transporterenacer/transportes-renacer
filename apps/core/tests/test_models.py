from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase

from apps.core.models import AuditMixin, TimeStampedModel


class StampModel(AuditMixin):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "core"


class TimeStampedModelTests(TestCase):
    def test_stamps_are_set_on_creation(self):
        obj = StampModel.objects.create(name="x")
        self.assertIsNotNone(obj.created_at)
        self.assertIsNotNone(obj.updated_at)

    def test_updated_at_changes_on_update(self):
        obj = StampModel.objects.create(name="x")
        original = obj.updated_at
        obj.name = "y"
        obj.save()
        obj.refresh_from_db()
        self.assertGreater(obj.updated_at, original)


class AuditMixinTests(TestCase):
    def test_user_stamps_are_recorded(self):
        user = get_user_model().objects.create_user(username="ana")
        obj = StampModel.objects.create(name="x", created_by=user, updated_by=user)
        self.assertEqual(obj.created_by, user)
        self.assertEqual(obj.updated_by, user)
