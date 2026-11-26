import agentlab


def test_agentlab_package_is_importable():
    assert agentlab.__name__ == "agentlab"
    assert agentlab.__file__ is not None