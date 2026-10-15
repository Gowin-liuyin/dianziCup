import argparse, contextlib, importlib.util, io, json, os, pathlib, re, sys, time
source = pathlib.Path("/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi/scripts/prepare_search_tls_test.py")
spec = importlib.util.spec_from_file_location("frozen_fixture", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_compose = module.compose_command
module.compose_command = lambda command, project, host: original_compose(command, project, host) + ["-f", "/mnt/d/dianzi/reports/runs/recovery_r01_search_tls_review_2_20261015/a7_prefix_recheck/bounded_fixture.yaml"]
directory = pathlib.Path("/tmp/dianzi-r01-tls-prefix-review2-20261015")
arguments = argparse.Namespace(run_id="r01_tls_prefix_review2_20261015", private_directory=directory, port=29208,
    transport_port=29308, host_network=True, github_env=directory / "github_env")
os.environ["DIANZI_DOCKER_COMMAND_JSON"] = json.dumps(['/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker', '--config', '/tmp/dianzi-docker-static-r01-20261014/runtime/client-config', '-H', 'unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock'])
if True:
    os.environ.pop("DIANZI_DOCKER_COMMAND_JSON", None)
    os.environ["PATH"] = "/tmp/dianzi-r01-tls-prefix-runtime-20261015/bin:" + os.environ["PATH"]
buffer = io.StringIO()
code = 0
started = time.time()
with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
    try:
        if sys.argv[1] == "create":
            module.create_fixture(arguments)
        else:
            module.cleanup_fixture(arguments)
    except Exception as error:
        code = 1
        print("blocked: " + type(error).__name__)
text = buffer.getvalue()
values = None
if (directory / "connection.json").is_file():
    values = json.loads((directory / "connection.json").read_text())["environment"]
    password = values["TEST_SEARCH_TLS_PASSWORD"]
    mask_seen = "::add-mask::" + password in text
    text = text.replace(password, "[review fixture credential redacted]")
    text = re.sub("|".join(re.escape(password[i:i+8]) for i in range(len(password)-7)), "[review fixture fragment redacted]", text)
else:
    mask_seen = False
export_matches = False
exported = {}
if sys.argv[1] == "create" and (directory / "github_env").is_file():
    exported = dict(line.split("=", 1) for line in (directory / "github_env").read_text().splitlines())
    export_matches = exported == values
print(json.dumps({"action": sys.argv[1], "exit_code": code, "elapsed_seconds": time.time()-started,
    "github_mask_seen": mask_seen, "github_export_matches_connection": export_matches, "safe_output": text,
    "exported_name_count": len(exported), "exported_docker_prefix": exported.get("DIANZI_DOCKER_COMMAND_JSON"),
    "resource_overlay": "768MiB and heap384MiB", "host_network": True}))
sys.exit(code)
