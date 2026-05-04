from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register("configs", api_views.GeneratedConfigViewSet)

urlpatterns = router.urls
