from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect


def role_required(*group_names):
    """
    Decorator that checks user belongs to at least one of the specified groups.
    Usage: @role_required("Admin", "Jefe Mecánico")
    """
    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            if not request.user.groups.filter(name__in=group_names).exists():
                messages.error(request, "No tienes permiso para acceder a esta sección.", fail_silently=True)
                return redirect("dashboard:inicio")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
