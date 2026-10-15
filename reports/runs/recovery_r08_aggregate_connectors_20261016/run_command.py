import datetime, json, os, pathlib, subprocess, sys
run_directory = pathlib.Path(__file__).parent
label, *argv = sys.argv[1:]
started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
ended_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
(run_directory / (label + '.log')).write_bytes(result.stdout)
record = {'label': label, 'argv': argv, 'cwd': os.getcwd(), 'started_at': started_at, 'ended_at': ended_at, 'exit_code': result.returncode}
with (run_directory / 'commands.jsonl').open('a', encoding='utf-8', newline='\n') as receipt:
    receipt.write(json.dumps(record, ensure_ascii=False) + '\n')
print(json.dumps(record, ensure_ascii=False))
print(result.stdout.decode('utf-8', errors='replace')[-7000:])
sys.exit(result.returncode)
