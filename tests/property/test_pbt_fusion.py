from hypothesis import given
from hypothesis import strategies as st

from audit.domain.models import L3Result, LayerResult
from audit.pipeline.l4_fusion import fuse


def _layer(score: float) -> LayerResult:
    return LayerResult(score=score, hits=[], elapsed_ms=0)


@given(
    l1=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
    l2=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
    l3=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
)
def test_fusion_risk_level_is_monotonic_when_any_layer_score_increases(l1, l2, l3):
    order = {"合规": 0, "提示": 1, "警告": 2, "违规": 3}
    baseline = fuse(_layer(l1), _layer(l2), L3Result(score=l3, hits=[], elapsed_ms=0))
    increased = fuse(_layer(max(l1, 1.0)), _layer(l2), L3Result(score=l3, hits=[], elapsed_ms=0))

    assert order[increased.risk_level.value] >= order[baseline.risk_level.value]


@given(score=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False))
def test_fusion_confidence_stays_in_unit_interval(score):
    decision = fuse(_layer(score), _layer(0.0), L3Result(score=0.0, hits=[], elapsed_ms=0))

    assert 0.0 <= decision.confidence_score <= 1.0
