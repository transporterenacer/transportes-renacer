from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand


USERS = [
    {"username": "admin", "password": "admin123", "groups": ["Admin"], "first_name": "Admin", "last_name": "Sistema"},
    {"username": "secretaria", "password": "secretaria123", "groups": ["Secretaria"], "first_name": "María", "last_name": "García"},
    {"username": "mecanico", "password": "mecanico123", "groups": ["Jefe Mecánico"], "first_name": "Carlos", "last_name": "Rodríguez"},
    {"username": "gerente", "password": "gerente123", "groups": ["Gerencia"], "first_name": "Ana", "last_name": "López"},
]


class Command(BaseCommand):
    help = "Crea usuarios de prueba para cada rol del sistema."

    def handle(self, *args, **options):
        for data in USERS:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={"first_name": data["first_name"], "last_name": data["last_name"]},
            )
            if created:
                user.set_password(data["password"])
                user.save()
            for group_name in data["groups"]:
                group, _ = Group.objects.get_or_create(name=group_name)
                user.groups.add(group)
            status = "creado" if created else "actualizado"
            self.stdout.write(self.style.SUCCESS(f"Usuario '{data['username']}' {status}"))
