import importlib.util,tempfile
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('workflow',str(Path(__file__).resolve().parents[1]/'delivery/eq/apps/workflow/workflow.py'));w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
with tempfile.TemporaryDirectory() as d:
 r=Path(d);w.write(r/'status.json',{'state':'running'});w.write(r/'job.json',{'pid':99999999,'token':'abc','start_ticks':'42'})
 original=Path.read_bytes
 def vanished(p):
  if str(p)=='/proc/99999999/cmdline':
   w.write(r/'status.json',{'state':'completed'});raise FileNotFoundError(str(p))
  return original(p)
 with patch.object(w,'process_identity',return_value={'start_ticks':'42'}),patch.object(Path,'read_bytes',vanished):
  assert w.state(r)['state']=='completed'
 print('PASS: worker exit race preserves final completed state')


def test_worker_exit_race_contract():
    """Run the existing standalone assertions under pytest as well."""
    import runpy
    runpy.run_path(str(Path(__file__).resolve()), run_name="workflow_contract_check")
