from django.contrib.auth.views import LoginView


class RedirectAuthenticatedLoginView(LoginView):
    """Login que evita mostrar el formulario (y el chrome/sidebar) a
    usuarios que ya tienen una sesión activa: los redirige a la portada."""

    redirect_authenticated_user = True