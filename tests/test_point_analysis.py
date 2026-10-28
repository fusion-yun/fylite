"""POINT numerical-processing checks, not experimental qualification."""
import json,math,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'delivery/eq/apps/workflow'));sys.path.insert(0,str(ROOT/'tools'))
import point_analysis as p
from eq_delivery import Kernel,read

class Point(unittest.TestCase):
 def test_qr_known_overdetermined_solution(self):
  a=[[1,0,0],[0,2,0],[0,0,3],[1,1,1]];c=[2,-3,4];b=[sum(x*y for x,y in zip(row,c)) for row in a]
  for actual,expected in zip(p.fit(a,b),c):self.assertAlmostEqual(actual,expected,places=12)
 def test_rank_deficiency_refused(self):
  with self.assertRaises(ValueError):p.fit([[1,1,1]]*4,[1]*4)
 def test_archived_basis_and_masks(self):
  d=read(ROOT/'delivery/eq/cases/EQ-P01-94048/point-observations.json')['parameters']
  self.assertEqual(p.basis(1,d),[0,0,0]);self.assertEqual(sum(x>0 for x in d['fwtnel']),8);self.assertEqual(sum(x>0 for x in d['fwtpol']),7)
  d['knefnc']=[6]
  with self.assertRaises(ValueError):p.basis(.5,d)
 @unittest.skipUnless(os.environ.get('FYLITE_POINT_KERNEL'),'locked native package required')
 def test_native_constant_field_units_and_sign(self):
  root=Path(os.environ['FYLITE_POINT_KERNEL']);k=Kernel(root,read(root/'kernel.lock.json'))
  n=17;r=[1+i/16 for i in range(n)];z=[-.5+i/16 for i in range(n)];br=-.2
  flux=[-2*math.pi*br*rr*zz for rr in r for zz in z]
  req={'settings':{'nw':n,'nh':n,'r_min':1,'r_max':2,'z_min':-.5,'z_max':.5,'rows':0,'ne0':1e19,'n_samples':401,'length':1},'inputs':{'device':{'fylite:point':{'interferometer':[{'first_point':{'r':1.9,'z':0},'fylite:theta':0}]}},'equilibrium':{'time_slice':{'profiles_2d':{'psi':flux},'global_quantities':{'psi_axis':[-2.0],'psi_boundary':[2.0]}}}}}
  v=p.native(k,req);self.assertGreater(v['chord_nel19'][0],0)
  self.assertAlmostEqual(v['chord_bpolar'][0]/v['chord_nel19'][0],br,places=10)

if __name__=='__main__':unittest.main()
