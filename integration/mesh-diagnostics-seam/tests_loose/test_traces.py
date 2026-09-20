import numpy as np
import pytest
from cad_mesh_inspector.traces import traces_from_offsets


def test_offsets_make_imported_paths_without_inferred_states():
    paths=traces_from_offsets(np.arange(15.).reshape(5,3),np.array([0,2,5]))
    assert len(paths)==2 and paths[0].status=="unknown" and paths[0].provenance=="imported"

@pytest.mark.parametrize("offsets",[np.array([1,5]),np.array([0,1,5]),np.array([0,6]),np.array([0.,5.])])
def test_bad_offsets(offsets):
    with pytest.raises(ValueError): traces_from_offsets(np.arange(15.).reshape(5,3),offsets)
