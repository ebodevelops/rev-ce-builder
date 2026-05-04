from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register("vendors", api_views.VendorViewSet)
router.register("device-models", api_views.DeviceModelViewSet)
router.register("sites", api_views.SiteViewSet)
router.register("scenarios", api_views.DeploymentScenarioViewSet)
router.register("devices", api_views.DeviceViewSet)

urlpatterns = router.urls
