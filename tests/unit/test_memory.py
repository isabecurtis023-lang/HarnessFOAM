from harnessfoam.memory import DEFAULT_TOKEN_LIMITS, initialize_memory, read_memory, record_event

def test_memory_is_off_by_default(tmp_path):
    assert initialize_memory(str(tmp_path)) == []
    assert not (tmp_path / '.harnessfoam').exists()

def test_memory_creates_all_agents_and_compresses(tmp_path):
    initialize_memory(str(tmp_path), enabled=True, limits={'architect': 256})
    assert len(list((tmp_path / '.harnessfoam' / 'memory').glob('*.md'))) == len(DEFAULT_TOKEN_LIMITS)
    record_event(str(tmp_path), 'architect', outcome='error', details='bad ' * 1000, enabled=True, limits={'architect': 256})
    assert len(read_memory(str(tmp_path), 'architect', enabled=True, limits={'architect': 256}).split()) <= 256
