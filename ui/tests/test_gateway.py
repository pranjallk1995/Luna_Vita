import unittest
from io import BytesIO

import httpx
from PIL import Image
from starlette.testclient import TestClient

from config import SSOConfig, UIConfig
from gateway import UIGateway

OWNER = {"user_id": "owner", "email": "owner@example.com", "email_verified": True}
STRANGER = {"user_id": "stranger", "email": "other@example.com", "email_verified": True}
PHOTO = "https://visia.example.com/api/public/images/12345678-1234-1234-1234-123456789012"


def png() -> bytes:
    data = BytesIO()
    Image.new("RGB", (64, 32), "red").save(data, "PNG")
    return data.getvalue()


class GatewayTestCase(unittest.TestCase):
    def setUp(self):
        self.backend_requests: list[httpx.Request] = []
        self.visia_requests: list[httpx.Request] = []
        self.visia_up = True

        def sso(request: httpx.Request) -> httpx.Response:
            session = {"owner": OWNER, "stranger": STRANGER}.get(request.headers["X-Luna-Session"])
            return httpx.Response(200, json=session) if session else httpx.Response(401)

        def backend(request: httpx.Request) -> httpx.Response:
            self.backend_requests.append(request)
            if request.url.path.startswith("/api/reports/"):
                return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
            if request.method == "DELETE":
                return httpx.Response(204)
            return httpx.Response(200, json={"status": "ok"})

        def visia(request: httpx.Request) -> httpx.Response:
            self.visia_requests.append(request)
            return httpx.Response(200, content=png()) if self.visia_up else httpx.Response(503)

        config = UIConfig(
            api_url="http://backend",
            api_token="t" * 32,
            allowed_emails=frozenset({"owner@example.com"}),
            sso=SSOConfig(public_url="https://auth.example.com"),
        )
        gateway = UIGateway(config, httpx.MockTransport(backend), httpx.MockTransport(sso), httpx.MockTransport(visia))
        self.client = TestClient(gateway.application(), base_url="https://vita.example.com")

    def sign_in(self, who: str = "owner") -> None:
        self.client.cookies.set(SSOConfig.COOKIE_NAME, who)


class AccessTests(GatewayTestCase):
    def test_every_data_route_needs_an_allowed_session(self):
        for path in ("/api/recommendations", "/api/food", "/api/reports/daily/2026-01-01", "/app/food-photos"):
            self.client.cookies.clear()
            self.assertEqual(self.client.get(path).status_code, 401, path)
            self.sign_in("stranger")
            self.assertEqual(self.client.get(path).status_code, 403, path)
        self.assertEqual(self.backend_requests, [])

    def test_settings_reach_the_browser(self):
        self.sign_in()
        settings = self.client.get("/auth/session").json()["settings"]
        self.assertEqual(settings["time_zone"], UIConfig.TIME_ZONE)
        self.assertEqual(settings["food_photo_size"], list(UIConfig.FOOD_PHOTO_SIZE))


class ProxyTests(GatewayTestCase):
    def test_everything_the_ui_does_is_forwarded(self):
        self.sign_in()
        for method, path in (
            ("GET", "/api/summary/2026-01-01"),
            ("GET", "/api/food?start=2026-01-01&end=2026-01-01&limit=500"),
            ("POST", "/api/food"),
            ("PUT", "/api/food/3"),
            ("GET", "/api/analysis/displayed?day=2026-01-01"),
            ("PUT", "/api/analysis/range"),
            ("GET", "/api/measurements?limit=500"),
            ("POST", "/api/measurements/batch"),
            ("GET", "/api/body-composition?start=2026-01-01&end=2026-01-31"),
            ("GET", "/api/workouts?start=2026-01-01&end=2026-01-31"),
            ("PUT", "/api/workouts/2026-01-01"),
            ("GET", "/api/workouts/exercises?start=2026-01-01&end=2026-01-01"),
            ("POST", "/api/workouts/exercises"),
            ("PUT", "/api/workouts/exercises/9"),
        ):
            self.assertEqual(self.client.request(method, path).status_code, 200, path)

    def test_deleting_passes_the_empty_answer_through(self):
        self.sign_in()
        for path in ("/api/food/3", "/api/measurements/4", "/api/workouts/2026-01-01", "/api/workouts/exercises/9", "/api/analysis/range"):
            self.assertEqual(self.client.delete(path).status_code, 204, path)

    def test_query_reaches_the_backend(self):
        self.sign_in()
        self.client.get("/api/analysis/displayed?day=2026-01-15")
        self.assertEqual(self.backend_requests[0].url.params["day"], "2026-01-15")

    def test_report_keeps_its_type(self):
        self.sign_in()
        response = self.client.get("/api/reports/daily/2026-01-01")
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.content, b"%PDF")

    def test_routes_the_ui_does_not_use_are_not_forwarded(self):
        self.sign_in()
        for method, path in (
            ("GET", "/api/analysis"),
            ("PUT", "/api/days/2026-01-01"),
            ("PUT", "/api/measurements/3"),
            ("GET", "/api/workouts/summary"),
            ("PUT", "/api/workouts/not-a-day"),
        ):
            self.assertEqual(self.client.request(method, path).status_code, 404, path)
        self.assertEqual(self.backend_requests, [])


class FoodPhotoTests(GatewayTestCase):
    def test_visia_photo_is_fitted_and_fetched_once_on_the_private_network(self):
        self.sign_in()
        for _ in range(2):
            response = self.client.get("/app/food-photos", params={"url": PHOTO})
            self.assertEqual((response.status_code, response.headers["content-type"]), (200, "image/webp"))
        self.assertEqual(len(self.visia_requests), 1)
        self.assertEqual(self.visia_requests[0].url.host, "luna-visia-mcp")
        with Image.open(BytesIO(response.content)) as image:
            self.assertEqual(image.size, UIConfig.FOOD_PHOTO_SIZE)

    def test_large_photo_keeps_the_whole_image_and_never_enlarges_it(self):
        self.sign_in()
        table = self.client.get("/app/food-photos", params={"url": PHOTO})
        response = self.client.get("/app/food-photos", params={"url": PHOTO, "size": "large"})
        self.assertEqual((response.status_code, response.headers["content-type"]), (200, "image/webp"))
        self.assertNotEqual(response.content, table.content)
        with Image.open(BytesIO(response.content)) as image:
            self.assertEqual(image.size, (64, 32))

    def test_other_addresses_are_never_fetched(self):
        self.sign_in()
        response = self.client.get("/app/food-photos", params={"url": "http://169.254.169.254/latest"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.visia_requests, [])

    def test_visia_away_is_a_plain_miss_that_is_not_remembered(self):
        self.sign_in()
        self.visia_up = False
        self.assertEqual(self.client.get("/app/food-photos", params={"url": PHOTO}).status_code, 404)
        self.visia_up = True
        self.assertEqual(self.client.get("/app/food-photos", params={"url": PHOTO}).status_code, 200)


class ApplicationTests(GatewayTestCase):
    def test_health_needs_no_session_on_both_paths(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/_stcore/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
