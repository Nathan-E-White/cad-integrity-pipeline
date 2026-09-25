import pytest

from cad_integrity.session_admission import SessionAdmission, SessionBusy


def test_same_session_is_exclusive_across_routes_but_other_sessions_can_run():
    guard = SessionAdmission()
    with guard.admit("browser-a"):
        with pytest.raises(SessionBusy):
            with guard.admit("browser-a"):
                pytest.fail("overlapping route entered")
        with guard.admit("browser-b"):
            pass
    with guard.admit("browser-a"):
        pass


def test_failure_and_abandoned_generator_release_admission():
    guard = SessionAdmission()
    with pytest.raises(RuntimeError, match="compute failed"):
        with guard.admit("a"):
            raise RuntimeError("compute failed")
    with guard.admit("a"):
        pass


def test_simultaneous_requests_admit_exactly_one():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Event

    guard = SessionAdmission()
    barrier, release = Barrier(3), Event()

    def start():
        barrier.wait()
        try:
            with guard.admit("a"):
                release.wait(2)
                return "admitted"
        except SessionBusy:
            release.set()
            return "busy"

    with ThreadPoolExecutor(2) as pool:
        a, b = pool.submit(start), pool.submit(start)
        barrier.wait()
        assert sorted([a.result(), b.result()]) == ["admitted", "busy"]


def test_abandoned_stream_releases_guard_without_affecting_another_session():
    guard = SessionAdmission()

    def stream():
        with guard.admit("a"):
            yield "cleared"
            yield "finished"

    running = stream()
    assert next(running) == "cleared"
    with pytest.raises(SessionBusy):
        with guard.admit("a"):
            pass
    running.close()
    with guard.admit("a"):
        pass


def test_session_identity_is_required():
    with pytest.raises(ValueError, match="session"):
        with SessionAdmission().admit(""):
            pass


@pytest.mark.parametrize("overlap", ["run_example", "run_upload", "run_step"])
def test_installed_routes_share_admission_and_clear_only_after_admission(overlap):
    import gradio as gr

    from cad_integrity.gradio_app import build_app

    app = build_app(inspection_enabled=True)
    routes = {fn.api_name: fn.fn for fn in app.fns.values()}
    arguments = {
        "run_example": ("00_clean_boss",),
        "run_upload": (None, False, 0.01, 0.1, False),
        "run_step": (None, 0.001, 0.01, 1, False, 0.1, 0.1, False),
    }
    request = gr.Request(session_hash="same-browser")
    active = routes["run_example"](*arguments["run_example"], request)
    cleared = next(active)
    assert all(control["interactive"] is False for control in cleared[-3:])
    rejected = routes[overlap](*arguments[overlap], request)
    with pytest.raises(gr.Error, match="active computation"):
        next(rejected)
    active.close()
    retry = routes["run_upload"](*arguments["run_upload"], request)
    assert next(retry)[-1]["interactive"] is False
    failed = next(retry)
    assert all(not control["interactive"] for control in failed[-3:])
    assert all(control["interactive"] for control in next(retry)[-3:])
    assert failed[10]["meshes"] == []
    with pytest.raises(StopIteration):
        next(retry)


def test_delivery_failure_restores_controls_and_clears_inspection(monkeypatch):
    import gradio as gr

    import cad_integrity.gradio_app as parent

    encode = parent.encode_inspection

    def broken(snapshot):
        if snapshot is not None:
            raise ValueError("delivery failed")
        return encode(None)

    monkeypatch.setattr(parent, "encode_inspection", broken)
    app = parent.build_app(inspection_enabled=True)
    route = next(fn.fn for fn in app.fns.values() if fn.api_name == "run_example")
    stream = route("00_clean_boss", gr.Request(session_hash="browser"))
    next(stream)
    result = next(stream)
    assert result[10]["meshes"] == []
    assert result[7] is not None
    assert result[9] is not None
    assert result[11] is not None
    assert "delivery failed" in result[0]
    assert all(not control["interactive"] for control in result[-3:])
    assert all(control["interactive"] for control in next(stream)[-3:])
    stream.close()


def test_run_setup_collapses_only_when_a_result_reaches_the_shared_workspace():
    import gradio as gr

    from cad_integrity.gradio_app import build_app

    app = build_app(inspection_enabled=True)
    routes = {fn.api_name: fn.fn for fn in app.fns.values()}

    example = routes["run_example"]("00_clean_boss", gr.Request(session_hash="success"))
    assert "open" not in next(example)[-4]
    assert next(example)[-4]["open"] is False
    next(example)

    rejected = routes["run_example"](
        "02_pinched_vertex", gr.Request(session_hash="rejected")
    )
    assert "open" not in next(rejected)[-4]
    assert next(rejected)[-4]["open"] is True
    next(rejected)

    upload = routes["run_upload"](
        None, False, 0.01, 0.1, False, gr.Request(session_hash="failure")
    )
    assert "open" not in next(upload)[-4]
    assert next(upload)[-4]["open"] is True
    next(upload)
