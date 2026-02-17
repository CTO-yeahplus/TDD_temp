from src.app import hello

def test_hello():
    assert hello() == "hello"


from src.app import add

def test_add_basic():
    assert add(1, 2) == 3

def test_add_negative():
    assert add(-1, 1) == 0
