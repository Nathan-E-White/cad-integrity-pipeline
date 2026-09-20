import io
import zipfile
import numpy as np
import pytest
from cad_mesh_inspector.npz_io import load_numeric_npz
from cad_mesh_inspector.traces import traces_from_offsets


def test_numeric_npz_aliases(tmp_path):
    p=tmp_path/"mesh.npz";np.savez_compressed(p,vertices=np.zeros((3,3)),faces=np.array([[0,1,2]]))
    data=load_numeric_npz(p)
    assert set(data)=={"positions","triangles"}


def test_pickle_object_rejected(tmp_path):
    p=tmp_path/"object.npz";np.savez(p,vertices=np.array([{"unsafe":1}],dtype=object),faces=np.empty((0,3),dtype=int))
    with pytest.raises(ValueError,match="numeric"):load_numeric_npz(p)


def test_bad_header_shape_before_allocation(tmp_path):
    p=tmp_path/"bad.npz";header=io.BytesIO()
    np.lib.format.write_array_header_1_0(header,{"descr":"<f8","fortran_order":False,"shape":(1_000_000_000,3)})
    with zipfile.ZipFile(p,"w") as archive:archive.writestr("vertices.npy",header.getvalue())
    with pytest.raises(ValueError,match="header shape"):load_numeric_npz(p)


def test_ambiguous_keys_rejected(tmp_path):
    p=tmp_path/"mesh.npz";np.savez(p,vertices=np.zeros((3,3)),positions=np.zeros((3,3)),faces=np.array([[0,1,2]]))
    with pytest.raises(ValueError,match="exactly one"):load_numeric_npz(p)


def test_unexpected_member_rejected(tmp_path):
    p=tmp_path/"mesh.npz"
    with zipfile.ZipFile(p,"w") as archive:archive.writestr("../../vertices.npy",b"no")
    with pytest.raises(ValueError,match="Unexpected"):load_numeric_npz(p)


def test_truncated_file_raises(tmp_path):
    p=tmp_path/"mesh.npz";p.write_bytes(b"broken")
    with pytest.raises(zipfile.BadZipFile):load_numeric_npz(p)


def test_offsets_make_imported_paths_without_inferred_states():
    paths=traces_from_offsets(np.arange(15.).reshape(5,3),np.array([0,2,5]))
    assert len(paths)==2 and paths[0].status=="unknown" and paths[0].provenance=="imported"

@pytest.mark.parametrize("offsets",[np.array([1,5]),np.array([0,1,5]),np.array([0,6]),np.array([0.,5.])])
def test_bad_offsets(offsets):
    with pytest.raises(ValueError): traces_from_offsets(np.arange(15.).reshape(5,3),offsets)
