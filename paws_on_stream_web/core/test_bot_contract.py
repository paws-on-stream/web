from django.test import TestCase
from rest_framework.test import APIClient


class HealthEndpointContractTest(TestCase):
    def test_health_endpoint_is_public(self):
        response = APIClient().get("/api/v1/health/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["db_reachable"] is True
