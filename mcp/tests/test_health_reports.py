"""Tests for reading health reports from Luna Lexia and judging each result against its range."""

import unittest

import httpx

from app.core.errors import NotFoundError
from app.integrations.lexia import LexiaHealthReports, LexiaUnavailableError
from app.services.health_reports import HealthReportService, status_of, test_key

APRIL = "0b9f0c6e-4a4f-4c41-9d0c-0a1b2c3d4e5f"
OCTOBER = "1c8e1d7f-5b5e-4d52-8e1d-1b2c3d4e5f60"
TOKEN = "lexia-test-token-with-at-least-32-characters"


def lab(document_id, date, results, **extra):
    return {
        "document_id": document_id, "name": f"report-{date}.pdf", "doc_type": "health_report", "title": "Full body check-up",
        "issuer": "Acme Diagnostics", "document_date": date, "review_flags": [], "public_url": None, "updated_at": date,
        "extracted": {"lab_name": "Acme Diagnostics", "collection_date": date, "results": results, **extra},
    }


LDL = {"panel": "Lipid Profile", "test_name": "Cholesterol - LDL", "unit": "mg/dl", "reference_range": "<= 99.9", "reference_high": 99.9}
DOCUMENTS = [
    lab(OCTOBER, "2025-09-12", [{**LDL, "value": 161}]),
    lab(APRIL, "2026-03-09", [
        {**LDL, "value": 142, "previous_value": 161, "previous_date": "2025-09-12"},
        {"test_name": "Vitamin D (25-OH)", "value": 22.4, "unit": "ng/mL", "reference_low": 30, "reference_high": 100},
        {"test_name": "Glucose", "value_text": "Negative", "reference_range": "Negative"},
        {"test_name": "Hemoglobin", "value": 14, "reference_low": 13, "reference_high": 17},
    ], pending_tests=["Testosterone Free"]),
    {"document_id": "x", "doc_type": "payslip", "extracted": {}},
]


