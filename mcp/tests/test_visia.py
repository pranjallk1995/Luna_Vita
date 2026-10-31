"""Tests for verifying food images against the Luna Visia catalog."""

import unittest
from unittest.mock import patch

import httpx

from app.core.errors import NotFoundError
from app.integrations.visia import VisiaImageCatalog, VisiaUnavailableError

IMAGE_ID = "2d77a066-d097-4b1b-9682-c9eb41538b26"
HIDDEN_ID = "11111111-2222-3333-4444-555555555555"
PLACEHOLDER_ID = "b7adf6ae-30b3-4750-8381-5dc6ab393de6"
PUBLIC = "https://visia.example/api/public/images/"
CATALOG = {
    "images": [
        {"image_id": IMAGE_ID, "public_url": PUBLIC + IMAGE_ID, "hidden": False},
        {"image_id": HIDDEN_ID, "public_url": PUBLIC + HIDDEN_ID, "hidden": True},
        {"image_id": PLACEHOLDER_ID, "public_url": PUBLIC + PLACEHOLDER_ID, "hidden": False},
    ]
}


def respond(payload=CATALOG, status=200):
    request = httpx.Request("GET", "http://visia/api/metadata")
    return httpx.Response(status, json=payload, request=request)


class VisiaImageCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = VisiaImageCatalog("http://visia/", PLACEHOLDER_ID.upper())

    def test_image_id_accepts_only_image_id_urls(self) -> None:
        self.assertEqual(VisiaImageCatalog.image_id(PUBLIC + IMAGE_ID.upper()), IMAGE_ID)
        for bad in (
            "data:image/jpeg;base64,AAAA",
            PUBLIC + "Paratha.png",
            "https://visia.example/images/" + IMAGE_ID,
            IMAGE_ID,
            "ftp://visia.example/api/public/images/" + IMAGE_ID,
        ):
            with self.subTest(url=bad):
                with self.assertRaises(ValueError):
                    VisiaImageCatalog.image_id(bad)

    def test_resolve_returns_visias_canonical_url(self) -> None:
        with patch("app.integrations.visia.httpx.get", return_value=respond()) as get:
            resolved = self.catalog.resolve("http://luna-visia-mcp:8000/api/public/images/" + IMAGE_ID)

        self.assertEqual(resolved, PUBLIC + IMAGE_ID)
        self.assertEqual(get.call_args.args[0], "http://visia/api/metadata")

    def test_unknown_and_hidden_images_are_not_found(self) -> None:
        for image_id in ("99999999-9999-9999-9999-999999999999", HIDDEN_ID):
            with self.subTest(image_id=image_id):
                with patch("app.integrations.visia.httpx.get", return_value=respond()):
                    with self.assertRaises(NotFoundError):
                        self.catalog.resolve(PUBLIC + image_id)

    def test_placeholder_resolves_through_the_catalog(self) -> None:
        with patch("app.integrations.visia.httpx.get", return_value=respond()):
            self.assertEqual(self.catalog.placeholder_url(), PUBLIC + PLACEHOLDER_ID)

    def test_missing_placeholder_names_the_setting_to_fix(self) -> None:
        catalog = VisiaImageCatalog("http://visia/", "99999999-9999-9999-9999-999999999999")
        with patch("app.integrations.visia.httpx.get", return_value=respond()):
            with self.assertRaisesRegex(NotFoundError, "LUNAVITA_PLACEHOLDER_IMAGE_ID"):
                catalog.placeholder_url()

    def test_unreachable_visia_fails_closed(self) -> None:
        for failure in (httpx.ConnectError("refused"), respond(status=500)):
            with self.subTest(failure=type(failure).__name__):
                side_effect = failure if isinstance(failure, Exception) else None
                return_value = None if side_effect else failure
                with patch("app.integrations.visia.httpx.get", side_effect=side_effect, return_value=return_value):
                    with self.assertRaises(VisiaUnavailableError):
                        self.catalog.resolve(PUBLIC + IMAGE_ID)


def stored(status=201, payload=None):
    request = httpx.Request("POST", "http://visia/api/companion/images")
    body = payload if payload is not None else {"status": "created", "public_url": PUBLIC + IMAGE_ID}
    return httpx.Response(status, json=body, request=request)


@patch("app.integrations.visia.time.sleep")
class VisiaImageStoreTests(unittest.TestCase):
    TOKEN = "t" * 32

    def setUp(self) -> None:
        self.catalog = VisiaImageCatalog("http://visia/", PLACEHOLDER_ID, companion_token=self.TOKEN)

    def test_posts_the_source_with_the_companion_token(self, _sleep) -> None:
        with patch("app.integrations.visia.httpx.post", return_value=stored()) as post:
            result = self.catalog.store("Rice", ["food"], {"image_url": "https://x.test/rice.png"})
        self.assertEqual(result["public_url"], PUBLIC + IMAGE_ID)
        self.assertEqual(post.call_args.args[0], "http://visia/api/companion/images")
        self.assertEqual(
            post.call_args.kwargs["json"],
            {"name": "Rice", "tags": ["food"], "image_url": "https://x.test/rice.png"},
        )
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": f"Bearer {self.TOKEN}"})

    def test_retries_dropped_connections_and_server_errors(self, sleep) -> None:
        responses = [httpx.ConnectError("refused"), stored(502, {"error": "restarting"}), stored()]
        with patch("app.integrations.visia.httpx.post", side_effect=responses) as post:
            result = self.catalog.store("Rice", [], {"content_base64": "AAAA"})
        self.assertEqual((post.call_count, result["status"]), (3, "created"))
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_gives_up_after_the_last_attempt(self, _sleep) -> None:
        with patch("app.integrations.visia.httpx.post", return_value=stored(503, {"error": "off"})):
            with self.assertRaisesRegex(VisiaUnavailableError, "HTTP 503: off"):
                self.catalog.store("Rice", [], {"content_base64": "AAAA"})

    def test_rejected_images_and_tokens_are_not_retried(self, _sleep) -> None:
        for status, error in ((400, ValueError), (401, VisiaUnavailableError)):
            with self.subTest(status=status):
                with patch(
                    "app.integrations.visia.httpx.post",
                    return_value=stored(status, {"error": "Content is not a valid image."}),
                ) as post, self.assertRaises(error):
                    self.catalog.store("Rice", [], {"content_base64": "AAAA"})
                self.assertEqual(post.call_count, 1)

    def test_storing_needs_the_companion_token(self, _sleep) -> None:
        with self.assertRaisesRegex(VisiaUnavailableError, "LUNAVISIA_COMPANION_TOKEN"):
            VisiaImageCatalog("http://visia/", PLACEHOLDER_ID).store("Rice", [], {"content_base64": "AAAA"})

    def test_recognizes_visia_urls(self, _sleep) -> None:
        self.assertTrue(VisiaImageCatalog.is_visia_url(PUBLIC + IMAGE_ID))
        self.assertFalse(VisiaImageCatalog.is_visia_url("https://files.example.test/rice.png"))


if __name__ == "__main__":
    unittest.main()
