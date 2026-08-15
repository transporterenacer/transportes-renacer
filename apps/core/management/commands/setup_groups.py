from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

GROUPS = {
    "Admin": {"__all__"},
    "Secretaria": {"__all__"},
    "Gerencia": {"view_all"},
}


class Command(BaseCommand):
    help = "Crea o actualiza los grupos de usuarios del sistema."

    def handle(self, *args, **options):
        for name, perms in GROUPS.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.all())
            self.stdout.write(self.style.SUCCESS(f"Grupo '{name}' listo"))
