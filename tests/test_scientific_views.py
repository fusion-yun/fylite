"""W2 read-only API contracts. Fixtures are synthetic, not scientific validation."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/'delivery/eq/apps/workflow/workflow.py'
spec=importlib.util.spec_from_file_location('wf_views',p);w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)

class Views(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.roots=[self.root];self.case=w.save({'name':'synthetic test','parameters':w.DEFAULT},self.roots)
  self.query={'case_id':[self.case['case_id']],'run_id':['run-a'],'other_run_id':['run-b']}
  self.a=w.runpath(self.case['case_id'],'run-a',self.roots);self.b=w.runpath(self.case['case_id'],'run-b',self.roots)
  for run in (self.a,self.b):
   run.mkdir(parents=True);w.write(run/'snapshot.json',{'revision':1,'dataset_manifest_sha256':'fixture'})
   data={'effective':{'shot':94048,'time_s':5.760,'pressure_time_s':6.510,'q_mode':'target'},'config':{'x':[1,2]}}
   w.write(run/'assemble.json',data);w.write(run/'status.json',{'steps':{'assemble':{'state':'completed','sha256':w.sha(run/'assemble.json')}}})
 def tearDown(self):self.tmp.cleanup()
 def dispatch(self):return w.scientific_views.dispatch(w,'compare',self.roots,self.query)
 def update(self,run,value):
  w.write(run/'assemble.json',value);w.write(run/'status.json',{'steps':{'assemble':{'state':'completed','sha256':w.sha(run/'assemble.json')}}})
 def test_unchanged_inputs_and_files(self):
  before={str(p):w.sha(p) for p in self.root.rglob('*') if p.is_file()}
  d=self.dispatch();self.assertEqual(d['input_diff'],[]);self.assertTrue(d['aligned']);self.assertEqual(d['reports'],[None,None]);self.assertEqual(before,{str(p):w.sha(p) for p in self.root.rglob('*') if p.is_file()})
 def test_diff_array_and_time_mismatch(self):
  v=w.read(self.b/'assemble.json');v['config']['x']=[1,3,4];v['effective']['time_s']=6.386;self.update(self.b,v)
  d=self.dispatch();self.assertFalse(d['aligned']);self.assertTrue(d['warnings']);self.assertEqual(next(x for x in d['input_diff'] if x['field']=='config.x')['changed_count'],2)
 def test_corrupt_or_incomplete_inputs_rejected(self):
  w.write(self.b/'assemble.json',{});
  with self.assertRaises(ValueError):self.dispatch()
 def test_personal_path_escape_rejected(self):
  self.query['other_case_id']=['../../bad']
  with self.assertRaises(ValueError):self.dispatch()
 def test_no_unknown_channel_kind(self):
  with self.assertRaises(ValueError):w.scientific_views.dispatch(w,'channel-view',self.roots,{**self.query,'kind':['PF'],'index':['0']})
 def test_pressure_preview_validates_scale_without_solver(self):
  with patch.object(w,'manifest'),patch.object(w,'sha',return_value='test-sha'),patch.object(w,'pressure',return_value={'pressure_Pa':[1]}) as pressure:
   d=w.scientific_views.dispatch(w,'pressure-preview',self.roots,{'scale':['1.2']});self.assertEqual(d['kind'],'draft-preview');self.assertEqual(pressure.call_args[0][1]['pressure_scale'],1.2)
   with self.assertRaises(ValueError):w.scientific_views.dispatch(w,'pressure-preview',self.roots,{'scale':['nan']})

if __name__=='__main__':unittest.main()
