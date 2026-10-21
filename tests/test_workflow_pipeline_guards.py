"""Review identity and acquisition fail-closed regression tests."""
import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/'delivery/eq/apps/workflow/workflow.py'
spec=importlib.util.spec_from_file_location('wf_pipeline_guards',p);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
with tempfile.TemporaryDirectory() as folder:
 r=Path(folder)
 w.write(r/'snapshot.json',{'revision':1})
 w.write(r/'quality.json',{'passed':True})
 st={'steps':{'quality':{'state':'completed','sha256':w.sha(r/'quality.json')},'review_data':{'state':'waiting_review'}}}
 identity=w.review_identity(r,st,'review_data')
 w.write(r/'snapshot.json',{'revision':2})
 assert w.review_identity(r,st,'review_data')!=identity
 w.write(r/'quality.json',{'passed':False})
 try:w.review_identity(r,st,'review_data');raise AssertionError('changed artifact accepted')
 except ValueError:pass
 mapping={'mapping':{'FLUX_LOOP_NODES':['FL1B'],'B_PROBE_NODES_LEGACY':[],'PF_NODES':[]}}
 with patch.object(w.pipeline_tools,'read',return_value=mapping),patch.dict(w.os.environ,{'FYLITE_EQ_ROOT':str(r)}),patch.object(w.pipeline_tools,'sp_call',side_effect=ValueError('offline')):
  try:w.pipeline_tools.acquire(r,{'data_source':'mdsplus'},r);raise AssertionError('online failure accepted')
  except ValueError as e:assert str(e)=='offline'
  assert not (r/'acquired-waveforms.json.gz').exists()
print('PASS: review snapshot/artifact identity and no silent online fallback')
