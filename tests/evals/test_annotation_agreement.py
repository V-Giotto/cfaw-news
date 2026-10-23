"""Arithmetic fixtures are not submissions by people."""

import pytest


def test_weighted_kappa_uses_quadratic_distance_and_reports_counts():
    from evals.intelligence_v1.annotations import agreement_statistic

    value = agreement_statistic([0, 1, 2, 3], [0, 2, 1, 3], [0, 1, 2, 3], weighted=True)
    assert value['count'] == 4 and value['agreement_numerator'] == 2
    assert value['raw_agreement'] == .5
    assert value['kappa'] == pytest.approx(.8)
    assert sum(map(sum, value['confusion_matrix'])) == 4


def test_nominal_kappa_and_missing_or_degenerate_samples_are_explicit():
    from evals.intelligence_v1.annotations import agreement_statistic

    value = agreement_statistic(['focus', 'radar'], ['focus', 'focus'], ['focus', 'radar'])
    assert value['kappa'] == 0 and value['raw_agreement'] == .5
    assert agreement_statistic([], [], [0, 1])['undefined_reason'] == 'no_paired_samples'
    value = agreement_statistic([1, 1], [1, 1], [0, 1, 2, 3], weighted=True)
    assert value['kappa'] is None and value['undefined_reason'] == 'degenerate_expected_agreement'
    with pytest.raises(ValueError):
        agreement_statistic([0], [], [0, 1])
