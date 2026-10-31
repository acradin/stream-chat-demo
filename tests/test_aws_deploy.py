"""Deployment boundaries with fake AWS; no account, cloud spend or provider calls."""

import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from deploy.aws.deploy import (Aws, AwsError, ROOT, RUNTIME_FILES, assert_account, ensure_stack,
                              package, remote_commands, runtime_config, validate_domain)
from deploy.aws.run_server import validate_config
from deploy.aws.template import build_template


class AwsDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def env_file(self):
        path = self.directory / ".env"
        path.write_text("OPENAI_API_KEY=test-openai-secret\nCHAT_SERVICE_TOKEN=" + "x" * 40 +
                        "\nCHZZK_CLIENT_ID=test-id\nCHZZK_CLIENT_SECRET=test-chzzk-secret\nCHZZK_CHANNEL_ID=" + "a" * 32 +
                        "\nUNRELATED_SECRET=never-upload\nCHAT_PUBLIC_URL=http://localhost:8766\n", encoding="utf-8")
        return path

    def test_archive_excludes_runtime_data_and_normalizes_windows_scripts(self):
        root = self.directory / "source"
        (root / "backend").mkdir(parents=True)
        (root / "backend/server.py").write_bytes(b"# source\r\n")
        for relative in RUNTIME_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# source\r\n")
        for name in ("backend/.env", "backend/tokens.json", "runs/chzzk/tokens.json", "apps/desktop/.env", ".git/config"):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("UNIQUE-SECRET-MUST-NOT-BE-PACKAGED")
        archive, digest, template = package(root, self.directory / "out")
        self.assertEqual(len(digest), 64)
        with tarfile.open(archive) as bundle:
            self.assertEqual(set(bundle.getnames()), {"backend/server.py", *RUNTIME_FILES})
            for member in bundle:
                content = bundle.extractfile(member).read()
                self.assertNotIn(b"UNIQUE-SECRET", content)
                self.assertNotIn(b"\r\n", content)
                self.assertTrue(member.isfile())
        self.assertIn("Resources", json.loads(template.read_text()))

    def test_web_build_contains_only_public_assets_with_binary_bytes_intact(self):
        static = self.directory / "source/apps/web/dist"
        static.mkdir(parents=True)
        root = self.directory / "source"
        (root / "backend").mkdir()
        (root / "backend/server.py").write_text("# server")
        for relative in RUNTIME_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# source")
        (static / "index.html").write_text("<html>tiki</html>")
        (static / "icon.png").write_bytes(b"\x89PNG\r\n\xff")
        (static / "demo.mp4").write_bytes(b"\x00\x00ftyp\r\n\xff")
        (static / ".env").write_text("private")
        (static / "main.js.map").write_text("private source")
        archive, _, _ = package(root, self.directory / "out")
        with tarfile.open(archive) as bundle:
            self.assertIn("apps/web/dist/index.html", bundle.getnames())
            self.assertEqual(bundle.extractfile("apps/web/dist/icon.png").read(), b"\x89PNG\r\n\xff")
            self.assertEqual(bundle.extractfile("apps/web/dist/demo.mp4").read(), b"\x00\x00ftyp\r\n\xff")
            self.assertNotIn("apps/web/dist/.env", bundle.getnames())
            self.assertNotIn("apps/web/dist/main.js.map", bundle.getnames())

    def test_runtime_config_is_filtered_validated_and_does_not_modify_local_env(self):
        path = self.env_file()
        before = path.read_bytes()
        config = runtime_config(path, "chat.mydomain.com")
        self.assertNotIn("UNRELATED_SECRET", config)
        self.assertEqual(config["CHAT_PUBLIC_URL"], "https://chat.mydomain.com")
        self.assertEqual(config["CHZZK_REDIRECT_URI"], "https://chat.mydomain.com/oauth/chzzk/callback")
        self.assertEqual(config["CHAT_STATE_DIR"], "/var/lib/stream-chat")
        self.assertEqual(path.read_bytes(), before)
        for altered in ({"CHAT_HOST": "0.0.0.0"}, {"PORT": "80"}, {"CHAT_STATE_DIR": "/tmp"},
                        {"CHZZK_SERVICE_ACCOUNT": "another-user"}, {"OPENAI_API_KEY": ""}):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "must-not-fallback"}), self.assertRaises(ValueError):
                validate_config({**config, **altered})

    def test_domain_and_remote_command_arguments_cannot_inject_shell_commands(self):
        for domain in ("chat.example.com;id", "https://chat.example.com", "chat.example.com/path", "127.0.0.1",
                       "localhost", "chat.example.com\nwhoami", "*.example.com"):
            with self.assertRaises(ValueError):
                validate_domain(domain)
        outputs = {"ArtifactBucket": "private-artifacts-123", "RuntimeParameter": "/stream-chat/runtime", "DomainName": "chat.mydomain.com"}
        args = (outputs, "releases/" + "a" * 32 + ".tar.gz", "b" * 64, 3, "a" * 32, "ap-northeast-2")
        script = "\n".join(remote_commands(*args))
        self.assertIn("sha256sum --check", script)
        self.assertIn("/stream-chat/runtime:3", script)
        self.assertIn('> "$runtime"', script)
        self.assertNotIn("set -x", script)
        with self.assertRaises(ValueError):
            remote_commands({**outputs, "RuntimeParameter": "/stream-chat/runtime;id"}, *args[1:])

    def test_wrong_aws_account_stops_before_any_mutation(self):
        aws = Mock()
        aws.run.return_value = {"Account": "111111111111"}
        with self.assertRaises(ValueError):
            assert_account(aws, "222222222222")
        aws.run.assert_called_once_with("sts", "get-caller-identity")

    def test_existing_stack_is_reused_without_replacing_instance_or_disk(self):
        outputs = {"DeploymentKind": "StreamChatSingleInstanceV1", "DomainName": "chat.mydomain.com"}
        aws = Mock()
        aws.run.return_value = {"Stacks": [{"StackName": "stream-chat", "StackStatus": "CREATE_COMPLETE",
            "Outputs": [{"OutputKey": key, "OutputValue": value} for key, value in outputs.items()]}]}
        self.assertEqual(ensure_stack(aws, "stream-chat", "chat.mydomain.com", Path("unused"), "t3.micro"), outputs)
        self.assertTrue(all(call.args[:2] == ("cloudformation", "describe-stacks") for call in aws.run.call_args_list))
        with self.assertRaises(ValueError):
            ensure_stack(aws, "stream-chat", "other.mydomain.com", Path("unused"), "t3.micro")

    def test_secret_payload_is_not_in_arguments_and_temp_file_is_removed_on_failure(self):
        seen = []
        def execute(arguments, **kwargs):
            self.assertNotIn("private-secret-value", repr(arguments))
            name = Path(arguments[-1].removeprefix("file://"))
            seen.append(name)
            self.assertEqual(json.loads(name.read_text())["Value"], "private-secret-value")
            return subprocess.CompletedProcess(arguments, 1, "", "An error occurred (AccessDeniedException): private-secret-value")
        with patch("deploy.aws.deploy.shutil.which", return_value="fake-aws"), patch("deploy.aws.deploy.subprocess.run", side_effect=execute):
            with self.assertRaises(AwsError) as raised:
                Aws("ap-northeast-2").run("ssm", "put-parameter", payload={"Value": "private-secret-value"})
        self.assertNotIn("private-secret-value", str(raised.exception))
        self.assertFalse(seen[0].exists())

    def test_template_does_not_expose_backend_or_keys_and_preserves_state_disk(self):
        template = build_template()
        resources = template["Resources"]
        ingress = resources["SecurityGroup"]["Properties"]["SecurityGroupIngress"]
        self.assertEqual({entry["FromPort"] for entry in ingress}, {80, 443})
        instance = resources["Instance"]["Properties"]
        self.assertEqual(instance["MetadataOptions"]["HttpTokens"], "required")
        disk = instance["BlockDeviceMappings"][0]["Ebs"]
        self.assertTrue(disk["Encrypted"])
        self.assertFalse(disk["DeleteOnTermination"])
        self.assertNotIn("KeyName", instance)
        self.assertNotIn("OPENAI_API_KEY", json.dumps(template))
        self.assertTrue(all(resources["Artifacts"]["Properties"]["PublicAccessBlockConfiguration"].values()))


if __name__ == "__main__":
    unittest.main()
