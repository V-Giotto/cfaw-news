"""Primary-cohort completeness is a requirement separate from partial reports."""

import pytest
from test_loader import loaded

from evals.intelligence_v1.exceptions import ContractError


def test_pr5_matrix_rejects_missing_algorithms_or_repetitions(bundle, tmp_path):
    from evals.intelligence_v1.acceptance import verify_matrix

    data = loaded(bundle)
    with pytest.raises(ContractError, match='REPRODUCTION_MATRIX_INCOMPLETE'):
        verify_matrix({'cohorts': []}, data, tmp_path)
    with pytest.raises(ContractError, match='PRIMARY_COHORT_INCOMPLETE'):
        verify_matrix({'cohorts': [{'algorithm_id': 'b1', 'label_source': 'gold',
            'experiment': {'budget_seconds_override': 420, 'half_life_days': 7},
            'steps': [], 'replicates_by_step': {}}]}, data, tmp_path)
