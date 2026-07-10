from io import BytesIO

import pytest


pytest.importorskip('onnxruntime')
onnx = pytest.importorskip('onnx')

import numpy as np  # noqa: E402
from onnx import TensorProto  # noqa: E402
from onnx import helper  # noqa: E402
from onnx import numpy_helper  # noqa: E402
from PIL import Image  # noqa: E402

from szurubooru_toolkit.wdtagger import WDTagger  # noqa: E402


INPUT_SIZE = 448

# selected_tags.csv rows: general tags (category 0), a character tag (category 4)
# and the four rating tags (category 9)
TAGS_CSV = """tag_id,name,category,count
0,solo,0,100
1,long_hair,0,100
2,hatsune_miku,4,100
3,general,9,100
4,sensitive,9,100
5,questionable,9,100
6,explicit,9,100
"""

# The model averages the BGR pixel values (0-255) per channel and multiplies with
# this matrix (scaled by /255), so a solid-color image deterministically selects one
# row as the tag scores. The input is BGR: a red RGB image selects row 2, a green
# image row 1 and a blue image row 0.
#                      solo  hair  miku  gen  sens  ques  expl
WEIGHTS = np.array(
    [
        [0.1, 0.5, 0.6, 0.05, 0.1, 0.2, 0.9],  # blue: long_hair, miku below char threshold, explicit
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # green: nothing
        [0.9, 0.2, 0.95, 0.8, 0.1, 0.05, 0.02],  # red: solo + miku, rating general
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
        'fake_wd_tagger',
        [helper.make_tensor_value_info('input', TensorProto.FLOAT, [None, INPUT_SIZE, INPUT_SIZE, 3])],
        [helper.make_tensor_value_info('output', TensorProto.FLOAT, [None, WEIGHTS.shape[1]])],
        [numpy_helper.from_array(WEIGHTS / 255.0, name='weights')],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
    model.ir_version = 8
    onnx.save(model, str(path))


def make_image(color: tuple, size: tuple = (64, 64), mode: str = 'RGB') -> bytes:
    buffer = BytesIO()
    Image.new(mode, size, color=color).save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture(scope='module')
def model_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp('wdtagger')
    build_model(path / 'model.onnx')
    (path / 'selected_tags.csv').write_text(TAGS_CSV)
    return path


@pytest.fixture(scope='module')
def wd_tagger(model_dir):
    return WDTagger(str(model_dir))


def test_input_size_from_model(wd_tagger):
    assert wd_tagger.input_size == INPUT_SIZE


def test_general_and_character_tags_with_rating(wd_tagger):
    tags, rating = wd_tagger.tag_image(make_image((255, 0, 0)), 'safe', set_tag=False)

    # solo (0.9) clears the general threshold, long_hair (0.2) doesn't,
    # hatsune_miku (0.95) clears the character threshold
    assert sorted(tags) == ['hatsune_miku', 'solo']
    assert rating == 'safe'


def test_character_threshold_is_respected(wd_tagger):
    tags, rating = wd_tagger.tag_image(make_image((0, 0, 255)), 'safe', set_tag=False)

    # hatsune_miku (0.6) clears the general threshold but not the character threshold
    assert tags == ['long_hair']
    assert rating == 'unsafe'


def test_character_threshold_can_be_lowered(wd_tagger):
    tags, _ = wd_tagger.tag_image(make_image((0, 0, 255)), 'safe', character_threshold=0.5, set_tag=False)

    assert 'hatsune_miku' in tags


def test_set_tag_adds_wd_tagger(wd_tagger):
    tags, _ = wd_tagger.tag_image(make_image((255, 0, 0)), 'safe', set_tag=True)

    assert 'wd_tagger' in tags


def test_no_tags_above_threshold_keeps_rating(wd_tagger):
    tags, rating = wd_tagger.tag_image(make_image((0, 255, 0)), 'sketchy', set_tag=False)

    # All scores are zero: no tags, the rating argmax defaults to the first rating tag (general)
    assert tags == []
    assert rating == 'safe'


def test_invalid_image_falls_back_to_default(wd_tagger):
    tags, rating = wd_tagger.tag_image(b'not-an-image', 'sketchy')

    assert tags == []
    assert rating == 'sketchy'


def test_non_square_image_is_padded(wd_tagger):
    # A blue landscape image is padded with white; the blue channel mean stays at 255,
    # so the blue row still dominates the scores
    tags, rating = wd_tagger.tag_image(make_image((0, 0, 255), size=(448, 224)), 'safe', set_tag=False)

    assert 'long_hair' in tags
    assert rating == 'unsafe'


def test_rgba_image_is_composited(wd_tagger):
    tags, rating = wd_tagger.tag_image(make_image((255, 0, 0, 255), mode='RGBA'), 'safe', set_tag=False)

    assert sorted(tags) == ['hatsune_miku', 'solo']
    assert rating == 'safe'


def test_unavailable_provider_falls_back_to_cpu(model_dir):
    wd_tagger = WDTagger(str(model_dir), providers=['BogusExecutionProvider'])

    assert wd_tagger.session.get_providers() == ['CPUExecutionProvider']
    _, rating = wd_tagger.tag_image(make_image((0, 0, 255)), 'safe', set_tag=False)
    assert rating == 'unsafe'
