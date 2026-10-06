"""Independent statistical/geometry oracles; only synthetic masks are used.
"""
import numpy as np
import pytest
from scipy import stats
from scipy.spatial.distance import cdist
from oart_analysis import statistics as st, segmentation_metrics as sm

def test_descriptive_statistics():
    x=np.array([0.5,0.7,0.8,0.9,0.65,0.85])
    result=st.describe(x)
    assert result['n']==6
    assert result['mean']==pytest.approx(sum(x)/6)
    sd=np.sqrt(sum((v-x.mean())**2 for v in x)/5)
    assert result['sd']==pytest.approx(sd)
    ci=stats.t.interval(.95,5,loc=x.mean(),scale=sd/np.sqrt(6))
    np.testing.assert_allclose([result['ci_lower'],result['ci_upper']],ci)
    assert result['median']==pytest.approx(np.median(x))


def test_paired_t_and_ci():
    before=np.arange(5,dtype=float)
    after=before+np.arange(1,6)
    result=st.paired_test(before,after)
    oracle=stats.ttest_rel(after,before)
    assert result['difference']['mean']==3
    assert result['difference']['sd']==pytest.approx(np.sqrt(2.5))
    assert result['t']==pytest.approx(4.242640687119285)
    assert result['p']==pytest.approx(oracle.pvalue)
    ci=oracle.confidence_interval()
    np.testing.assert_allclose([result['difference']['ci_lower'],result['difference']['ci_upper']], [ci.low,ci.high])


@pytest.mark.parametrize('p',[[.01,.04,.03,.002],[0,0,1,1],[.2,.2,.01,.05,.9]])
def test_bh_against_scipy(p):
    np.testing.assert_allclose(st.benjamini_hochberg(p),stats.false_discovery_control(np.asarray(p,dtype=float),method='bh'))


@pytest.mark.parametrize('p',[[],[-.1,.2],[.2,1.1],[float('nan'),.1]])
def test_invalid_probabilities_rejected(p):
    with pytest.raises(ValueError): st.benjamini_hochberg(p)


@pytest.mark.parametrize('x',[[1],[],[1,float('nan')],[1,float('inf')],[[1,2],[3,4]]])
def test_invalid_numeric_vectors_rejected(x):
    with pytest.raises(ValueError): st.describe(x)


def test_degenerate_pair_rules():
    result=st.paired_test([1,2,3],[1,2,3])
    assert result['p']==1.0 and result['t']==0.0
    result=st.paired_test([1,2,3],[3,4,5])
    assert result['p']==0.0 and result['t'] is None


def test_pair_length_validation():
    with pytest.raises(ValueError): st.paired_test([1,2],[1,2,3])


@pytest.mark.parametrize('metric',['HD95','ASD'])
def test_distance_orientation(metric):
    assert st.orient_effect(-.5,-.8,-.2,metric)==(.5,.2,.8)


def test_dsc_orientation():
    assert st.orient_effect(.2,.1,.3,'DSC')==(.2,.1,.3)


def test_sample_size():
    result=st.precision_sample_size()
    assert result['evaluable_n']==114
    assert result['recruitment_n']==135


def surface_by_explicit_neighbours(mask):
    # Independent of the module's erosion/distance-transform implementation.
    coords=[]
    for pos_array in np.argwhere(mask):
        pos=tuple(pos_array)
        for axis in range(3):
            boundary=False
            for offset in (-1,1):
                other=list(pos); other[axis]+=offset
                if other[axis]<0 or other[axis]>=mask.shape[axis] or not mask[tuple(other)]:
                    boundary=True; break
            if boundary:
                coords.append(pos); break
    return np.array(coords,float)


def brute_force_oracle(ref,pred,spacing):
    a=surface_by_explicit_neighbours(ref)*np.asarray(spacing)
    b=surface_by_explicit_neighbours(pred)*np.asarray(spacing)
    distances=cdist(a,b)
    pooled=np.r_[distances.min(axis=0),distances.min(axis=1)]
    return dict(DSC=2*np.logical_and(ref,pred).sum()/(ref.sum()+pred.sum()),
                HD95_mm=np.quantile(pooled,.95,method='linear'),ASD_mm=pooled.mean())


