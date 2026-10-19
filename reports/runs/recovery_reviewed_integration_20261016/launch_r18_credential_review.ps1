param([Parameter(Mandatory)][string]$Batch)
$ErrorActionPreference='Stop'
$allowed=@('pg_new_1','pg_new_2','pg_new_3','pg_new_4','pg_new_5','pg_old_1','pg_old_2','pg_old_3','pg_old_4','pg_old_final_auth','pg_original_oracle')
if ($Batch -notin $allowed) { throw 'batch outside approved list' }
$reviewRoot='C:/Users/yinha/.codex/worktrees/r18-qcr-fix2-review/dianzi'
$run=$reviewRoot+'/reports/runs/r18_question_credential_review1_fix2_20261017'
$hashes=@{'run_pg_review.py'='4bb8b62dcd4093a9a97c2806a1d7cd3a45841536edd569c9dcd9fddc697401c9';'worker_entry.py'='c6bf4c406fc7bc61652999dc70c1e7f57ec82ddcf3a2cc5432e9f1ae75f83dbe';'pg_controller_admission.json'='fc6ce54b8a536b9bb95f1d522642e13a8f34b7ea1dab51d30bfe84178f5f2f5b'}
foreach($name in $hashes.Keys) {if((Get-FileHash -LiteralPath ($run+'/'+$name)).Hash.ToLowerInvariant() -ne $hashes[$name]) {throw 'frozen review entry changed'}}
$receiptRoot='D:/dianzi/reports/runs/recovery_reviewed_integration_20261016'
$receiptPath=$receiptRoot+'/r18_credential_'+$Batch+'_launch.json'
if(Test-Path -LiteralPath $receiptPath){throw 'refusing receipt overwrite'}
$deadline=[DateTimeOffset]::Parse('2026-10-16T23:34:04.844Z')
if([DateTimeOffset]::UtcNow -ge $deadline){throw 'review authorization expired'}
$started=[DateTimeOffset]::Now.ToString('o')
$pointer=[IntPtr]::Zero
try{$secure=ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi'));$pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);$parentResource=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)|ConvertFrom-Json -DateKind String}finally{if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}}
if(-not $parentResource.TEST_DATABASE_URL){throw 'authorized parent reference missing'}
$info=[Diagnostics.ProcessStartInfo]::new()
$info.FileName='C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe'
$info.WorkingDirectory=$reviewRoot
$info.UseShellExecute=$false
$info.CreateNoWindow=$true
$info.RedirectStandardOutput=$true
$info.RedirectStandardError=$true
$info.ArgumentList.Add($run+'/worker_entry.py');$info.ArgumentList.Add('run_pg_review');$info.ArgumentList.Add($Batch)
$info.Environment['PYTHONPATH']='D:/dianzi/backend/.venv/Lib/site-packages'
$info.Environment['PYTHONNOUSERSITE']='1'
$info.Environment['R18_REVIEW_PARENT_DATABASE_URL']=$parentResource.TEST_DATABASE_URL
$info.Environment['DIANZI_REVIEW_RESOURCE_AUTHORIZED']='r18-question-credential-review1-fix2'
$info.Environment['R18_REVIEW_BATCH_ALLOWLIST']=($allowed|ConvertTo-Json -Compress)
$info.Environment['R18_REVIEW_AUTHORIZED_UNTIL_UTC']=$deadline.ToUniversalTime().ToString('o')
$p=[Diagnostics.Process]::new();$p.StartInfo=$info;[void]$p.Start()
$outTask=$p.StandardOutput.ReadToEndAsync();$errTask=$p.StandardError.ReadToEndAsync()
$timedOut=-not $p.WaitForExit(60000)
if($timedOut){$p.Kill();$p.WaitForExit()}
$outText=$outTask.GetAwaiter().GetResult();$errText=$errTask.GetAwaiter().GetResult()
$outText=$outText.Replace([string]$parentResource.TEST_DATABASE_URL,'[REDACTED]');$errText=$errText.Replace([string]$parentResource.TEST_DATABASE_URL,'[REDACTED]')
[IO.File]::WriteAllText($receiptRoot+'/r18_credential_'+$Batch+'_stdout.log',$outText)
[IO.File]::WriteAllText($receiptRoot+'/r18_credential_'+$Batch+'_stderr.log',$errText)
$receipt=[ordered]@{batch=$Batch;started_at=$started;ended_at=[DateTimeOffset]::Now.ToString('o');exit_code=$p.ExitCode;timeout_seconds=60;outer_timeout=$timedOut;authorized_until_utc=$deadline.ToUniversalTime().ToString('o');source_sha='0bcabdcb5a511ce83e92b74683597c63b7a9a9cf';root_environment_injected=$true;secret_values_printed=$false;full_process_peak='independent native controller receipt'}
$receipt|ConvertTo-Json|Set-Content -LiteralPath $receiptPath -Encoding utf8
$parentResource=$null;$outText=$null;$errText=$null
$receipt|ConvertTo-Json -Compress
if($timedOut){exit 124};exit $p.ExitCode
