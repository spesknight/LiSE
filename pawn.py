# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013 Zachary Spector,  zacharyspector@gmail.com
from util import (
    SaveableMetaclass,
    TerminableImg,
    TerminableInteractivity,
    BranchTicksIter,
    LoadError,
    TabdictIterator)
from collections import defaultdict
from pyglet.sprite import Sprite
from pyglet.graphics import OrderedGroup
from pyglet.gl import GL_LINES
from logging import getLogger


logger = getLogger(__name__)


__metaclass__ = SaveableMetaclass


"""Widget representing things that move about from place to place."""


class Pawn(TerminableImg, TerminableInteractivity):
    """A token to represent something that moves about between places."""
    tables = [
        ("pawn_img",
         {"dimension": "text not null default 'Physical'",
          "board": "integer not null default 0",
          "thing": "text not null",
          "branch": "integer not null default 0",
          "tick_from": "integer not null default 0",
          "tick_to": "integer default null",
          "img": "text not null default 'default_pawn'"},
         ("dimension", "board", "thing", "tick_from"),
         {"dimension, board": ("board", "dimension, i"),
          "dimension, thing": ("thing_location", "dimension, name"),
          "img": ("img", "name")},
         []),
        ("pawn_interactive",
         {"dimension": "text not null default 'Physical'",
          "board": "integer not null default 0",
          "thing": "text not null",
          "branch": "integer not null default 0",
          "tick_from": "integer not null default 0",
          "tick_to": "integer default null"},
         ("dimension", "board", "thing", "tick_from"),
         {"dimension, board": ("board", "dimension, i"),
          "dimension, thing": ("thing_location", "dimension, name")},
         [])]
    loaded_keys = set()

    def __init__(self, rumor, dimn, boardi, thingn, td):
        """Return a pawn on the board for the given dimension, representing
the given thing with the given image. It may be visible or not,
interactive or not.

        """
        if (dimn, boardi, thingn) in Pawn.loaded_keys:
            raise LoadError("Pawn already loaded: {0}[{1}].{2}".format(dimn, boardi, thingn))
        else:
            Pawn.loaded_keys.add((dimn, boardi, thingn))
        self.rumor = rumor
        self._tabdict = td
        self._dimn = dimn
        self._boardi = boardi
        self._thingn = thingn
        self.imagery = defaultdict(dict)
        self.indefinite_imagery = {}
        self.interactivity = defaultdict(dict)
        self.indefinite_interactivity = {}
        imgns = set()
        for rd in TabdictIterator(self._tabdict["pawn_img"]):
            imgns.add(rd["img"])
        self.imgdict = self.rumor.get_imgs(imgns)
        for rd in TabdictIterator(self._tabdict["pawn_img"]):
            self.set_img(self.imgdict[rd["img"]],
                         rd["branch"],
                         rd["tick_from"],
                         rd["tick_to"])
        for rd in TabdictIterator(self._tabdict["pawn_interactive"]):
            self.set_interactive(rd["branch"], rd["tick_from"], rd["tick_to"])
        self.grabpoint = None
        self.sprite = None
        self.oldstate = None
        self.tweaks = 0
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.selectable = True
        self.vertlist = None

    def __str__(self):
        return str(self.thing)

    def __getattr__(self, attrn):
        if attrn == 'img':
            return self.get_img()
        elif attrn == 'dimension':
            return self.rumor.dimensiondict[self._dimn]
        elif attrn == 'board':
            return self.dimension.boards[self._boardi]
        elif attrn == 'thing':
            return self.dimension.thingdict[self._thingn]
        elif attrn == 'visible':
            return self.img is not None
        elif attrn == 'coords':
            coords = self.get_coords()
            return coords
        elif attrn == 'x':
            coords = self.coords
            if coords is None:
                return 0 - self.width
            else:
                return coords[0]
        elif attrn == 'y':
            coords = self.coords
            if coords is None:
                return 0 - self.height
            else:
                return coords[1]
        elif attrn == 'width':
            return self.img.width
        elif attrn == 'height':
            return self.img.height
        elif attrn == 'rx':
            return self.width / 2
        elif attrn == 'ry':
            return self.height / 2
        elif attrn == 'r':
            if self.rx > self.ry:
                return self.rx
            else:
                return self.ry
        else:
            raise AttributeError(
                "Pawn instance has no such attribute: " +
                attrn)

    def __setattr__(self, attrn, val):
        if attrn == "img":
            self.set_img(val)
        elif attrn == "interactive":
            self.set_interactive(val)
        else:
            super(Pawn, self).__setattr__(attrn, val)

    def get_coords(self, branch=None, tick=None):
        loc = self.thing.get_location(branch, tick)
        if loc is None:
            return None
        if hasattr(loc, 'dest'):
            origspot = self.board.get_spot(loc.orig)
            destspot = self.board.get_spot(loc.dest)
            (ox, oy) = origspot.get_coords(branch, tick)
            (dx, dy) = destspot.get_coords(branch, tick)
            prog = self.thing.get_progress(branch, tick)
            odx = dx - ox
            ody = dy - oy
            return (int(ox + odx * prog) + self.drag_offset_x,
                    int(oy + ody * prog) + self.drag_offset_y)
        elif str(loc) in self.board.spotdict:
            spot = self.board.get_spot(loc)
            coords = spot.get_coords(branch, tick)
            return (
                coords[0] + self.drag_offset_x,
                coords[1] + self.drag_offset_y)
        else:
            return None

    def get_tabdict(self):
        return {
            "pawn_img": [
                {
                    "dimension": str(self.board.dimension),
                    "board": int(self.board),
                    "thing": str(self.thing),
                    "branch": branch,
                    "tick_from": tick_from,
                    "tick_to": tick_to,
                    "img": str(img)}
                for (branch, tick_from, tick_to, img) in
                BranchTicksIter(self.imagery)],
            "pawn_interactive": [
                {
                    "dimension": str(self.board.dimension),
                    "board": int(self.board),
                    "thing": str(self.thing),
                    "branch": branch,
                    "tick_from": tick_from,
                    "tick_to": tick_to}
                for (branch, tick_from, tick_to) in
                BranchTicksIter(self.interactivity)]}

    def new_branch(self, parent, branch, tick):
        self.new_branch_imagery(parent, branch, tick)
        self.new_branch_interactivity(parent, branch, tick)


