from rest_framework.test import APITestCase


class DashboardAnonymousTests(APITestCase):
    def test_anonymous_request_gets_401(self):
        response = self.client.get("/api/v1/dashboard/")
        self.assertEqual(response.status_code, 401)
