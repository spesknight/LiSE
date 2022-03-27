from LiSE.examples.polygons import install
from LiSE import Engine


# TODO: use a test sim that does everything in every cache
def test_resume(tempdir):
    with Engine(tempdir) as eng:
        install(eng)
        eng.next_turn()
    with Engine(tempdir) as eng:
        curturn = eng.turn
        eng.next_turn()
        assert eng.turn == curturn + 1
