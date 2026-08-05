from media_redact.detect.face.onnx_utils import _dim_to_int, parse_model_input_size


def test_dim_to_int():
    assert _dim_to_int(320) == 320
    assert _dim_to_int("640") == 640
    assert _dim_to_int("height") is None
    assert _dim_to_int(0) is None


class _FakeInput:
    def __init__(self, shape):
        self.shape = shape


class _FakeSession:
    def __init__(self, shape):
        self._inputs = [_FakeInput(shape)]

    def get_inputs(self):
        return self._inputs


def test_parse_model_input_size_from_session():
    session = _FakeSession([1, 3, 320, 320])
    width, height = parse_model_input_size("dummy.onnx", session)
    assert (width, height) == (320, 320)
