import json

import pytest

from s7sim.models import DataBlock, PLC, Project, Simulation, Variable, clone, demo_project


def test_project_roundtrip(tmp_path):
    project = demo_project()
    path = tmp_path / "项目.s7sim.json"
    project.save(path)
    loaded = Project.load(path)
    assert loaded == project
    assert loaded.plcs[0].blocks[0].variables[2].simulation.mode == "sine"
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_save_keeps_existing_file(tmp_path):
    path = tmp_path / "test.json"
    project = demo_project()
    project.save(path)
    original = path.read_bytes()
    project.plcs[0].blocks.append(clone(project.plcs[0].blocks[0]))
    with pytest.raises(ValueError):
        project.save(path)
    assert path.read_bytes() == original


def test_invalid_version_and_duplicate_ids(tmp_path):
    path = tmp_path / "test.json"
    path.write_text(json.dumps({"version": 2}))
    with pytest.raises(ValueError, match="版本"):
        Project.load(path)
    project = demo_project()
    project.plcs[0].blocks[1].id = project.plcs[0].blocks[0].id
    with pytest.raises(ValueError, match="ID"):
        project.validate()


@pytest.mark.parametrize("sim,dtype", [
    (Simulation("random", -1, 10), "UINT"),
    (Simulation("random", 100, 0), "REAL"),
    (Simulation("sine"), "BOOL"),
    (Simulation("random"), "STRING"),
    (Simulation("toggle"), "INT"),
    (Simulation("random", float("nan"), 10), "REAL"),
    (Simulation("random", 0.1, 0.9), "INT"),
    (Simulation("random", 0, 1e39), "REAL"),
])
def test_invalid_simulation_rejected(sim, dtype):
    with pytest.raises(ValueError):
        sim.validate(dtype)


def test_plc_limits_and_endpoint_validation():
    project = Project(plcs=[PLC(), PLC()])
    with pytest.raises(ValueError, match="监听"):
        project.validate()
    with pytest.raises(ValueError, match="编号重复"):
        PLC(blocks=[DataBlock(), DataBlock()]).validate()
    with pytest.raises(ValueError):
        PLC(port=0).validate()


def test_wildcard_endpoint_collision():
    project = Project(plcs=[PLC(host="0.0.0.0"), PLC(host="127.0.0.1")])
    with pytest.raises(ValueError, match="监听"):
        project.validate()
