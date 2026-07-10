from io import BytesIO

import pytest


pytest.importorskip('onnxruntime')
onnx = pytest.importorskip('onnx')

import numpy as np  # noqa: E402
from onnx import TensorProto  # noqa: E402
from onnx import helper  # noqa: E402
from onnx import numpy_helper  # noqa: E402
from PIL import Image  # noqa: E402

from szurubooru_toolkit.deepbooru import Deepbooru  # noqa: E402


TAGS = ['solo', 'other_tag', 'multiple girls', 'rating:explicit']

# The model averages the image color channels and multiplies with this matrix,
# so a solid-color image deterministically selects one row as the tag scores.
# Red image -> row 0, green -> row 1, blue -> row 2.
WEIGHTS = np.array(
    [
        [0.9, 0.1, 0.8, 0.95],  # red: solo, multiple girls + rating:explicit
        [0.0, 0.0, 0.0, 0.0],  # green: nothing
        [0.1, 0.2, 0.3, 0.4],  # blue: nothing above default threshold
    ],
    dtype=np.float32,
)


def build_model(path) -> None:
    nodes = [
        helper.make_node('ReduceMean', ['input'], ['pooled'], axes=[1, 2], keepdims=0),
        helper.make_node('MatMul', ['pooled', 'weights'], ['output']),
    ]
    graph = helper.make_graph(
        nodes,
        'fake_deepbooru',
        [helper.make_tensor_value_info('input', TensorProto.FLOAT, [None, 512, 512, 3])],
        [helper.make_tensor_value_info('output', TensorProto.FLOAT, [None, len(TAGS)])],
        [numpy_helper.from_array(WEIGHTS, name='weights')],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
    model.ir_version = 8
    onnx.save(model, str(path))


def make_image(color: tuple) -> bytes:
    buffer = BytesIO()
    Image.new('RGB', (64, 64), color=color).save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture(scope='module')
def model_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp('deepbooru')
    build_model(path / 'model.onnx')
    (path / 'tags.txt').write_text('\n'.join(TAGS) + '\n')
    return path


@pytest.fixture(scope='module')
def deepbooru(model_dir):
    return Deepbooru(str(model_dir / 'model.onnx'))


def test_tags_above_threshold_with_rating(deepbooru):
    tags, rating = deepbooru.tag_image(make_image((255, 0, 0)), 'safe', threshold=0.7, set_tag=False)

    # rating:explicit is consumed as the rating, whitespace tag gets underscored
    assert sorted(tags) == ['multiple_girls', 'solo']
    assert rating == 'unsafe'


def test_set_tag_adds_deepbooru(deepbooru):
    tags, _ = deepbooru.tag_image(make_image((255, 0, 0)), 'safe', threshold=0.7, set_tag=True)

    assert 'deepbooru' in tags


def test_no_tags_above_threshold_falls_back_to_default(deepbooru):
    tags, rating = deepbooru.tag_image(make_image((0, 0, 255)), 'sketchy', threshold=0.7, set_tag=False)

    assert tags == []
    assert rating == 'sketchy'


def test_threshold_is_respected(deepbooru):
    tags, _ = deepbooru.tag_image(make_image((255, 0, 0)), 'safe', threshold=0.85, set_tag=False)

    # Only solo (0.9) and rating:explicit (0.95) clear 0.85; multiple girls (0.8) doesn't
    assert tags == ['solo']


def test_invalid_image_returns_none(deepbooru):
    assert deepbooru.tag_image(b'not-an-image', 'safe') is None


def test_h5_path_uses_converted_sibling(model_dir):
    # A configured .h5 path must pick up the already converted .onnx next to it
    (model_dir / 'model.h5').write_bytes(b'fake keras model')

    deepbooru = Deepbooru(str(model_dir / 'model.h5'))
    tags, rating = deepbooru.tag_image(make_image((255, 0, 0)), 'safe', threshold=0.7, set_tag=False)

    assert rating == 'unsafe'


def test_h5_without_conversion_exits(tmp_path):
    # No sibling .onnx and no tensorflow installed: must exit with instructions
    (tmp_path / 'model.h5').write_bytes(b'fake keras model')
    (tmp_path / 'tags.txt').write_text('solo\n')

    with pytest.raises(SystemExit):
        Deepbooru(str(tmp_path / 'model.h5'))
