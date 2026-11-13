"""Contrato de transporte: repetir leituras nunca pode duplicar um job."""
import sys
import time
import os
import importlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import client


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.credential = Mock()
        self.credential.get_token.return_value = SimpleNamespace(token="fixture", expires_on=time.time() + 3600)
        for patcher in [patch.object(client, "credential", self.credential), patch.object(client, "_fabric_token", None)]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_transient_get_is_retried_without_refetching_token(self):
        response = Mock()
        with patch.object(client.requests, "request", side_effect=[client.requests.ConnectTimeout(), response]) as send, patch.object(client.time, "sleep"):
            self.assertIs(client.request("GET", "workspaces"), response)
        self.assertEqual(send.call_count, 2)
        self.credential.get_token.assert_called_once()

    def test_job_start_is_never_retried_after_uncertain_submission(self):
        with patch.object(client.requests, "request", side_effect=client.requests.ReadTimeout()) as send:
            with self.assertRaises(client.requests.ReadTimeout):
                client.request("POST", "workspaces/fixture/items/fixture/jobs/Pipeline/instances", {})
        self.assertEqual(send.call_count, 1)

    def test_queryactivityruns_is_a_repeatable_read_despite_post(self):
        response = Mock()
        with patch.object(client.requests, "request", side_effect=[client.requests.ConnectTimeout(), response]) as send, patch.object(client.time, "sleep"):
            self.assertIs(client.request("POST", "workspaces/fixture/datapipelines/pipelineruns/fixture/queryactivityruns", {}), response)
        self.assertEqual(send.call_count, 2)

    def test_token_is_reused_only_while_valid(self):
        with patch.object(client.requests, "request", return_value=Mock()):
            client.request("GET", "workspaces")
            client.request("GET", "capacities")
            self.assertEqual(self.credential.get_token.call_count, 1)
            client._fabric_token.expires_on = time.time() + 30
            client.request("GET", "workspaces")
            self.assertEqual(self.credential.get_token.call_count, 2)

    def test_untrusted_host_is_rejected_before_token_acquisition(self):
        with self.assertRaises(ValueError):
            client.request("GET", "https://notfabric.example.net/resource")
        self.credential.get_token.assert_not_called()


class IdentityTests(unittest.TestCase):
    def test_reader_and_author_use_distinct_project_caches(self):
        try:
            paths = []
            for identity in ["author", "reader"]:
                with patch.dict(os.environ, {"FUELWATCH_IDENTITY": identity}):
                    importlib.reload(client)
                    paths.append(os.environ["AZURE_CONFIG_DIR"])
                    self.assertIsNone(client._fabric_token)
            self.assertNotEqual(paths[0], paths[1])
            self.assertTrue(paths[0].endswith("azure"))
            self.assertTrue(paths[1].endswith("azure-reader"))
        finally:
            importlib.reload(client)
