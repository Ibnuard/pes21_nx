import copy
import pytest

from test_stage_trophy_ceremony import tables
import stage_trophy_ceremony as trophy
from repair_trophy_file_list import repair_table


def previous_table():
    table = trophy.build_trophy_table(*tables())
    table['cuts'][-1]['variants'][0]['files'] = list(trophy.CORE_FILES[:3]) + ['', trophy.CORE_FILES[3]] + [''] * 5
    return table


def test_repair_changes_only_file_vector_and_is_idempotent():
    old = previous_table()
    before = copy.deepcopy(old)
    result = repair_table(old)
    assert old == before
    assert result['cuts'][-1]['variants'][0]['files'] == list(trophy.CORE_FILES) + [''] * 6
    expected = copy.deepcopy(before)
    expected['cuts'][-1]['variants'][0]['files'] = list(trophy.CORE_FILES) + [''] * 6
    assert result == expected
    assert repair_table(result) == result


@pytest.mark.parametrize('change', [
    lambda t: t.update(kind=1),
    lambda t: t['cuts'][-1].update(name='OTHER'),
    lambda t: t['scenes'][-1].update(name='OTHER'),
    lambda t: t['cuts'][-1]['variants'][0].update(human_mask=1),
    lambda t: t['cuts'][-1]['variants'][0].update(flags=1),
    lambda t: t['cuts'][-1]['variants'][0]['files'].__setitem__(3, 'unreviewed.fdc'),
    lambda t: t['cuts'][-1]['variants'][0]['files'].__setitem__(4, ''),
    lambda t: t['scenes'][-1]['cuts'][0].update(human_changes=[]),
])
def test_repair_refuses_unreviewed_input(change):
    table = previous_table()
    change(table)
    with pytest.raises(ValueError):
        repair_table(table)
