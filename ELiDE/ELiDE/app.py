# This file is part of LiSE, a framework for life simulation games.
# Copyright (C) 2013-2014 Zachary Spector, ZacharySpector@gmail.com
import json

from kivy.logger import Logger
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.resources import resource_add_path

from kivy.uix.screenmanager import ScreenManager

from kivy.properties import (
    ObjectProperty,
    NumericProperty,
    ReferenceListProperty,
    StringProperty
)
import LiSE
from LiSE.proxy import EngineProcessManager
import ELiDE
import ELiDE.screen
import ELiDE.stringsed
import ELiDE.funcsed
import ELiDE.statcfg
import ELiDE.spritebuilder
import ELiDE.rulesview
import ELiDE.charsview
from .util import trigger

"""Object to configure, start, and stop ELiDE."""

resource_add_path(ELiDE.__path__[0] + "/assets")
resource_add_path(ELiDE.__path__[0] + "/assets/rltiles")


class ELiDEApp(App):
    """Extensible LiSE Development Environment.

    """
    engine = ObjectProperty()
    branch = StringProperty()
    tick = NumericProperty()
    time = ReferenceListProperty(branch, tick)
    character = ObjectProperty()

    @trigger
    def pull_time(self, *args):
        self.time = self.engine.time

    def on_time(self, *args):
        local_time = list(self.time)
        if local_time != self.engine.time:
            self.engine.time = local_time

    def set_branch(self, b):
        """Set my branch to the given value."""
        self.branch = b

    def set_tick(self, t):
        """Set my tick to the given value, cast to an integer."""
        self.tick = int(t)

    def set_time(self, b, t=None):
        if t is None:
            (b, t) = b
        t = int(t)
        self.time = (b, t)

    def select_character(self, char):
        """Change my ``character`` to the selected character object if they
        aren't the same.

        """
        if char == self.character:
            return
        self.character = char

    def build_config(self, config):
        """Set config defaults"""
        for sec in 'LiSE', 'ELiDE':
            config.adddefaultsection(sec)
        config.setdefaults(
            'LiSE',
            {
                'world': 'sqlite:///LiSEworld.db',
                'code': 'LiSEcode.db',
                'language': 'en',
                'logfile': '',
                'loglevel': 'info'
            }
        )
        config.setdefaults(
            'ELiDE',
            {
                'boardchar': 'physical',
                'debugger': 'no',
                'inspector': 'no',
                'user_kv': 'yes',
                'play_speed': '1',
                'thing_graphics': json.dumps([
                    ("Marsh Davies' Island", 'marsh_davies_island_fg.atlas'),
                    ('RLTiles: Body', 'base.atlas'),
                    ('RLTiles: Basic clothes', 'body.atlas'),
                    ('RLTiles: Armwear', 'arm.atlas'),
                    ('RLTiles: Legwear', 'leg.atlas'),
                    ('RLTiles: Right hand', 'hand1.atlas'),
                    ('RLTiles: Left hand', 'hand2.atlas'),
                    ('RLTiles: Boots', 'boot.atlas'),
                    ('RLTiles: Hair', 'hair.atlas'),
                    ('RLTiles: Beard', 'beard.atlas'),
                    ('RLTiles: Headwear', 'head.atlas')
                ]),
                'place_graphics': json.dumps([
                    ("Marsh Davies' Island", 'marsh_davies_island_bg.atlas'),
                    ("Marsh Davies' Crypt", 'marsh_davies_crypt.atlas'),
                    ('RLTiles: Dungeon', 'dungeon.atlas')
                ])
            }
        )
        config.write()

    def build(self):
        """Make sure I can use the database, create the tables as needed, and
        return the root widget.

        """
        config = self.config
        Logger.debug(
            "ELiDEApp: starting with world {}, code {}, path {}".format(
                config['LiSE']['world'],
                config['LiSE']['code'],
                LiSE.__path__[-1]
            )
        )

        if config['ELiDE']['debugger'] == 'yes':
            import pdb
            pdb.set_trace()
        self.manager = EngineProcessManager()
        enkw = {}
        if 'logfile' in config['LiSE']:
            enkw['logfile'] = config['LiSE']['logfile']
        if 'loglevel' in config['LiSE']:
            enkw['loglevel'] = config['LiSE']['loglevel']
        self.engine = self.manager.start(
            config['LiSE']['world'],
            config['LiSE']['code'],
            **enkw
        )
        self.pull_time()

        Clock.schedule_interval(lambda dt: self.manager.sync_log(), 0.1)
        char = config['ELiDE']['boardchar']
        if char not in self.engine.character:
            self.engine.add_character(char)

        s = ScreenManager()

        def toggler(screenname):
            def tog(*args):
                if s.current == screenname:
                    s.current = 'main'
                else:
                    s.current = screenname
            return tog

        pawncfg = ELiDE.spritebuilder.PawnConfigScreen(
            toggle=toggler('pawncfg'),
            data=json.loads(config['ELiDE']['thing_graphics'])
        )

        spotcfg = ELiDE.spritebuilder.SpotConfigScreen(
            toggle=toggler('spotcfg'),
            data=json.loads(config['ELiDE']['place_graphics'])
        )

        rules = ELiDE.rulesview.RulesScreen(
            engine=self.engine,
            toggle=toggler('rules')
        )

        chars = ELiDE.charsview.CharactersScreen(
            toggle=toggler('chars'),
            select_character=self.select_character,
            engine=self.engine
        )

        strings = ELiDE.stringsed.StringsEdScreen(
            engine=self.engine,
            toggle=toggler('strings')
        )

        funcs = ELiDE.funcsed.FuncsEdScreen(
            table='trigger',
            store=self.engine.trigger,
            toggle=toggler('funcs')
        )
        funcs.bind(data=rules.rulesview._trigger_update_builders)

        self.select_character(
            self.engine.character[
                config['ELiDE']['boardchar']
            ]
        )

        stat_cfg = ELiDE.statcfg.StatScreen(
            json_loader=self.engine.json_load,
            remote=self.character.stat,
            toggle=toggler('stat_cfg'),
            time=self.time
        )
        self.bind(time=stat_cfg.setter('time'))

        self.mainscreen = ELiDE.screen.MainScreen(
            app=self,
            engine=self.engine,
            character=self.character,
            use_kv=config['ELiDE']['user_kv'] == 'yes',
            play_speed=int(config['ELiDE']['play_speed']),
            time=self.time,
            set_branch=self.set_branch,
            set_tick=self.set_tick,
            set_time=self.set_time,
            select_character=self.select_character,
            pawn_cfg=pawncfg,
            spot_cfg=spotcfg,
            stat_cfg=stat_cfg,
            rules=rules,
            chars=chars,
            strings=strings,
            funcs=funcs
        )
        for wid in (self.mainscreen, pawncfg, spotcfg, stat_cfg, rules, chars, strings, funcs):
            s.add_widget(wid)
        s.bind(current=self.mainscreen.setter('current'))
        self.bind(
            character=self.mainscreen.setter('character'),
            time=self.mainscreen.setter('time')
        )
        if config['ELiDE']['inspector'] == 'yes':
            from kivy.core.window import Window
            from kivy.modules import inspector
            inspector.create_inspector(Window, self.mainscreen)

        return s

    def on_character_name(self, *args):
        if self.config['ELiDE']['boardchar'] != self.character_name:
            self.config['ELiDE']['boardchar'] = self.character_name

    def on_pause(self):
        """Sync the database with the current state of the game."""
        self.engine.commit()
        self.config.write()

    def on_stop(self, *largs):
        """Sync the database, wrap up the game, and halt."""
        self.manager.shutdown()
        self.config.write()


kv = """
<SymbolLabel@Label>:
    font_name: "Symbola.ttf"
    font_size: 50
<SymbolButton@Button>:
    font_name: "Symbola.ttf"
    font_size: 50
"""
Builder.load_string(kv)
