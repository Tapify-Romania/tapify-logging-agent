import unittest
from pathlib import Path

from deploy import render_config

TEMPLATE = (Path(__file__).resolve().parent / "config.alloy.template").read_text()
VALUES = {
    "METRICS_URL": "https://prometheus-prod-01-eu-west-0.grafana.net/api/prom/push",
    "METRICS_USERNAME": "123",
    "LOGS_URL": "https://logs-prod-eu-west-0.grafana.net/loki/api/v1/push",
    "LOGS_USERNAME": "456",
}


class RenderConfigTests(unittest.TestCase):
    def test_prod_scrapes_the_api_on_loopback_only(self):
        config = render_config(TEMPLATE, "prod", "tapify-prod-1", VALUES)
        self.assertIn('prometheus.scrape "api"', config)
        self.assertIn('"__address__" = "127.0.0.1:9464"', config)
        self.assertIn('job_name        = "tapify-api"', config)
        self.assertNotIn("@@", config)
        self.assertNotIn("PROD_ONLY", config)

    def test_identity_host_has_no_api_scrape(self):
        config = render_config(TEMPLATE, "identity", "tapify-identity-1", VALUES)
        self.assertNotIn('prometheus.scrape "api"', config)
        self.assertNotIn("9464", config)
        self.assertIn('prometheus.scrape "host"', config)

    def test_rendered_values_are_quoted_and_complete(self):
        config = render_config(TEMPLATE, "prod", "tapify-prod-1", VALUES)
        self.assertEqual(config.count('replacement  = "tapify-prod-1"'), 2)
        self.assertIn('url = "' + VALUES["METRICS_URL"] + '"', config)

    def test_missing_values_are_refused(self):
        with self.assertRaises(ValueError):
            render_config(TEMPLATE, "prod", "tapify-prod-1", {})


if __name__ == "__main__":
    unittest.main()
