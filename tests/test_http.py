import unittest

import requests

from exchange_ticket.http import JsonHttpClient


class FakeResponse:
    def __init__(self, payload=None, *, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, url, params=None, timeout=None):
        return self.responses.pop(0)


class HttpClientTests(unittest.TestCase):
    def test_retries_connection_errors(self):
        error = requests.ConnectionError("temporary")
        responses = [FakeResponse(error=error), FakeResponse({"ok": True})]
        delays = []
        client = JsonHttpClient(
            session_factory=lambda: FakeSession(responses),
            sleep=delays.append,
            retry_base_delay=0.25,
        )

        self.assertEqual(client.get_json("https://example.test", attempts=2), {"ok": True})
        self.assertEqual(delays, [0.25])

    def test_rejects_zero_attempts(self):
        client = JsonHttpClient(session_factory=lambda: FakeSession([]))
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            client.get_json("https://example.test", attempts=0)


if __name__ == "__main__":
    unittest.main()
