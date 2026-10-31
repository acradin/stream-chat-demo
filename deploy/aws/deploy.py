"""Prepare locally; deploy only when an explicit AWS account and domain are supplied."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request
import uuid

from backend.env import BACKEND_KEYS, read_env_file
from deploy.aws.template import build_template


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "dist" / "aws"
RUNTIME_FILES = ("deploy/__init__.py", "deploy/aws/__init__.py", "deploy/aws/run_server.py",
                 "deploy/aws/install_release.sh", "deploy/aws/stream-chat.service", "deploy/aws/requirements.txt",
                 "apps/__init__.py", "apps/web/__init__.py", "apps/web/server.py")


def validate_domain(domain):
    if (not isinstance(domain, str) or len(domain) > 253 or domain != domain.lower() or "." not in domain
            or all(part.isdigit() for part in domain.split("."))
            or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in domain.split("."))
            or domain.endswith((".localhost", ".local", ".test", ".invalid", ".example"))):
        raise ValueError("Use a real public hostname you control, such as chat.your-domain.com.")
    return domain


def package(root=ROOT, output=OUTPUT):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    files = sorted(path.relative_to(root).as_posix() for path in (root / "backend").glob("*.py")
                   if path.name != "desktop_demo.py") + list(RUNTIME_FILES)
    if "backend/server.py" not in files:
        raise ValueError("Backend source is missing")
    static = root / "apps/web/dist"
    if (static / "index.html").is_file():
        files += [path.relative_to(root).as_posix() for path in static.rglob("*")
                  if path.is_file() and path.suffix in {".html", ".js", ".css", ".svg", ".png", ".jpg", ".webp", ".woff2", ".ttf", ".mp4"}
                  and not any(part.startswith(".") for part in path.relative_to(static).parts)]
    archive = output / "stream-chat-backend.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name in sorted(files):
            source = root / name
            if source.is_symlink() or not source.resolve().is_relative_to(root):
                raise ValueError("Refusing to bundle files outside the project")
            # Normalize Windows checkouts for Linux shell and systemd files.
            payload = (source.read_bytes() if name.startswith("apps/web/dist/") else
                       source.read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode("utf-8"))
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(payload), 0o644, 0
            bundle.addfile(info, io.BytesIO(payload))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = {"archive": archive.name, "sha256": checksum, "files": sorted(files), "contains_credentials": False}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    template = output / "cloudformation.json"
    template.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")
    return archive, checksum, template


def runtime_config(env_file, domain):
    from deploy.aws.run_server import validate_config
    config = read_env_file(Path(env_file), BACKEND_KEYS)
    origin = "https://" + validate_domain(domain)
    config.update(CHAT_PUBLIC_URL=origin, CHAT_HOST="127.0.0.1", PORT="8766",
                  CHAT_STATE_DIR="/var/lib/stream-chat", CHZZK_REDIRECT_URI=origin + "/oauth/chzzk/callback")
    validate_config(config)
    if len(json.dumps(config, ensure_ascii=True).encode()) > 4096:
        raise ValueError("Runtime configuration exceeds the 4 KB Standard Parameter Store limit")
    return config


class AwsError(RuntimeError):
    def __init__(self, command, stderr):
        # Only the stable AWS error code is safe to show; payloads may contain secrets.
        match = re.search(r"An error occurred \(([^)]+)\)", stderr)
        self.code = match.group(1) if match else "CLIError"
        super().__init__(f"AWS {' '.join(command[:2])} failed ({self.code}). Check the account, region and permissions.")


class Aws:
    def __init__(self, region, profile=None):
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", region):
            raise ValueError("Invalid AWS region")
        executable = shutil.which("aws")
        if not executable:
            raise ValueError("Install AWS CLI v2 and sign in before running deploy. See AWS.md.")
        self.prefix = [executable, "--region", region, "--output", "json"]
        if profile:
            self.prefix += ["--profile", profile]

    def run(self, *command, payload=None, timeout=90):
        environment = {**os.environ, "AWS_PAGER": "", "AWS_CLI_AUTO_PROMPT": "off"}
        filename = None
        try:
            arguments = [*self.prefix, *command]
            if payload is not None:
                # Never put secret values in argv, shell history, or tool output.
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="stream-chat-aws-",
                                                 suffix=".json", delete=False) as handle:
                    filename = Path(handle.name)
                    json.dump(payload, handle, ensure_ascii=True)
                if os.name != "nt":
                    filename.chmod(0o600)
                arguments += ["--cli-input-json", "file://" + str(filename)]
            result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=timeout, env=environment, check=False)
            if result.returncode:
                raise AwsError(command, result.stderr)
            return json.loads(result.stdout) if result.stdout.strip() else {}
        finally:
            if filename is not None:
                filename.unlink(missing_ok=True)


def assert_account(aws, expected):
    if not re.fullmatch(r"\d{12}", expected):
        raise ValueError("Supply the new AWS account's 12-digit account ID")
    identity = aws.run("sts", "get-caller-identity")
    if identity["Account"] != expected:
        raise ValueError("Signed in to a different AWS account. No resources were changed.")


def stack_outputs(aws, stack):
    result = aws.run("cloudformation", "describe-stacks", "--stack-name", stack)
    item = result["Stacks"][0]
    if item["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
        raise ValueError("Stack is not ready. Inspect its CloudFormation events before retrying.")
    outputs = {entry["OutputKey"]: entry["OutputValue"] for entry in item.get("Outputs", [])}
    if outputs.get("DeploymentKind") != "StreamChatSingleInstanceV1":
        raise ValueError("This stack belongs to another application; it will not be changed.")
    return outputs


def ensure_stack(aws, stack, domain, template, instance_type):
    # Reuse existing infrastructure; ordinary releases never replace the state disk/VM.
    names = aws.run("cloudformation", "describe-stacks").get("Stacks", [])
    if any(item["StackName"] == stack for item in names):
        outputs = stack_outputs(aws, stack)
        if outputs["DomainName"] != domain:
            raise ValueError("The existing stack uses another domain; choose its existing domain or a new stack name.")
        return outputs
    aws.run("cloudformation", "validate-template", "--template-body", "file://" + str(template))
    aws.run("cloudformation", "create-stack", payload={
        "StackName": stack, "TemplateBody": template.read_text(encoding="utf-8"), "Capabilities": ["CAPABILITY_IAM"],
        "Parameters": [{"ParameterKey": "DomainName", "ParameterValue": domain},
                       {"ParameterKey": "InstanceType", "ParameterValue": instance_type}],
        "Tags": [{"Key": "Application", "Value": "StreamChat"}]})
    for attempt in range(120):
        item = aws.run("cloudformation", "describe-stacks", "--stack-name", stack)["Stacks"][0]
        status = item["StackStatus"]
        if status == "CREATE_COMPLETE":
            return stack_outputs(aws, stack)
        if status != "CREATE_IN_PROGRESS":
            raise ValueError("Stack creation failed. Inspect CloudFormation events; do not delete retained data volumes blindly.")
        if attempt % 3 == 0:
            print("Creating AWS server...", flush=True)
        time.sleep(10)
    raise ValueError("Stack creation is still pending; check CloudFormation before retrying.")


def remote_commands(outputs, key, checksum, version, release_id, region):
    for value, pattern in ((outputs["ArtifactBucket"], r"[a-z0-9][a-z0-9.-]+"),
                           (outputs["RuntimeParameter"], r"/[A-Za-z0-9-]+/runtime"),
                           (release_id, r"[a-f0-9]{32}"), (checksum, r"[a-f0-9]{64}"),
                           (key, r"releases/[a-f0-9]{32}\.tar\.gz")):
        if not re.fullmatch(pattern, value):
            raise ValueError("Unexpected deployment identifier")
    domain = validate_domain(outputs["DomainName"])
    version = int(version)
    quote = shlex.quote
    release = "/opt/stream-chat/releases/" + release_id
    uri = "s3://" + outputs["ArtifactBucket"] + "/" + key
    parameter = outputs["RuntimeParameter"] + ":" + str(version)
    return ["set -eu", "umask 077",
        "cloud-init status --wait >/dev/null || test -f /var/lib/stream-chat-bootstrap.ready",
        "test -f /var/lib/stream-chat-bootstrap.ready", "test ! -e " + quote(release),
        "install -d -m 755 " + quote(release),
        "runtime=$(mktemp /var/tmp/stream-chat-runtime.XXXXXX)", "trap 'rm -f -- \"$runtime\"' EXIT",
        f"aws s3 cp {quote(uri)} {quote(release + '/source.tar.gz')} --region {quote(region)} --only-show-errors",
        f"echo {quote(checksum + '  ' + release + '/source.tar.gz')} | sha256sum --check --status",
        f"tar --extract --gzip --file {quote(release + '/source.tar.gz')} --directory {quote(release)} --no-same-owner",
        f"aws ssm get-parameter --name {quote(parameter)} --with-decryption --region {quote(region)} --query Parameter.Value --output text > \"$runtime\"",
        f"bash {quote(release + '/deploy/aws/install_release.sh')} {quote(release)} {quote(domain)} \"$runtime\""]


def wait_for_ssm(aws, instance):
    for attempt in range(90):
        info = aws.run("ssm", "describe-instance-information", payload={
            "Filters": [{"Key": "InstanceIds", "Values": [instance]}]})
        if any(item["PingStatus"] == "Online" for item in info["InstanceInformationList"]):
            return
        if attempt % 3 == 0:
            print("Waiting for server management connection...", flush=True)
        time.sleep(10)
    raise ValueError("SSM is not online yet. Check the EC2 instance role and outbound network access.")


def wait_for_command(aws, command_id, instance):
    for attempt in range(180):
        try:
            result = aws.run("ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", instance)
        except AwsError as exc:
            if exc.code != "InvocationDoesNotExist":
                raise
            result = {"Status": "Pending"}
        status = result["Status"]
        if status == "Success":
            return
        if status not in ("Pending", "InProgress", "Delayed"):
            raise ValueError(f"Server installation failed ({status}). Check SSM Run Command {command_id} in the console.")
        if attempt % 3 == 0:
            print("Installing and checking the backend...", flush=True)
        time.sleep(10)
    raise ValueError("Installation is still pending; check SSM Run Command before starting another release.")


def check_public(origin, token):
    from backend.chzzk_remote import public_origin
    origin = public_origin(origin)
    # Redirects must never forward the service token to a different host.
    from urllib.request import HTTPRedirectHandler, build_opener, HTTPSHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = build_opener(NoRedirect, HTTPSHandler(context=ssl.create_default_context()))
    for path, headers in (("/healthz", {}), ("/api/usage", {"Authorization": "Bearer " + token})):
        with opener.open(Request(origin + path, headers=headers), timeout=20) as response:
            body = json.loads(response.read(65537))
        if path == "/healthz" and body != {"status": "ok"}:
            raise ValueError("Unexpected health response")
        if path == "/api/usage" and not isinstance(body.get("generation_requests"), int):
            raise ValueError("Unexpected authenticated service response")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("package", help="Create a secret-free source archive; no AWS calls")
    for name in ("deploy", "check"):
        command = commands.add_parser(name)
        command.add_argument("--account-id", required=True)
        command.add_argument("--region", default="us-east-1")
        command.add_argument("--profile")
        command.add_argument("--stack", default="stream-chat-demo")
        command.add_argument("--env-file", type=Path, default=ROOT / "backend" / ".env")
        if name == "deploy":
            command.add_argument("--domain", required=True)
            command.add_argument("--instance-type", choices=("t3.micro", "t3.small"), default="t3.micro")
    args = parser.parse_args()
    try:
        if args.command == "package":
            archive, checksum, template = package()
            print(f"Archive: {archive}\nSHA256: {checksum}\nCloudFormation: {template}\nNo secrets included. No AWS resources created.")
            return
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,47}", args.stack):
            raise ValueError("Use a stack name of 1-48 letters, digits or hyphens, starting with a letter")
        aws = Aws(args.region, args.profile)
        assert_account(aws, args.account_id)
        if args.command == "deploy":
            config = runtime_config(args.env_file, args.domain)
            archive, checksum, template = package()
            print(f"Target: AWS {args.account_id}, {args.region}, {args.stack}, {args.domain}", flush=True)
            outputs = ensure_stack(aws, args.stack, args.domain, template, args.instance_type)
            version = aws.run("ssm", "put-parameter", payload={"Name": outputs["RuntimeParameter"],
                "Type": "SecureString", "Tier": "Standard", "Value": json.dumps(config, ensure_ascii=True), "Overwrite": True})["Version"]
            release = uuid.uuid4().hex
            key = "releases/" + release + ".tar.gz"
            aws.run("s3", "cp", str(archive), "s3://" + outputs["ArtifactBucket"] + "/" + key, "--only-show-errors")
            wait_for_ssm(aws, outputs["InstanceId"])
            command = aws.run("ssm", "send-command", payload={"InstanceIds": [outputs["InstanceId"]],
                "DocumentName": "AWS-RunShellScript", "TimeoutSeconds": 600,
                "Parameters": {"commands": remote_commands(outputs, key, checksum, version, release, args.region),
                               "executionTimeout": ["1800"]}})
            wait_for_command(aws, command["Command"]["CommandId"], outputs["InstanceId"])
        else:
            outputs = stack_outputs(aws, args.stack)
            config = runtime_config(args.env_file, outputs["DomainName"])
        print(f"DNS A record: {outputs['DomainName']} -> {outputs['PublicIp']}")
        print(f"CHZZK login redirect: {outputs['CallbackUrl']}")
        accounts = json.loads(config["CHAT_SERVICE_ACCOUNTS"]) if config.get("CHAT_SERVICE_ACCOUNTS") else {"development": config["CHAT_SERVICE_TOKEN"]}
        token = accounts[config.get("CHZZK_SERVICE_ACCOUNT", "development")]
        try:
            check_public(outputs["PublicUrl"], token)
        except (URLError, OSError, ValueError):
            parser.exit(2, "Public HTTPS/auth check is pending. Set the DNS record, allow certificate issuance, then run check. No AI/chat requests were sent.\n")
        print("HTTPS and authenticated service verified. No AI requests or broadcast chats sent.")
    except (ValueError, OSError, AwsError, subprocess.TimeoutExpired):
        # Error strings from SDKs/subprocesses can contain request payloads.
        import sys
        exc = sys.exception()
        message = str(exc) if isinstance(exc, (ValueError, AwsError)) else "Local command failed; check AWS CLI and local file permissions."
        parser.exit(1, message + "\n")


if __name__ == "__main__":
    main()