def test_identical_cuboids():
    m=np.zeros((8,8,8),bool); m[2:6,2:6,2:6]=True
    result=sm.segmentation_metrics(m,m,(3,.95,.95))
    assert result['DSC']==1 and result['HD95_mm']==0 and result['ASD_mm']==0
    assert result['reference_volume_cm3']==pytest.approx(64*3*.95*.95/1000)


@pytest.mark.parametrize('axis,spacing',[(0,(3,.95,.95)),(1,(3,.95,.95)),(2,(3,.95,.95))])
def test_shifted_single_voxel(axis,spacing):
    ref=np.zeros((7,7,7),bool);pred=ref.copy();ref[2,2,2]=True
    pos=[2,2,2];pos[axis]+=1;pred[tuple(pos)]=True
    result=sm.segmentation_metrics(ref,pred,spacing)
    assert result['DSC']==0
    assert result['HD95_mm']==pytest.approx(spacing[axis])
    assert result['ASD_mm']==pytest.approx(spacing[axis])


@pytest.mark.parametrize('seed',range(10))
def test_geometry_against_independent_bruteforce(seed):
    rng=np.random.default_rng(seed)
    ref=rng.random((5,6,7))>.78
    pred=rng.random((5,6,7))>.85
    spacing=(3,.95,.95)
    result=sm.segmentation_metrics(ref,pred,spacing)
    expected=brute_force_oracle(ref,pred,spacing)
    for key in expected: assert result[key]==pytest.approx(expected[key],rel=1e-12,abs=1e-12)
    reverse=sm.segmentation_metrics(pred,ref,spacing)
    for key in expected: assert result[key]==pytest.approx(reverse[key])


def test_unequal_surface_counts_weighting():
    ref=np.zeros((8,8,8),bool);pred=ref.copy()
    ref[1:5,1:5,1:5]=True;pred[5:7,5:7,5:7]=True
    result=sm.segmentation_metrics(ref,pred,(1,1,1))
    oracle=brute_force_oracle(ref,pred,(1,1,1))
    assert result['reference_surface_points']!=result['prediction_surface_points']
    assert result['ASD_mm']==pytest.approx(oracle['ASD_mm'])
    distances=cdist(surface_by_explicit_neighbours(ref),surface_by_explicit_neighbours(pred))
    unweighted=(distances.min(axis=0).mean()+distances.min(axis=1).mean())/2
    assert abs(unweighted-result['ASD_mm'])>1e-3


def test_bilateral_union():
    a=np.zeros((5,5,5),bool);b=a.copy();a[1,1,1]=True;b[3,3,3]=True
    u=sm.union_masks([a,b])
    assert u.sum()==2
    result=sm.segmentation_metrics(u,a,(1,1,1))
    assert result['DSC']==pytest.approx(2/3)


@pytest.mark.parametrize('which',['reference','prediction','both'])
def test_empty_masks_rejected(which):
    nonempty=np.zeros((4,4,4),bool);nonempty[1,1,1]=True
    empty=np.zeros_like(nonempty)
    ref=empty if which in ('reference','both') else nonempty
    pred=empty if which in ('prediction','both') else nonempty
    with pytest.raises(ValueError,match='Empty mask'): sm.segmentation_metrics(ref,pred,(1,1,1))


@pytest.mark.parametrize('spacing',[(0,1,1),(-1,1,1),(float('nan'),1,1),(1,1)])
def test_invalid_spacing_rejected(spacing):
    m=np.ones((3,3,3),bool)
    with pytest.raises(ValueError): sm.segmentation_metrics(m,m,spacing)


@pytest.mark.parametrize('bad',[np.ones((3,3)),np.full((3,3,3),.5),np.full((3,3,3),np.nan),np.full((3,3,3),2)])
def test_bad_mask_rejected(bad):
    with pytest.raises(ValueError): sm.binary_mask(bad)


def test_grid_mismatch_rejected():
    with pytest.raises(ValueError): sm.segmentation_metrics(np.ones((3,3,3)),np.ones((4,4,4)),(1,1,1))