class FakeLexia:
    """Answers like Lexia's /api/metadata and public document routes, recording what was asked."""

    def __init__(self, documents=DOCUMENTS, status=200, lab_tests=None):
        self.documents, self.status, self.requests = documents, status, []
        self.lab_tests = lab_tests

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/api/lab-tests":
            return httpx.Response(404, json={"error": "Not found"}) if self.lab_tests is None else httpx.Response(200, json={"tests": self.lab_tests})
        if request.url.path.startswith("/api/public/documents/"):
            return httpx.Response(200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"})
        return httpx.Response(self.status, json={"documents": self.documents})


def service(fake=None, token=TOKEN):
    fake = fake or FakeLexia()
    return HealthReportService(LexiaHealthReports("http://lexia:8000/", token, transport=httpx.MockTransport(fake))), fake


class StatusTests(unittest.TestCase):
    def test_numbers_are_judged_against_their_range(self):
        self.assertEqual(status_of({"value": 22.4, "reference_low": 30, "reference_high": 100}), "low")
        self.assertEqual(status_of({"value": 142, "reference_high": 99.9}), "high")
        self.assertEqual(status_of({"value": 14, "reference_low": 13, "reference_high": 17}), "normal")
        self.assertEqual(status_of({"value": 14}), "unknown")

    def test_a_printed_flag_wins_and_text_results_are_read(self):
        self.assertEqual(status_of({"value": 14, "reference_low": 13, "flag": "low"}), "low")
        self.assertEqual(status_of({"value_text": "Negative", "reference_range": "Negative"}), "normal")
        self.assertEqual(status_of({"value_text": "Positive", "reference_range": "Negative"}), "abnormal")
        self.assertEqual(status_of({"value_text": "Nil"}), "normal")
        self.assertEqual(status_of({"value_text": "< 24", "reference_range": "11-44"}), "unknown")

    def test_test_names_match_without_punctuation(self):
        self.assertEqual(test_key("Glucose - Fasting"), test_key("glucose fasting"))


class HealthReportServiceTests(unittest.TestCase):
    def test_reports_come_newest_first_with_counts_and_history(self):
        reports, fake = service()
        found = reports.reports()
        self.assertEqual(found["count"], 2)
        latest = found["reports"][0]
        self.assertEqual(latest["document_id"], APRIL)
        self.assertEqual(latest["pending_tests"], ["Testosterone Free"])
        self.assertEqual(latest["counts"], {
            "tests": 4, "low": 1, "high": 1, "abnormal": 0, "normal": 2, "unknown": 0, "out_of_range": 2,
        })
        ldl = latest["results"][0]
        self.assertEqual(ldl["status"], "high")
        # October's own reading and the earlier value April prints are the same point.
        self.assertEqual([(point["date"], point["value"]) for point in ldl["history"]], [("2025-09-12", 161)])
        request = fake.requests[0]
        self.assertEqual(request.url.params.get_list("doc_type"), ["health_report"])
        self.assertEqual(request.headers["authorization"], f"Bearer {TOKEN}")
        self.assertTrue(request.headers["x-luna-user"])

    def test_results_can_be_narrowed_to_a_test_or_to_out_of_range(self):
        reports, _ = service()
        latest = reports.reports(test_name="ldl")["reports"][0]
        self.assertEqual([result["test_name"] for result in latest["results"]], ["Cholesterol - LDL"])
        flagged = reports.reports(only_out_of_range=True)["reports"][0]
        self.assertEqual([result["status"] for result in flagged["results"]], ["high", "low"])
        self.assertEqual(flagged["counts"]["tests"], 4)

    def test_a_trend_lists_every_dated_value(self):
        reports, _ = service()
        trend = reports.trend("cholesterol ldl")
        self.assertEqual(trend["test_name"], "Cholesterol - LDL")
        self.assertEqual([point["value"] for point in trend["points"]], [161, 142])
        self.assertEqual(trend["reference_high"], 99.9)
        with self.assertRaises(ValueError):
            reports.trend("ferritin")

    def test_each_result_carries_what_its_test_measures(self):
        explained = {"cholesterolldl": {"test_name": "LDL", "about": "The cholesterol that builds up in arteries.", "source": "assistant"},
                     "hemoglobin": {"test_name": "Hemoglobin", "about": "  ", "source": "model"}}
        reports, fake = service(FakeLexia(lab_tests=explained))
        april = reports.reports()["reports"][0]
        about = {result["test_name"]: result["about"] for result in april["results"]}
        self.assertEqual(about["Cholesterol - LDL"], "The cholesterol that builds up in arteries.")
        self.assertIsNone(about["Hemoglobin"])
        self.assertEqual(reports.trend("ldl")["about"], "The cholesterol that builds up in arteries.")
        self.assertEqual(fake.requests[1].url.path, "/api/lab-tests")

    def test_a_lexia_without_explanations_still_serves_reports(self):
        reports, _ = service()
        self.assertTrue(all(result["about"] is None for report in reports.reports()["reports"] for result in report["results"]))

    def test_only_this_persons_reports_are_served_as_files(self):
        reports, fake = service()
        data, media_type, name = reports.file(APRIL.upper())
        self.assertEqual((data, media_type, name), (b"%PDF-1.7", "application/pdf", "report-2026-03-09.pdf"))
        self.assertEqual(fake.requests[-1].url.path, f"/api/public/documents/{APRIL}")
        for unknown in ("2d77a066-d097-4b1b-9682-c9eb41538b26", "../etc/passwd"):
            with self.subTest(unknown), self.assertRaises(NotFoundError):
                reports.file(unknown)

    def test_lexia_being_off_or_refusing_is_reported(self):
        reports, _ = service(token="")
        self.assertFalse(reports.enabled)
        with self.assertRaisesRegex(LexiaUnavailableError, "LUNALEXIA_API_TOKEN"):
            reports.reports()
        with self.assertRaisesRegex(LexiaUnavailableError, "rejected"):
            service(FakeLexia(status=401))[0].reports()


if __name__ == "__main__":
    unittest.main()
