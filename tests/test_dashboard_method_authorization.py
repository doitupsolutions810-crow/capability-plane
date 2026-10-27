import unittest
from unittest.mock import patch

from sovereign.dashboard import app


class DashboardMethodAuthorizationTests(unittest.TestCase):
    def test_missing_method_fails_before_capability_issue(self):
        with patch.object(app, "plane_post") as plane_post:
            result = app.run_intent({"resource": "tool.summarize"})

        self.assertEqual(result["stage"], "validate")
        self.assertIn("method", result["error"])
        plane_post.assert_not_called()

    def test_multiple_rights_fail_before_capability_issue(self):
        rights = [
            {"type": "tool", "resource": "tool.summarize", "method": "invoke"},
            {"type": "file", "resource": "result.json", "method": "write"},
        ]
        with patch.object(app, "plane_post") as plane_post:
            result = app.run_intent({"rights": rights})

        self.assertEqual(result["stage"], "validate")
        self.assertIn("exactly one", result["error"])
        plane_post.assert_not_called()

    def test_explicit_method_is_used_for_issue_verify_and_execute(self):
        rights = [{"type": "tool", "resource": "tool.summarize", "method": "invoke"}]
        responses = [
            {"status": "ok", "capability": {"id": "cap-1"}, "signature": "sig"},
            {"valid": True},
            {"status": "ok"},
        ]
        with patch.object(app, "plane_post", side_effect=responses) as plane_post:
            result = app.run_intent({"rights": rights})

        self.assertEqual(result["stage"], "execute")
        calls = plane_post.call_args_list
        self.assertEqual(calls[0].args[1]["rights"], rights)
        self.assertEqual(calls[1].args[1]["required"], rights[0])
        self.assertEqual(calls[2].args[1]["required"], rights[0])


if __name__ == "__main__":
    unittest.main()
