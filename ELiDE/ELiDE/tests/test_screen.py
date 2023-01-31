from types import SimpleNamespace

from kivy.base import EventLoop
from kivy.tests.common import UnitTestTouch

from LiSE import Engine
from LiSE.character import Facade
from ELiDE.menu import DirPicker
from ELiDE.screen import MainScreen
from ELiDE.spritebuilder import PawnConfigScreen, SpotConfigScreen
from ELiDE.statcfg import StatScreen
from ELiDE.graph.board import GraphBoard
from ELiDE.grid.board import GridBoard
from .util import ELiDEAppTest, ListenableDict, MockEngine, idle_until, \
 window_with_widget


class MockStore:

	def save(self, *args):
		pass


class ScreenTest(ELiDEAppTest):

	def test_advance_time(self):
		app = self.app
		app.mainmenu = DirPicker()
		app.spotcfg = SpotConfigScreen()
		app.pawncfg = PawnConfigScreen()
		app.statcfg = StatScreen()
		char = Facade()
		char.name = 'physical'
		app.character = char
		app.engine = MockEngine()
		app.strings = MockStore()
		app.funcs = MockStore()
		char.character = SimpleNamespace(engine=app.engine)
		app.engine.character['physical'] = char
		entity = ListenableDict()
		entity.engine = app.engine
		entity.name = 'name'
		app.selected_proxy = app.proxy = app.statcfg.proxy = entity
		screen = MainScreen(
			graphboards={'physical': GraphBoard(character=char)},
			gridboards={'physical': GridBoard(character=char)})
		win = window_with_widget(screen)
		idle_until(lambda: 'timepanel' in screen.ids, 100,
					"timepanel never got id")
		timepanel = screen.ids['timepanel']
		idle_until(lambda: timepanel.size != [100, 100], 100,
					"timepanel never resized")
		turnfield = timepanel.ids['turnfield']
		turn_before = int(turnfield.hint_text)
		stepbut = timepanel.ids['stepbut']
		motion = UnitTestTouch(*stepbut.center)
		motion.touch_down()
		motion.touch_up()
		EventLoop.idle()
		assert int(turnfield.hint_text) == turn_before + 1

	def test_play(self):
		app = self.app
		app.spotcfg = SpotConfigScreen()
		app.pawncfg = PawnConfigScreen()
		app.statcfg = StatScreen()
		app.mainmenu = DirPicker()
		app.strings = MockStore()
		app.funcs = MockStore()
		char = Facade()
		char.name = 'foo'
		app.character = char
		app.engine = MockEngine()
		char.character = SimpleNamespace(engine=app.engine)
		app.engine.character['foo'] = char
		entity = ListenableDict()
		entity.engine = app.engine
		entity.name = 'name'
		app.selected_proxy = app.proxy = app.statcfg.proxy = entity
		screen = MainScreen(graphboards={'foo': GraphBoard(character=char)},
							gridboards={'foo': GridBoard(character=char)},
							play_speed=1.0)
		win = window_with_widget(screen)
		idle_until(lambda: 'timepanel' in screen.ids, 100,
					"timepanel never got id")
		timepanel = screen.ids['timepanel']
		idle_until(lambda: timepanel.size != [100, 100], 100,
					"timepanel never resized")
		turnfield = timepanel.ids['turnfield']
		turn_before = int(turnfield.hint_text)
		playbut = timepanel.ids['playbut']
		motion = UnitTestTouch(*playbut.center)
		motion.touch_down()
		motion.touch_up()
		idle_until(lambda: int(turnfield.hint_text) == 3, 400,
					"Time didn't advance fast enough")

	def test_update(self):
		with Engine(self.prefix) as eng:
			phys = eng.new_character('physical')
			here = phys.new_place((0, 0))
			phys.add_place((1, 1))
			phys.add_place(9)  # test that gridboard can handle this
			this = here.new_thing(2)
			@this.rule(always=True)
			def go(me):
				me["location"] = (1, 1)
		app = self.app
		app.starting_dir = self.prefix
		app.build()
		idle_until(lambda: app.engine is not None, 100, "Never got engine proxy")
		assert app.engine.character['physical'].thing[2]['location'] == (0, 0)
		graphboard = app.mainscreen.graphboards['physical']
		gridboard = app.mainscreen.gridboards['physical']
		idle_until(lambda: graphboard.size != [100, 100], 100, "Never resized graphboard")
		idle_until(lambda: gridboard.size != [100, 100], 100, "Never resized gridboard")
		idle_until(lambda: (0, 0) in graphboard.spot, 100, "Never made spot for location 0")
		locspot0 = graphboard.spot[0, 0]
		gridspot0 = gridboard.spot[0, 0]
		locspot1 = graphboard.spot[1, 1]
		gridspot1 = gridboard.spot[1, 1]
		graphpawn = graphboard.pawn[2]
		gridpawn = gridboard.pawn[2]
		idle_until(lambda: graphpawn.x == locspot0.right, 100, "Never positioned pawn to 0's right")
		idle_until(lambda: graphpawn.y == locspot0.top, 100, "Never positioned pawn to 0's top")
		idle_until(lambda: gridpawn.pos == gridspot0.pos, 100, "Never positioned pawn to grid 0, 0")
		app.mainscreen.next_turn()
		assert app.engine.character['physical'].thing[2]['location'] == (1, 1)
		idle_until(lambda: graphpawn.x == locspot1.right, 100, "Never positioned pawn to 1's right")
		idle_until(lambda: graphpawn.y == locspot1.top, 100, "Never positioned pawn to 1's top")
		idle_until(lambda: gridpawn.pos == gridspot1.pos, 100, "Never positioned pawn to grid 1, 1")
