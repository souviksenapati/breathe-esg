"""
URL configuration for config project.
"""

import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView


def serve_react(request):
    """
    Catch-all: serve the React index.html for any path not matched by the API.
    This lets React Router handle client-side navigation.
    """
    index_path = os.path.join(settings.STATIC_ROOT, "frontend", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "rb") as f:
            return HttpResponse(f.read(), content_type="text/html")
    # Fallback during development when frontend hasn't been built yet
    return HttpResponse(
        "<h1>Breathe ESG API</h1>"
        "<p>Frontend not built. Run <code>npm run build</code> in the <code>frontend/</code> directory.</p>"
        "<p><a href='/api/'>Browse the API →</a></p>"
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    # Serve React for all other paths
    path("", serve_react),
    path("<path:path>", serve_react),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