class PawnWidget:
    selectable = True

    def __init__(self, viewport, pawn):
        self.pawn = pawn
        self.rumor = self.pawn.rumor
        self.viewport = viewport
        self.batch = self.viewport.batch
        self.spritegroup = OrderedGroup(0, self.viewport.pawngroup)
        self.boxgroup = OrderedGroup(1, self.viewport.pawngroup)
        self.window = self.viewport.window
        self.calcol = None

    def __getattr__(self, attrn):
        if attrn == "board_left":
            return self.pawn.x
        elif attrn == "board_bot":
            return self.pawn.y
        elif attrn == "board_top":
            return self.pawn.y + self.pawn.height
        elif attrn == "board_right":
            return self.pawn.x + self.pawn.width
        elif attrn == "viewport_left":
            return self.board_left + self.viewport.offset_x
        elif attrn == "viewport_right":
            return self.board_right + self.viewport.offset_x
        elif attrn == "viewport_bot":
            return self.board_bot + self.viewport.offset_y
        elif attrn == "viewport_top":
            return self.board_top + self.viewport.offset_y
        elif attrn == "window_left":
            return self.viewport_left + self.viewport.window_left
        elif attrn == "window_right":
            return self.viewport_right + self.viewport.window_left
        elif attrn == "window_bot":
            return self.viewport_bot + self.viewport.window_bot
        elif attrn == "window_top":
            return self.viewport_top + self.viewport.window_bot
        elif attrn in ("selected", "highlit"):
            return self in self.window.selected
        elif attrn == "hovered":
            return self is self.window.hovered
        elif attrn == "pressed":
            return self is self.window.pressed
        elif attrn == "grabbed":
            return self is self.window.grabbed
        elif attrn == "in_view":
            return (
                self.viewport_right > 0 and
                self.viewport_left < self.viewport.width and
                self.viewport_top > 0 and
                self.viewport_bot < self.viewport.height)
        elif attrn in (
                "img", "visible", "interactive",
                "width", "height", "thing"):
            return getattr(self.pawn, attrn)
        else:
            raise AttributeError(
                "PawnWidget instance has no attribute " + attrn)

    def hover(self, x, y):
        return self

    def move_with_mouse(self, x, y, dx, dy, buttons, modifiers):
        self.pawn.drag_offset_x += dx
        self.pawn.drag_offset_y += dy

    def dropped(self, x, y, button, modifiers):
        """When dropped on a spot, if my thing doesn't have anything else to
do, make it journey there.

If it DOES have anything else to do, make the journey in another branch.

        """
        spotto = None
        for spot in self.viewport.board.spots:
            if (
                    self.viewport_left < spot.x and
                    spot.x < self.viewport_right and
                    self.viewport_bot < spot.y and
                    spot.y < self.viewport_top):
                spotto = spot
                break
        if spotto is not None:
            self.thing.journey_to(spotto.place)
            try:
                self.calcol.regen_cells()
            except:
                pass
        self.pawn.drag_offset_x = 0
        self.pawn.drag_offset_y = 0

    def delete(self):
        try:
            self.sprite.delete()
        except:
            pass

    def draw(self):
        if (
                None in (self.viewport_left, self.viewport_bot)):
            return
        try:
            self.sprite.x = self.viewport_left
            self.sprite.y = self.viewport_bot
        except AttributeError:
            self.sprite = Sprite(
                self.img.tex,
                self.window_left,
                self.window_bot,
                batch=self.batch,
                group=self.spritegroup)
        if self.selected:
            yelo = (255, 255, 0, 255)
            colors = yelo * 4
            points = (
                self.viewport_left, self.viewport_top,
                self.viewport_right, self.viewport_top,
                self.viewport_right, self.viewport_bot,
                self.viewport_left, self.viewport_bot)
            try:
                self.vertlist.vertices = points
            except:
                self.vertlist = self.batch.add_indexed(
                    4,
                    GL_LINES,
                    self.boxgroup,
                    (0, 1, 1, 2, 2, 3, 3, 0),
                    ('v2i', points),
                    ('c4B', colors))
        else:
            try:
                self.vertlist.delete()
            except:
                pass
            self.vertlist = None

    def overlaps(self, x, y):
        return (
            self.viewport_left < x and x < self.viewport_right and
            self.viewport_bot < y and y < self.viewport_top)

    def pass_focus(self):
        return self.viewport

    def select(self):
        if self.calcol is not None:
            self.calcol.visible = True

    def unselect(self):
        if self.calcol is not None:
            self.calcol.visible = False
