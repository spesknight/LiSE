# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) Zachary Spector,  zacharyspector@gmail.com


"""The top level of the LiSE world model, the Character.

Based on NetworkX DiGraph objects with various additions and
conveniences.

A Character is a graph that follows rules. Its rules may be assigned
to run on only some portion of it: just edges (called Portals), just
nodes, or just nodes of the kind that have a location in another node
(called Things and Places, respectively). Each Character has a
``stat`` property that acts very much like a dictionary, in which you
can store game-relevant data for the rules to use.

You can designate some nodes in one Character as avatars of another,
and then assign a rule to run on all of a Character's avatars. This is
useful for the common case where someone in your game has a location
in the physical world (here, a Character, called 'physical') but also
has a behavior flowchart, or a skill tree, that isn't part of the
physical world. In that case the flowchart is the person's Character,
and their node in the physical world is an avatar of it.

"""

from collections import (
    Mapping,
    MutableMapping,
    Callable
)
from operator import ge, gt, le, lt, eq
from math import floor

import networkx as nx
from gorm.graph import (
    DiGraph,
    GraphNodeMapping,
    GraphSuccessorsMapping,
    DiGraphPredecessorsMapping
)
from gorm.reify import reify

from .xcollections import CompositeDict
from .bind import TimeDispatcher
from .rule import RuleBook, RuleMapping
from .rule import RuleFollower as BaseRuleFollower
from .node import Node
from .thing import Thing
from .place import Place
from .portal import Portal
from .util import getatt


class AbstractCharacter(object):
    """The Character API, with all requisite mappings and graph generators."""
    @reify
    def thing(self):
        return self.ThingMapping(self)

    @reify
    def place(self):
        return self.PlaceMapping(self)

    @reify
    def node(self):
        return self.ThingPlaceMapping(self)

    @reify
    def portal(self):
        return self.PortalSuccessorsMapping(self)

    @reify
    def preportal(self):
        return self.PortalPredecessorsMapping(self)

    @reify
    def avatar(self):
        return self.AvatarGraphMapping(self)

    @reify
    def stat(self):
        return self.StatMapping(self)

    pred = getatt('preportal')
    adj = succ = edge = getatt('portal')

    def do(self, func, *args, **kwargs):
        """Apply the function to myself, and return myself.

        Look up the function in the database if needed. Pass it any
        arguments given, keyword or positional.

        Useful chiefly when chaining.

        """
        if not callable(func):
            func = self.engine.function[func]
        func(self, *args, **kwargs)
        return self

    def perlin(self, stat='perlin'):
        """Apply Perlin noise to my nodes, and return myself.

        I'll try to use the name of the node as its spatial position
        for this purpose, or use its stats 'x', 'y', and 'z', or skip
        the node if neither are available. z is assumed 0 if not
        provided for a node.

        Result will be stored in a node stat named 'perlin' by default.
        Supply the name of another stat to use it instead.

        """
        p = self.engine.shuffle([
            151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7,
            225, 140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190,
            6, 148, 247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117,
            35, 11, 32, 57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136,
            171, 168, 68, 175, 74, 165, 71, 134, 139, 48, 27, 166, 77, 146,
            158, 231, 83, 111, 229, 122, 60, 211, 133, 230, 220, 105, 92, 41,
            55, 46, 245, 40, 244, 102, 143, 54, 65, 25, 63, 161, 1, 216, 80,
            73, 209, 76, 132, 187, 208, 89, 18, 169, 200, 196, 135, 130, 116,
            188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64, 52, 217, 226,
            250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212, 207,
            206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213,
            119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43,
            172, 9, 129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178,
            185, 112, 104, 218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144,
            12, 191, 179, 162, 241, 81, 51, 145, 235, 249, 14, 239, 107, 49,
            192, 214, 31, 181, 199, 106, 157, 184, 84, 204, 176, 115, 121, 50,
            45, 127, 4, 150, 254, 138, 236, 205, 93, 222, 114, 67, 29, 24, 72,
            243, 141, 128, 195, 78, 66, 215, 61, 156, 180
        ]) * 2

        def fade(t):
            return t * t * t * (t * (t * 6 - 15) + 10)

        def lerp(t, a, b):
            return a + t * (b - a)

        def grad(hsh, x, y, z):
            """CONVERT LO 4 BITS OF HASH CODE INTO 12 GRADIENT DIRECTIONS."""
            h = hsh & 15
            u = x if h < 8 else y
            v = y if h < 4 else x if h == 12 or h == 14 else z
            return (u if h & 1 == 0 else -u) + (v if h & 2 == 0 else -v)

        def noise(x, y, z):
            # FIND UNIT CUBE THAT CONTAINS POINT.
            X = int(x) & 255
            Y = int(y) & 255
            Z = int(z) & 255
            # FIND RELATIVE X, Y, Z OF POINT IN CUBE.
            x -= floor(x)
            y -= floor(y)
            z -= floor(z)
            # COMPUTE FADE CURVES FOR EACH OF X, Y, Z.
            u = fade(x)
            v = fade(y)
            w = fade(z)
            # HASH COORDINATES OF THE 8 CUBE CORNERS,
            A = p[X] + Y
            AA = p[A] + Z
            AB = p[A+1] + Z
            B = p[X+1] + y
            BA = p[B] + Z
            BB = p[B+1] + Z
            # AND ADD BLENDED RESULTS FROM 8 CORNERS OF CUBE
            return lerp(
                w,
                lerp(
                    v,
                    lerp(
                        u,
                        grad(p[AA], x, y, z),
                        grad(p[BA], x-1, y, z)
                    ),
                    lerp(
                        u,
                        grad(p[AB], x, y-1, z),
                        grad(p[BB], x-1, y-1, z)
                    )
                ),
                lerp(
                    v,
                    lerp(
                        u,
                        grad(p[AA+1], x, y, z-1),
                        grad(p[BA+1], x-1, y, z-1)
                    ),
                    lerp(
                        u,
                        grad(p[AB+1], x, y-1, z-1),
                        grad(p[BB+1], x-1, y-1, z-1)
                    )
                )
            )

        for node in self.node.values():
            try:
                (x, y, z) = node.name
            except ValueError:
                try:
                    (x, y) = node.name
                    z = 0.0
                except ValueError:
                    try:
                        x = node['x']
                        y = node['y']
                        z = node.get('z', 0.0)
                    except KeyError:
                        continue
            x, y, z = map(float, (x, y, z))
            node[stat] = noise(x, y, z)

        return self

    def copy_from(self, g):
        """Copy all nodes and edges from the given graph into this."""
        renamed = {}
        for k, v in g.node.items():
            ok = k
            if k in self.place:
                n = 0
                while k in self.place:
                    k = ok + (n,) if isinstance(ok, tuple) else (ok, n)
                    n += 1
            renamed[ok] = k
            self.place[k] = v
        for u in g.edge:
            for v in g.edge[u]:
                if isinstance(g, nx.MultiGraph) or\
                   isinstance(g, nx.MultiDiGraph):
                    self.edge[renamed[u]][renamed[v]] = g.edge[u][v][0]
                else:
                    self.edge[renamed[u]][renamed[v]] = g.edge[u][v]
        return self

    def become(self, g):
        """Erase all my nodes and edges. Replace them with a copy of the graph
        provided."""
        self.clear()
        self.copy_from(g)
        return self

    def balanced_tree(self, r, h):
        return self.copy_from(nx.balanced_tree(r, h))

    def barbell_graph(self, m1, m2):
        return self.copy_from(nx.barbell_graph(m1, m2))

    def complete_graph(self, n):
        return self.copy_from(nx.complete_graph(n))

    def circular_ladder_graph(self, n):
        return self.copy_from(nx.circular_ladder_graph(n))

    def cycle_graph(self, n):
        return self.copy_from(nx.cycle_graph(n))

    def empty_graph(self, n):
        return self.copy_from(nx.empty_graph(n))

    def grid_2d_graph(self, m, n, periodic=False):
        return self.copy_from(nx.grid_2d_graph(m, n, periodic))

    def grid_graph(self, dim, periodic=False):
        return self.copy_from(nx.grid_graph(dim, periodic))

    def ladder_graph(self, n):
        return self.copy_from(nx.ladder_graph(n))

    def lollipop_graph(self, m, n):
        return self.copy_from(nx.lollipop_graph(m, n))

    def path_graph(self, n):
        return self.copy_from(nx.path_graph(n))

    def star_graph(self, n):
        return self.copy_from(nx.star_graph(n))

    def wheel_graph(self, n):
        return self.copy_from(nx.wheel_graph(n))

    def fast_gnp_random_graph(self, n, p, seed=None):
        return self.copy_from(nx.fast_gnp_random_graph(
            n, p, seed, directed=True
        ))

    def gnp_random_graph(self, n, p, seed=None):
        return self.copy_from(nx.gnp_random_graph(n, p, seed, directed=True))

    def gnm_random_graph(self, n, m, seed=None):
        return self.copy_from(nx.gnm_random_graph(n, m, seed, directed=True))

    def erdos_renyi_graph(self, n, p, seed=None):
        return self.copy_from(nx.erdos_renyi_graph(n, p, seed, directed=True))

    def binomial_graph(self, n, p, seed=None):
        return self.erdos_renyi_graph(n, p, seed)

    def newman_watts_strogatz_graph(self, n, k, p, seed=None):
        return self.copy_from(nx.newman_watts_strogatz_graph(n, k, p, seed))

    def watts_strogatz_graph(self, n, k, p, seed=None):
        return self.copy_from(nx.watts_strogatz_graph(n, k, p, seed))

    def connected_watts_strogatz_graph(self, n, k, p, tries=100, seed=None):
        return self.copy_from(nx.connected_watts_strogatz_graph(
            n, k, p, tries, seed
        ))

    def random_regular_graph(self, d, n, seed=None):
        return self.copy_from(nx.random_regular_graph(d, n, seed))

    def barabasi_albert_graph(self, n, m, seed=None):
        return self.copy_from(nx.barabasi_albert_graph(n, m, seed))

    def powerlaw_cluster_graph(self, n, m, p, seed=None):
        return self.copy_from(nx.powerlaw_cluster_graph(n, m, p, seed))

    def duplication_divergence_graph(self, n, p, seed=None):
        return self.copy_from(nx.duplication_divergence_graph(n, p, seed))

    def random_lobster(self, n, p1, p2, seed=None):
        return self.copy_from(nx.random_lobster(n, p1, p2, seed))

    def random_shell_graph(self, constructor, seed=None):
        return self.copy_from(nx.random_shell_graph(constructor, seed))

    def random_powerlaw_tree(self, n, gamma=3, seed=None, tries=100):
        return self.copy_from(nx.random_powerlaw_tree(n, gamma, seed, tries))

    def configuration_model(self, deg_sequence, seed=None):
        return self.copy_from(nx.configuration_model(deg_sequence, seed=seed))

    def directed_configuration_model(
            self,
            in_degree_sequence,
            out_degree_sequence,
            seed=None
    ):
        return self.copy_from(nx.directed_configuration_model(
            in_degree_sequence,
            out_degree_sequence,
            seed=seed
        ))

    def expected_degree_graph(self, w, seed=None, selfloops=True):
        return self.copy_from(nx.expected_degree_graph(w, seed, selfloops))

    def havel_hakmi_graph(self, deg_sequence):
        return self.copy_from(nx.havel_hakimi_graph(deg_sequence))

    def directed_havel_hakmi_graph(
            self,
            in_degree_sequence,
            out_degree_sequence
    ):
        return self.copy_from(nx.directed_havel_hakmi_graph(
            in_degree_sequence,
            out_degree_sequence
        ))

    def degree_sequence_tree(self, deg_sequence):
        return self.copy_from(nx.degree_sequence_tree(deg_sequence))

    def random_degree_sequence_graph(self, sequence, seed=None, tries=10):
        return self.copy_from(nx.random_degree_sequence_graph(
            sequence, seed, tries
        ))

    def random_clustered_graph(self, joint_degree_sequence, seed=None):
        return self.copy_from(nx.random_clustered_graph(
            joint_degree_sequence, seed=seed
        ))

    def gn_graph(self, n, kernel=None, seed=None):
        return self.copy_from(nx.gn_graph(n, kernel, seed=seed))

    def gnr_graph(self, n, p, seed=None):
        return self.copy_from(nx.gnr_graph(n, p, seed=seed))

    def gnc_graph(self, n, seed=None):
        return self.copy_from(nx.gnc_graph(n, seed=seed))

    def scale_free_graph(
            self, n,
            alpha=0.41,
            beta=0.54,
            gamma=0.05,
            delta_in=0.2,
            delta_out=0,
            seed=None
    ):
        return self.copy_from(nx.scale_free_graph(
            n,
            alpha,
            beta,
            gamma,
            delta_in,
            delta_out,
            seed=seed
        ))

    def random_geometric_graph(self, n, radius, dim=2, pos=None):
        return self.copy_from(nx.random_geometric_graph(n, radius, dim, pos))

    def geographical_threshold_graph(
            self, n, theta,
            alpha=2,
            dim=2,
            pos=None,
            weight=None
    ):
        return self.copy_from(nx.geographical_threshold_graph(
            n, theta, alpha, dim, pos, weight
        ))

    def waxman_graph(
            self, n,
            alpha=0.4,
            beta=0.1,
            L=None,
            domain=(0, 0, 1, 1)
    ):
        return self.copy_from(nx.waxman_graph(
            n, alpha, beta, L, domain
        ))

    def navigable_small_world_graph(self, n, p=1, q=1, r=2, dim=2, seed=None):
        return self.copy_from(nx.navigable_small_world_graph(
            n, p, q, r, dim, seed
        ))

    def line_graph(self):
        lg = nx.line_graph(self)
        self.clear()
        return self.copy_from(lg)

    def ego_graph(
            self, n,
            radius=1,
            center=True,
            distance=None
    ):
        return self.become(nx.ego_graph(
            self, n,
            radius,
            center,
            False,
            distance
        ))

    def stochastic_graph(self, weight='weight'):
        nx.stochastic_graph(self, copy=False, weight=weight)
        return self

    def uniform_random_intersection_graph(self, n, m, p, seed=None):
        return self.copy_from(nx.uniform_random_intersection_graph(
            n, m, p, seed=seed
        ))

    def k_random_intersection_graph(self, n, m, k, seed=None):
        return self.copy_from(nx.k_random_intersection_graph(
            n, m, k, seed=seed
        ))

    def general_random_intersection_graph(self, n, m, p, seed=None):
        return self.copy_from(
            nx.general_random_intersection_graph(n, m, p, seed=seed)
        )

    def caveman_graph(self, l, k):
        return self.copy_from(nx.caveman_graph(l, k))

    def connected_caveman_graph(self, l, k):
        return self.copy_from(nx.connected_caveman_graph(l, k))

    def relaxed_caveman_graph(self, l, k, p, seed=None):
        return self.copy_from(nx.relaxed_caveman_graph(l, k, p, seed=seed))

    def random_partition_graph(self, sizes, p_in, p_out, seed=None):
        return self.copy_from(nx.random_partition_graph(
            sizes, p_in, p_out, seed=seed, directed=True
        ))

    def planted_partition_graph(self, l, k, p_in, p_out, seed=None):
        return self.copy_from(nx.planted_partition_graph(
            l, k, p_in, p_out, seed=seed, directed=True
        ))

    def gaussian_random_partition_graph(self, n, s, v, p_in, p_out, seed=None):
        return self.copy_from(nx.gaussian_random_partition_graph(
            n, s, v, p_in, p_out, seed=seed
        ))

    def _lookup_comparator(self, comparator):
        if callable(comparator):
            return comparator
        ops = {
            'ge': ge,
            'gt': gt,
            'le': le,
            'lt': lt,
            'eq': eq
        }
        if comparator in ops:
            return ops[comparator]
        return self.engine.function[comparator]

    def cull_nodes(self, stat, threshold=0.5, comparator=ge):
        """Delete nodes whose stat >= ``threshold`` (default 0.5).

        Optional argument ``comparator`` will replace >= as the test
        for whether to cull. You can use the name of a stored function.

        """
        comparator = self._lookup_comparator(comparator)
        dead = [
            name for name, node in self.node.items()
            if stat in node and comparator(node[stat], threshold)
        ]
        self.remove_nodes_from(dead)
        return self

    def cull_portals(self, stat, threshold=0.5, comparator=ge):
        """Delete portals whose stat >= ``threshold`` (default 0.5).

        Optional argument ``comparator`` will replace >= as the test
        for whether to cull. You can use the name of a stored function.

        """
        comparator = self._lookup_comparator(comparator)
        dead = []
        for u in self.portal:
            for v in self.portal[u]:
                if stat in self.portal[u][v] and comparator(
                        self.portal[u][v][stat], threshold
                ):
                    dead.append((u, v))
        self.remove_edges_from(dead)
        return self

    def cull_edges(self, stat, threshold=0.5, comparator=ge):
        """Delete edges whose stat >= ``threshold`` (default 0.5).

        Optional argument ``comparator`` will replace >= as the test
        for whether to cull. You can use the name of a stored function.

        """
        return self.cull_portals(stat, threshold, comparator)


class CharRuleMapping(RuleMapping):
    """Wraps one of a character's rulebooks so you can get its rules by name.

    You can access the rules in this either dictionary-style or as
    attributes. This is for convenience if you want to get at a rule's
    decorators, eg. to add an Action to the rule.

    Using this as a decorator will create a new rule, named for the
    decorated function, and using the decorated function as the
    initial Action.

    Using this like a dictionary will let you create new rules,
    appending them onto the underlying :class:`RuleBook`; replace one
    rule with another, where the new one will have the same index in
    the :class:`RuleBook` as the old one; and activate or deactivate
    rules. The name of a rule may be used in place of the actual rule,
    so long as the rule already exists.

    You can also set a rule active or inactive by setting it to
    ``True`` or ``False``, respectively. Inactive rules are still in
    the rulebook, but won't be followed.

    """
    def __init__(self, character, rulebook, booktyp):
        """Initialize as usual for the ``rulebook``, mostly.

        My ``character`` property will be the one passed in, and my
        ``_table`` will be the ``booktyp`` with ``"_rules"`` appended.

        """
        super().__init__(rulebook.engine, rulebook)
        self.character = character
        self._table = booktyp + "_rules"

    def __iter__(self):
        """Use a query specialized to the character-rule tables."""
        return self.engine.db.active_rules_char(
            self._table,
            self.character.name,
            self.rulebook.name,
            *self.engine.time
        )


class RuleFollower(BaseRuleFollower):
    """Mixin class. Has a rulebook, which you can get a RuleMapping into."""
    def _rule_names_activeness(self):
        if self.engine.caching:
            rulebook = self.engine._characters_rulebooks_cache[
                self.character.name][self._book]
            cache = self.engine._active_rules_cache[rulebook]
            for rule in cache:
                for (branch, tick) in self.engine._active_branches():
                    if branch not in cache[rule]:
                        continue
                    try:
                        yield (
                            rule,
                            cache[rule][branch][tick]
                        )
                        break
                    except KeyError:
                        continue
            return
        return getattr(
            self.character.engine.db,
            'current_rules_' + self._book
        )(self.character.name, *self.character.engine.time)

    def _get_rule_mapping(self):
        return CharRuleMapping(
            self.character,
            self.rulebook,
            self._book
        )

    def _get_rulebook_name(self):
        if not self.engine.caching:
            return self.engine.db.get_rulebook_char(
                self._book,
                self.character.name
            )
        return self.engine._characters_rulebooks_cache[
            self.character.name][self._book]

    def _set_rulebook_name(self, n):
        self.engine.db.upd_rulebook_char(self._book, n, self.character.name)
        if self.engine.caching:
            self.engine._characters_rulebooks_cache[
                self.character.name][self._book] = n

    def __contains__(self, k):
        if self.engine.caching:
            rulebook_name = self._get_rulebook_name()
            if (
                    rulebook_name not in self.engine._active_rules_cache or
                    k not in self.engine._active_rules_cache[rulebook_name]
            ):
                return False
            cache = self.engine._active_rules_cache[
                self._get_rulebook_name()][k]
            for (branch, tick) in self.engine._active_branches():
                if branch not in cache:
                    continue
                try:
                    return cache[branch][tick]
                except KeyError:
                    continue
            return False
        return self.engine.db.active_rule_char(
            self._table,
            self.character.name,
            self.rulebook.name,
            k,
            *self.engine.time
        )


class SenseFuncWrap(object):
    """Wrapper for a sense function that looks it up in the code store if
    provided with its name, and prefills the first two arguments.

    """
    engine = getatt('character.engine')

    def __init__(self, character, fun):
        """Store the character and the function.

        Look up the function in the engine's ``sense`` function store,
        if needed.

        """
        self.character = character
        if isinstance(fun, str):
            self.fun = self.engine.sense[fun]
        else:
            self.fun = fun
        if not isinstance(self.fun, Callable):
            raise TypeError("Function is not callable")

    def __call__(self, observed):
        """Call the function, prefilling the engine and observer arguments"""
        if isinstance(observed, str):
            observed = self.engine.character[observed]
        return self.fun(self.engine, self.character, Facade(observed))


class CharacterSense(object):
    """Mapping for when you've selected a sense for a character to use
    but haven't yet specified what character to look at

    """
    engine = getatt('container.engine')
    observer = getatt('container.character')

    def __init__(self, container, sensename):
        """Store the container and the name of the sense"""
        self.container = container
        self.sensename = sensename

    @property
    def func(self):
        """Return the function most recently associated with this sense"""
        fn = self.engine.db.sense_func_get(
            self.observer.name,
            self.sensename,
            *self.engine.time
        )
        if fn is not None:
            return SenseFuncWrap(self.observer, fn)

    def __call__(self, observed):
        """Call my sense function and make sure it returns the right type,
        then return that.

        """
        r = self.func(observed)
        if not (
                isinstance(r, Character) or
                isinstance(r, Facade)
        ):
            raise TypeError(
                "Sense function did not return a character-like object"
            )
        return r


class CharacterSenseMapping(MutableMapping, RuleFollower, TimeDispatcher):
    """Used to view other Characters as seen by one, via a particular sense"""
    _book = "character"

    engine = getatt('character.engine')

    def __init__(self, character):
        """Store the character"""
        self.character = character

    def __iter__(self):
        """Iterate over active sense names"""
        yield from self.engine.db.sense_active_items(
            self.character.name, *self.engine.time
        )

    def __len__(self):
        """Count active senses"""
        n = 0
        for sense in iter(self):
            n += 1
        return n

    def __getitem__(self, k):
        """Get a :class:`CharacterSense` named ``k`` if it exists"""
        if not self.engine.db.sense_is_active(
                self.character.name,
                k,
                *self.engine.time
        ):
            raise KeyError("Sense isn't active or doesn't exist")
        return CharacterSense(self.character, k)

    def __setitem__(self, k, v):
        """Use the function for the sense from here on out"""
        if isinstance(v, str):
            funn = v
        else:
            funn = v.__name__
        if funn not in self.engine.sense:
            if not isinstance(v, Callable):
                raise TypeError("Not a function")
            self.engine.sense[funn] = v
        (branch, tick) = self.engine.time
        self.engine.db.sense_fun_set(
            self.character.name,
            k,
            branch,
            tick,
            funn,
            True
        )
        self.dispatch(k, v)

    def __delitem__(self, k):
        """Stop having the given sense"""
        (branch, tick) = self.engine.time
        self.engine.db.sense_set(
            self.character.name,
            k,
            branch,
            tick,
            False
        )
        self.dispatch(k, None)

    def __call__(self, fun, name=None):
        """Decorate the function so it's mine now"""
        if not isinstance(fun, Callable):
            raise TypeError(
                "I need a function here"
            )
        if name is None:
            name = fun.__name__
        self[name] = fun


class FacadePlace(MutableMapping, TimeDispatcher):
    """Lightweight analogue of Place for Facade use"""
    @property
    def name(self):
        return self['name']

    @property
    def _dispatch_cache(self):
        return self

    @reify
    def _patch(self):
        return {}

    @reify
    def _masked(self):
        return set()

    def contents(self):
        for thing in self.facade.thing.values():
            if thing.container is self:
                yield thing

    def __init__(self, facade, real_or_name, **kwargs):
        """Store ``facade``; store ``real_or_name`` if it's a Place

        Otherwise use a plain dict for the underlying 'place'.

        """
        self._patch = kwargs
        if isinstance(real_or_name, Place) or \
           isinstance(real_or_name, FacadePlace):
            self._real = real_or_name
        else:
            self._real = {'name': real_or_name}

    def __iter__(self):
        seen = set()
        for k in self._real:
            if k not in self._masked:
                yield k
            seen.add(k)
        for k in self._patch:
            if (
                    k not in self._masked and
                    k not in seen
            ):
                yield k

    def __len__(self):
        n = 0
        for k in self:
            n += 1
        return n

    def __getitem__(self, k):
        if k in self._masked:
            raise KeyError("{} has been masked.".format(k))
        if k in self._patch:
            return self._patch[k]
        return self._real[k]

    def __setitem__(self, k, v):
        if k == 'name':
            raise TypeError("Can't change names")
        self._masked.discard(k)
        self._patch[k] = v
        self.dispatch(k, v)

    def __delitem__(self, k):
        self._masked.add(k)
        self.dispatch(k, None)


class FacadeThing(FacadePlace):
    @property
    def name(self):
        return self._real['name']

    def __init__(self, facade, real_or_name, location=None, *args, **kwargs):
        if location is None and not (
                isinstance(real_or_name, Thing) or
                isinstance(real_or_name, FacadeThing)
        ):
            raise TypeError(
                "FacadeThing needs to wrap a real Thing or another "
                "FacadeThing, or have a location of its own."
            )
        self._patch = kwargs
        if hasattr(location, 'name'):
            location = location.name
        if location is not None and location not in self.facade.place:
            self.facade.new_place(location)
        self._real = {
            'name': real_or_name.name if hasattr(real_or_name, 'name')
            else real_or_name,
            'location': location
        }

    @property
    def location(self):
        try:
            return self.facade.node[self['location']]
        except KeyError:
            return None

    @property
    def next_location(self):
        try:
            return self.facade.node[self['next_location']]
        except KeyError:
            return None

    @property
    def container(self):
        if self['next_location'] is None:
            return self.location
        try:
            return self.facade.portal[self['location']][
                self['next_location']]
        except KeyError:
            return self.location


class FacadePortal(FacadePlace):
    """Lightweight analogue of Portal for Facade use"""
    def __init__(self, real_or_origin, destination=None, **kwargs):
        if destination is None:
            if not (
                    isinstance(real_or_origin, Portal) or
                    isinstance(real_or_origin, FacadePortal)
            ):
                raise TypeError(
                    "FacadePortal must wrap a real portal or another "
                    "FacadePortal, or be instantiated with "
                    "an origin and a destiantion."
                )
            self._real = real_or_origin
        else:
            if (
                    isinstance(real_or_origin, Portal) or
                    isinstance(real_or_origin, FacadePortal)
            ):
                raise TypeError(
                    "Either wrap something, or supply origin and destination. "
                    "Not both."
                )
            self._real = {
                'origin': real_or_origin.name
                if hasattr(real_or_origin, 'name')
                else real_or_origin,
                'destination': destination.name
                if hasattr(destination, 'name')
                else destination
            }
        self._patch = kwargs

    def __setitem__(self, k, v):
        if k in ('origin', 'destination'):
            raise TypeError("Portals have fixed origin and destination")
        super().__setitem__(k, v)

    @property
    def origin(self):
        return self.facade.node[self._real['origin']]

    @property
    def destination(self):
        return self.facade.node[self._real['destination']]


class FacadeEntityMapping(MutableMapping, TimeDispatcher):
    """Mapping that contains entities in a Facade.

    All the entities are of the same type, ``facadecls``, possibly
    being distorted views of entities of the type ``innercls``.

    """
    @property
    def _dispatch_cache(self):
        return self

    engine = getatt('facade.engine')

    @reify
    def _patch(self):
        return {}

    @reify
    def _masked(self):
        return set()

    def __init__(self, facade):
        """Store the facade"""
        self.facade = facade

    def __contains__(self, k):
        return (
            k not in self._masked and (
                k in self._patch or
                k in self._get_inner_map()
            )
        )

    def __iter__(self):
        seen = set()
        for k in self._get_inner_map():
            if k not in self._masked:
                yield k
            seen.add(k)
        for k in self._patch:
            if k not in seen:
                yield k

    def __len__(self):
        n = 0
        for k in self:
            n += 1
        return n

    def __getitem__(self, k):
        if k in self._masked:
            raise KeyError("masked")
        if k in self._patch:
            return self._patch[k]
        return self.facadecls(self.facade, self._get_inner_map()[k])

    def __setitem__(self, k, v):
        if not isinstance(v, self.facadecls):
            if not isinstance(v, self.innercls):
                raise TypeError(
                    "Need :class:``Thing`` or :class:``FacadeThing``"
                )
            v = self.facadecls(self.facade, v)
        self._masked.discard(k)
        self._patch[k] = v
        self.dispatch(k, v)

    def __delitem__(self, k):
        self._masked.add(k)
        self.dispatch(k, None)


class FacadePortalSuccessors(FacadeEntityMapping):
    facadecls = FacadePortal
    innercls = Portal

    def __init__(self, facade, origname):
        super().__init__(facade)
        self._origname = origname

    def _get_inner_map(self):
        return self.facade.character.portal[self._origname]


class FacadePortalPredecessors(FacadeEntityMapping):
    facadecls = FacadePortal
    innercls = Portal

    def __init__(self, facade, destname):
        super().__init__(facade)
        self._destname = destname

    def _get_inner_map(self):
        return self.facade.character.preportal[self._destname]


class FacadePortalMapping(FacadeEntityMapping):
    def __getitem__(self, node):
        if node in self._masked:
            raise KeyError("masked")
        if node in self._patch:
            return self._patch[node]
        return self.cls(self.facade, node)

    def __setitem__(self, node, value):
        self._masked.discard(node)
        v = self.cls(self.facade, node)
        v.update(value)
        self._patch[node] = v

    def __delitem__(self, node):
        self._masked.add(node)


class Facade(AbstractCharacter, nx.DiGraph):
    engine = getatt('character.engine')

    def __init__(self, character):
        """Store the character"""
        self.character = character

    class ThingMapping(FacadeEntityMapping):
        facadecls = FacadeThing
        innercls = Thing

        def _get_inner_map(self):
            return self.facade.character.thing

    class PlaceMapping(FacadeEntityMapping):
        facadecls = FacadePlace
        innercls = Place

        def _get_inner_map(self):
            return self.facade.character.place

    def ThingPlaceMapping(self, *args):
        return CompositeDict(self.thing, self.place)

    class PortalSuccessorsMapping(FacadePortalMapping):
        cls = FacadePortalSuccessors

        def _get_inner_map(self):
            return self.facade.character.portal

    class PortalPredecessorsMapping(FacadePortalMapping):
        cls = FacadePortalPredecessors

        def _get_inner_map(self):
            return self.facade.character.preportal

    class StatMapping(MutableMapping, TimeDispatcher):
        @property
        def _dispatch_cache(self):
            return self

        def __init__(self, facade):
            self.facade = facade
            self._patch = {}
            self._masked = set()

        def __iter__(self):
            seen = set()
            for k in self.facade.graph:
                if k not in self._masked:
                    yield k
                seen.add(k)
            for k in self._patch:
                if k not in seen:
                    yield k

        def __len__(self):
            n = 0
            for k in self:
                n += 1
            return n

        def __contains__(self, k):
            if k in self._masked:
                return False
            return (
                k in self._patch or
                k in self.facade.graph
            )

        def __getitem__(self, k):
            if k in self._masked:
                raise KeyError("masked")
            if k in self._patch:
                return self._patch[k]
            return self.facade.graph[k]

        def __setitem__(self, k, v):
            self._masked.discard(k)
            self._patch[k] = v
            self.dispatch(k, v)

        def __delitem__(self, k):
            self._masked.add(k)
            self.dispatch(k, None)


class Character(AbstractCharacter, DiGraph, RuleFollower):
    """A graph that follows game rules and has a containment hierarchy.

    Nodes in a Character are subcategorized into Things and
    Places. Things have locations, and those locations may be Places
    or other Things. A Thing might also travel, in which case, though
    it will spend its travel time located in its origin node, it may
    spend some time contained by a Portal (i.e. an edge specialized
    for Character). If a Thing is not contained by a Portal, it's
    contained by whatever it's located in.

    """
    _book = "character"

    adj = succ = getatt('portal')

    @property
    def character(self):
        return self

    def __init__(self, engine, name, data=None, **attr):
        """Store engine and name, and set up mappings for Thing, Place, and
        Portal

        """
        super().__init__(engine, name, data, **attr)
        self.engine = engine
        d = {}
        for mapp in (
                'character',
                'avatar',
                'thing',
                'place',
                'portal',
                'node'
        ):
            if mapp + '_rulebook' in attr:
                rulebook = attr[mapp + '_rulebook']
                d[mapp] = rulebook.name \
                          if isinstance(rulebook, RuleBook) \
                          else rulebook
        self.engine.db.init_character(
            self.name,
            **d
        )
        if engine.caching:
            self.engine._characters_rulebooks_cache[self.name] = {
                'character': d.get('character', (self.name, 'character')),
                'avatar': d.get('avatar', (self.name, 'avatar')),
                'character_thing': d.get('thing',
                                         (self.name, 'character_thing')),
                'character_place': d.get('place',
                                         (self.name, 'character_place')),
                'character_node': d.get('node', (self.name, 'character_node')),
                'character_portal': d.get('portal',
                                          (self.name, 'character_portal'))
            }

    class ThingMapping(MutableMapping, RuleFollower, TimeDispatcher):
        """:class:`Thing` objects that are in a :class:`Character`"""
        _book = "character_thing"

        engine = getatt('character.engine')
        name = getatt('character.name')
        _cache = getatt('_dispatch_cache')

        def __init__(self, character):
            """Store the character and initialize cache"""
            self.character = character

        def __iter__(self):
            if not self.engine.caching:
                for (n, l) in self.engine.db.thing_loc_items(
                    self.character.name,
                    *self.engine.time
                ):
                    yield n
                return
            (branch, tick) = self.engine.time
            if self.character.name not in self.engine._things_cache:
                return
            cache = self.engine._things_cache[self.character.name]
            for thing in cache:
                try:
                    if branch in cache[thing] and cache[thing][branch][tick]:
                        yield thing
                except KeyError:
                    continue

        def __contains__(self, thing):
            if not self.engine.caching:
                for (n, l) in self.engine.db.thing_loc_items(
                    self.character.name,
                    *self.engine.time
                ):
                    if n == thing:
                        return True
                return False
            cache = self.engine._things_cache[self.character.name][thing]
            for (branch, tick) in self.engine._active_branches():
                try:
                    return cache[branch][tick]
                except KeyError:
                    continue
            return False

        def __len__(self):
            n = 0
            for th in self:
                n += 1
            return n

        def __getitem__(self, thing):
            if self.engine.caching and thing in self:
                if thing not in self._cache:
                    self._cache[thing] = Thing(self.character, thing)
                return self._cache[thing]
            if thing not in self:
                raise KeyError("No such thing: {}".format(thing))
            (th, l) = self.engine.db.thing_and_loc(
                self.character.name,
                thing,
                *self.engine.time
            )
            r = Thing(self.character, th)
            if self.engine.caching:
                self._cache[thing] = r
            return r

        def __setitem__(self, thing, val):
            if not isinstance(val, Mapping):
                raise TypeError('Things are made from Mappings')
            if 'location' not in val:
                raise ValueError('Thing needs location')
            (branch, tick) = self.engine.time
            self.engine.db.exist_node(
                self.character.name,
                thing,
                branch,
                tick,
                True
            )
            location = val['location']
            next_location = val.get('next_location', None)
            th = Thing(self.character, thing)
            th.clear()
            th.update(val)
            if self.engine.caching:
                self.engine._nodes_cache[
                    self.character.name][thing][branch][tick] = True
                self.engine._things_cache[
                    self.character.name][thing][branch][tick] \
                    = (location, next_location)
            self.dispatch(thing, th)

        def __delitem__(self, thing):
            (branch, tick) = self.engine.time
            self[thing].delete(nochar=True)
            if self.engine.caching:
                if thing in self._cache:
                    del self._cache[thing]
            self.dispatch(thing, None)

        def __repr__(self):
            return repr(dict(self))

    class PlaceMapping(MutableMapping, RuleFollower, TimeDispatcher):
        """:class:`Place` objects that are in a :class:`Character`"""
        _book = "character_place"

        _cache = getatt('_dispatch_cache')
        engine = getatt('character.engine')
        name = getatt('character.name')

        def __init__(self, character):
            """Store the character."""
            self.character = character

        def __iter__(self):
            things = set(self.character.thing.keys())
            for node in self.character.nodes():
                if node not in things:
                    yield node

        def __len__(self):
            n = 0
            for place in self:
                n += 1
            return n

        def __contains__(self, place):
            if self.engine.caching:
                try:
                    cache = self.engine._nodes_cache[
                        self.character.name][place]
                except KeyError:
                    return False
                for (branch, tick) in self.engine._active_branches():
                    if branch not in cache:
                        continue
                    try:
                        if cache[branch][tick]:
                            return not self.engine._is_thing(
                                self.character.name, place
                            )
                    except KeyError:
                        continue
                return False
            (branch, tick) = self.engine.time
            return self.engine.db.node_exists(
                self.character.name,
                place,
                branch,
                tick
            )

        def __getitem__(self, place):
            if place not in self:
                raise KeyError("No such place: {}".format(place))
            if not self.engine.caching:
                return Place(self.character, place)
            if place not in self._cache:
                self._cache[place] = Place(self.character, place)
            return self._cache[place]

        def __setitem__(self, place, v):
            if not self.engine.caching:
                pl = Place(self.character, place)
            else:
                if place not in self._cache:
                    self._cache[place] = Place(self.character, place)
                pl = self._cache[place]
            (branch, tick) = self.engine.time
            self.engine.db.exist_node(
                self.character.name,
                place,
                branch,
                tick,
                True
            )
            pl.clear()
            pl.update(v)
            if self.engine.caching:
                self.engine._nodes_cache[
                    self.character.name][place][branch][tick] = True
            self.dispatch(place, v)

        def __delitem__(self, place):
            self[place].delete(nochar=True)
            self.dispatch(place, None)

        def __repr__(self):
            return repr(dict(self))

    class ThingPlaceMapping(GraphNodeMapping, RuleFollower):
        """Replacement for gorm's GraphNodeMapping that does Place and Thing"""
        _book = "character_node"

        _cache = getatt('_dispatch_cache')
        graph = getatt('character')
        engine = gorm = getatt('character.engine')
        name = getatt('character.name')

        def __init__(self, character):
            """Store the character."""
            self.character = character

        def __getitem__(self, k):
            try:
                return self.character.place[k]
            except KeyError:
                return self.character.thing[k]

        def __setitem__(self, k, v):
            self.character.place[k] = v

        def __delitem__(self, k):
            if k in self.character.thing:
                del self.character.thing[k]
            elif k in self.character.place:
                del self.character.place[k]
            else:
                raise KeyError("No such thing or place: {}".format(k))

    class PortalSuccessorsMapping(
            GraphSuccessorsMapping, RuleFollower, TimeDispatcher
    ):
        """Mapping of nodes that have at least one outgoing edge.

        Maps them to another mapping, keyed by the destination nodes,
        which maps to Portal objects.

        """
        _book = "character_portal"

        character = getatt('graph')
        engine = getatt('graph.engine')
        _cache = getatt('_dispatch_cache')

        def __getitem__(self, nodeA):
            if self.engine._node_exists(
                    self.graph.name,
                    nodeA
            ):
                if nodeA not in self._cache:
                    self._cache[nodeA] = self.Successors(self, nodeA)
                return self._cache[nodeA]
            raise KeyError("No such node")

        def __setitem__(self, nodeA, val):
            if nodeA not in self._cache:
                self._cache[nodeA] = self.Successors(self, nodeA)
            sucs = self._cache[nodeA]
            sucs.clear()
            sucs.update(val)
            self.dispatch(nodeA, val)

        def __delitem__(self, nodeA):
            super().__delitem__(nodeA)
            self.dispatch(nodeA, None)

        class Successors(GraphSuccessorsMapping.Successors, TimeDispatcher):
            """Mapping for possible destinations from some node."""

            _cache = getatt('_dispatch_cache')
            engine = getatt('graph.engine')

            def dispatch(self, nodeB, portal):
                """Call all listeners to ``nodeB`` and to my ``nodeA``."""
                super().dispatch(nodeB, portal)
                self.container.dispatch(self.nodeA, self)

            def _getsub(self, nodeB):
                if hasattr(self, '_cache'):
                    if nodeB not in self._cache:
                        self._cache[nodeB] = Portal(
                            self.graph, self.nodeA, nodeB
                        )
                    return self._cache[nodeB]
                return Portal(self.graph, self.nodeA, nodeB)

            def __getitem__(self, nodeB):
                if not self.engine.caching:
                    return super().__getitem__(nodeB)
                if nodeB in self:
                    if nodeB not in self._cache:
                        self._cache[nodeB] = Portal(
                            self.graph, self.nodeA, nodeB
                        )
                    return self._cache[nodeB]
                raise KeyError("No such portal: {}->{}".format(
                    self.nodeA, nodeB
                ))

            def __setitem__(self, nodeB, value):
                (branch, tick) = self.engine.time
                if self.engine.caching:
                    if nodeB not in self._cache:
                        self._cache[nodeB] = Portal(
                            self.graph, self.nodeA, nodeB
                        )
                    p = self._cache[nodeB]
                else:
                    p = Portal(self.graph, self.nodeA, nodeB)
                self.engine.db.exist_edge(
                    self.graph.name,
                    self.nodeA,
                    nodeB,
                    0,
                    branch,
                    tick,
                    True
                )
                p.clear()
                p.update(value)
                if self.engine.caching:
                    self.engine._edges_cache[
                        self.graph.name][self.nodeA][nodeB][0][
                            branch][tick] = True
                self.dispatch(nodeB, p)

            def __delitem__(self, nodeB):
                if not self.engine.caching:
                    super().__delitem__(nodeB)
                    return
                (branch, tick) = self.engine.time
                if (
                        nodeB in self._cache and
                        branch in self._cache[nodeB] and
                        tick in self._cache[nodeB][branch]
                ):
                    del self._cache[nodeB][branch][tick]
                super().__delitem__(nodeB)
                self.engine._edges_cache[
                    self.character.name][self.nodeA][nodeB][0][
                        branch][tick] = False
                self.dispatch(nodeB, None)

    class PortalPredecessorsMapping(
            DiGraphPredecessorsMapping,
            RuleFollower
    ):
        """Mapping of nodes that have at least one incoming edge.

        Maps to another mapping keyed by the origin nodes, which maps to
        Portal objects.

        """
        _book = "character_portal"

        class Predecessors(DiGraphPredecessorsMapping.Predecessors):
            """Mapping of possible origins from some destination."""
            def _getsub(self, nodeA):
                if not self.graph.engine.caching:
                    return Portal(self.graph, nodeA, self.nodeB)
                if nodeA in self.graph.portal:
                    if (
                            self.graph.engine.caching and
                            self.nodeB not in self.graph.portal[nodeA]._cache
                    ):
                        self.graph.portal[nodeA]._cache[self.nodeB] = Portal(
                            self.graph,
                            nodeA,
                            self.nodeB
                        )
                    return self.graph.portal[nodeA][self.nodeB]
                return Portal(self.graph, nodeA, self.nodeB)

            def __setitem__(self, nodeA, value):
                if nodeA in self.graph.portal:
                    if (
                            self.graph.engine.caching and
                            self.nodeB not in self.graph.portal[nodeA]._cache
                    ):
                        self.graph.portal[nodeA]._cache[self.nodeB] = Portal(
                            self.graph,
                            nodeA,
                            self.nodeB
                        )
                p = self.graph.portal[nodeA][self.nodeB]
                p.clear()
                p.update(value)
                if self.engine.caching:
                    (branch, tick) = self.engine.time
                    self.engine._edges_cache[
                        self.character.name][self.nodeB][nodeA][0][
                            branch][tick] = True

    class AvatarGraphMapping(Mapping, RuleFollower):
        """A mapping of other characters in which one has an avatar.

        Maps to a mapping of the avatars themselves, or if there's only
        one, to that.

        """
        _book = "avatar"

        engine = getatt('character.engine')
        name = getatt('character.name')

        def __init__(self, char):
            """Remember my character"""
            self.character = char

        def __call__(self, av):
            """Add the avatar. It must be an instance of Place or Thing."""
            if av.__class__ not in (Place, Thing):
                raise TypeError("Only Things and Places may be avatars")
            self.character.add_avatar(av.name, av.character.name)

        def _avatarness_db(self):
            """Get avatar-ness data and return it"""
            return self.engine.db.avatarness(
                self.character.name, *self.engine.time
            )

        def __iter__(self):
            """Iterate over every avatar graph that has at least one avatar node
            in it presently

            """
            if self.engine.caching:
                cache = self.engine._avatarness_cache.db_order
                if self.character.name not in cache:
                    return
                cache = cache[self.character.name]
                seen = False
                for avatar in cache:
                    if seen:
                        continue
                    for node in cache[avatar]:
                        if seen:
                            seen = False
                            break
                        for (branch, tick) in self.engine._active_branches():
                            try:
                                if cache[avatar][node][branch][tick]:
                                    yield avatar
                                seen = True
                                break
                            except KeyError:
                                continue
                return
            yield from self._avatarness_db()

        def __len__(self):
            """Number of graphs in which I have an avatar"""
            n = 0
            for g in self:
                n += 1
            return n

        def __getitem__(self, g):
            """Get the CharacterAvatarMapping for the given graph, if I have any
            avatars in it.

            If I have avatars in only one graph, behave as a proxy to that
            graph's CharacterAvatarMapping.

            Unless I have only one avatar anywhere, in which case be a
            proxy to that.

            """
            if self.engine.caching:
                cache = self.engine._avatarness_cache.db_order[
                    self.character.name][g]
                for node in cache:
                    for (branch, tick) in self.engine._active_branches():
                        try:
                            if cache[node][branch][tick]:
                                return self.CharacterAvatarMapping(self, g)
                        except KeyError:
                            continue
                if len(self) == 1:
                    return self.CharacterAvatarMapping(
                        self, next(iter(self))
                    )[g]
                raise KeyError("{} has no avatar in {}".format(
                    self.character.name, g
                ))
            d = self._avatarness_db()
            if g in d:
                return self.CharacterAvatarMapping(self, g)
            elif len(d.keys()) == 1:
                avm = self.CharacterAvatarMapping(self, list(d.keys())[0])
                if len(avm.keys()) == 1:
                    return avm[list(avm.keys())[0]][g]
                else:
                    return avm[g]
            raise KeyError("No avatar in {}".format(g))

        def __getattr__(self, attr):
            """If I've got only one avatar, return its attribute"""
            if len(self.keys()) == 1:
                avs = self.CharacterAvatarMapping(
                    self, next(iter(self.keys()))
                )
                if len(avs) == 1:
                    av = list(avs.keys())[0]
                    if attr == av:
                        return avs[attr]
                    else:
                        return getattr(avs[list(avs.keys())[0]], attr)
            raise AttributeError

        def __repr__(self):
            """Represent myself like a dictionary"""
            d = {}
            for k in self:
                d[k] = dict(self[k])
            return repr(d)

        class CharacterAvatarMapping(Mapping):
            """Mapping of avatars of one Character in another Character."""
            def __init__(self, outer, graphn):
                """Store the character and the name of the "graph", ie. the other
                character.

                """
                self.character = outer.character
                self.engine = outer.engine
                self.name = outer.name
                self.graph = graphn

            def _branchdata(self, branch, rev):
                if self.engine.caching:
                    return self._branchdata_cache(branch, rev)
                else:
                    return self.engine.db.avatar_branch_data(
                        self.character.name, self.graph, branch, rev
                    )

            def _branchdata_cache(self, branch, rev):
                ac = self.engine._avatarness_cache.db_order[
                    self.character.name][self.graph]
                r = []
                for node in ac:
                    try:
                        r.append((
                            node,
                            ac[node][branch][rev]
                        ))
                    except KeyError:
                        continue
                return r

            def __getattr__(self, attrn):
                """If I don't have such an attribute, but I contain exactly one
                avatar, and *it* has the attribute, return the
                avatar's attribute.

                """
                seen = set()
                counted = 0
                for (branch, rev) in self.engine._active_branches():
                    if counted > 1:
                        break
                    for (n, extant) in self._branchdata(branch, rev):
                        if counted > 1:
                            break
                        x = bool(extant)
                        if x and n not in seen:
                            counted += 1
                        seen.add(n)
                if counted == 1:
                    node = self.engine.character[self.graph].node[seen.pop()]
                    if hasattr(node, attrn):
                        return getattr(node, attrn)
                raise AttributeError("No such attribute: " + attrn)

            def __iter__(self):
                """Iterate over the names of all the presently existing nodes in the
                graph that are avatars of the character

                """
                seen = set()
                for (branch, rev) in self.engine._active_branches():
                    for (n, x) in self._branchdata(branch, rev):
                        if (
                                x and
                                n not in seen and
                                self.engine._node_exists(self.graph, n)
                        ):
                            yield n
                        seen.add(n)

            def __contains__(self, av):
                fun = (
                    self._contains_when_cache
                    if self.engine.caching
                    else self._contains_when_db
                )
                for (branch, tick) in self.engine._active_branches():
                    r = fun(av, branch, tick)
                    if r is None:
                        continue
                    return r
                return False

            def _contains_when_cache(self, av, branch, rev):
                ac = self.engine._avatarness_cache.db_order[
                    self.character.name][self.graph]
                if av not in ac:
                    return False
                for node in ac[av]:
                    try:
                        if ac[av][branch][rev]:
                            return True
                    except KeyError:
                        continue

            def _contains_when_db(self, av, branch, tick):
                return self.engine.db.is_avatar_of(
                    self.character.name,
                    self.graph,
                    av,
                    branch,
                    tick
                )

            def __len__(self):
                """Number of presently existing nodes in the graph that are avatars of
                the character"""
                n = 0
                for a in self:
                    n += 1
                return n

            def __getitem__(self, av):
                """Return the Place or Thing by the given name in the graph, if it's
                my avatar and it exists.

                If I contain exactly *one* Place or Thing, and you're
                not trying to get it by its name, delegate to its
                __getitem__. It's common for one Character to have
                exactly one avatar in another Character, and when that
                happens, it's nice not to have to specify the avatar's
                name.

                """
                if av in self:
                    return self.engine.character[self.graph].node[av]
                if len(self.keys()) == 1:
                    k = list(self.keys())[0]
                    return self.engine.character[self.graph].node[k]
                raise KeyError("No such avatar")

            def __repr__(self):
                """Represent myself like a dictionary"""
                d = {}
                for k in self:
                    d[k] = dict(self[k])
                return repr(d)

    class StatMapping(MutableMapping, TimeDispatcher):
        """Caching dict-alike for character stats"""
        @property
        def _dispatch_cache(self):
            return self.engine._graph_val_cache[
                self.character.name
            ]

        engine = getatt('character.engine')
        _real = getatt('character.graph')

        def __init__(self, char):
            """Store character"""
            self.character = char

        def __iter__(self):
            return iter(self._real)

        def __len__(self):
            return len(self._real)

        def __getitem__(self, k):
            return self._real[k]

        def _get(self, k=None):
            if k is None:
                return self
            return self[k]

        def __setitem__(self, k, v):
            assert(v is not None)
            self._real[k] = v
            self.dispatch(k, v)

        def __delitem__(self, k):
            del self._real[k]
            self.dispatch(k, None)

    def facade(self):
        return Facade(self)

    def add_place(self, name, **kwargs):
        """Create a new Place by the given name, and set its initial
        attributes based on the keyword arguments (if any).

        """
        self.place[name] = kwargs

    def add_places_from(self, seq):
        """Take a series of place names and add the lot."""
        super().add_nodes_from(seq)

    def new_place(self, name, **kwargs):
        self.add_place(name, **kwargs)
        return self.place[name]

    def new_node(self, name, **kwargs):
        return self.new_place(name, **kwargs)

    def add_thing(self, name, location, next_location=None, **kwargs):
        """Create a Thing, set its location and next_location (if provided),
        and set its initial attributes from the keyword arguments (if
        any).

        """
        super().add_node(name, **kwargs)
        if isinstance(location, Node):
            location = location.name
        if isinstance(next_location, Node):
            next_location = next_location.name
        self.place2thing(name, location, next_location)

    def add_things_from(self, seq):
        for tup in seq:
            name = tup[0]
            location = tup[1]
            next_loc = tup[2] if len(tup) > 2 else None
            kwargs = tup[3] if len(tup) > 3 else {}
            self.add_thing(name, location, next_loc, **kwargs)

    def new_thing(self, name, location, next_location=None, **kwargs):
        self.add_thing(name, location, next_location, **kwargs)
        return self.thing[name]

    def place2thing(self, name, location, next_location=None):
        """Turn a Place into a Thing with the given location and (if provided)
        next_location. It will keep all its attached Portals.

        """
        (branch, tick) = self.engine.time
        self.engine.db.thing_loc_and_next_set(
            self.name,
            name,
            branch,
            tick,
            location,
            next_location
        )
        if self.engine.caching:
            self.engine._things_cache[self.name][name][branch][tick] \
                = (location, next_location)

    def thing2place(self, name):
        """Unset a Thing's location, and thus turn it into a Place."""
        self.engine.db.thing_loc_and_next_del(
            self.name,
            name,
            *self.engine.time
        )

    def add_portal(self, origin, destination, symmetrical=False, **kwargs):
        """Connect the origin to the destination with a :class:`Portal`.

        Keyword arguments are the :class:`Portal`'s
        attributes. Exception: if keyword ``symmetrical`` == ``True``,
        a mirror-:class:`Portal` will be placed in the opposite
        direction between the same nodes. It will always appear to
        have the placed :class:`Portal`'s stats, and any change to the
        mirror :class:`Portal`'s stats will affect the placed
        :class:`Portal`.

        """
        if isinstance(origin, Node):
            origin = origin.name
        if isinstance(destination, Node):
            destination = destination.name
        super(Character, self).add_edge(origin, destination, **kwargs)
        if symmetrical:
            self.add_portal(destination, origin, is_mirror=True)

    def new_portal(self, origin, destination, symmetrical=False, **kwargs):
        if isinstance(origin, Node):
            origin = origin.name
        if isinstance(destination, Node):
            destination = destination.name
        self.add_portal(origin, destination, symmetrical, **kwargs)
        return self.portal[origin][destination]

    def add_portals_from(self, seq, symmetrical=False):
        """Take a sequence of (origin, destination) pairs and make a
        :class:`Portal` for each.

        Actually, triples are acceptable too, in which case the third
        item is a dictionary of stats for the new :class:`Portal`.

        If optional argument ``symmetrical`` is set to ``True``, all
        the :class:`Portal` instances will have a mirror portal going
        in the opposite direction, which will always have the same
        stats.

        """
        for tup in seq:
            orig = tup[0]
            dest = tup[1]
            kwargs = tup[2] if len(tup) > 2 else {}
            if symmetrical:
                kwargs['symmetrical'] = True
            self.add_portal(orig, dest, **kwargs)

    def add_avatar(self, a, b=None):
        """Start keeping track of a :class:`Thing` or :class:`Place` in a
        different :class:`Character`.

        """
        if b is None:
            if not (
                    isinstance(a, Place) or
                    isinstance(a, Thing)
            ):
                raise TypeError(
                    'when called with one argument, '
                    'it must be a place or thing'
                )
            g = a.character.name
            n = a.name
        else:
            if isinstance(a, Character):
                g = a.name
            elif not isinstance(a, str):
                raise TypeError(
                    'when called with two arguments, '
                    'the first is a character or its name'
                )
            else:
                g = a
            if isinstance(b, Place) or isinstance(b, Thing):
                n = b.name
            elif not isinstance(b, str):
                raise TypeError(
                    'when called with two arguments, '
                    'the second is a thing/place or its name'
                )
            else:
                n = b
        (branch, tick) = self.engine.time
        # This will create the node if it doesn't exist. Otherwise
        # it's redundant but harmless.
        self.engine.db.exist_node(
            g,
            n,
            branch,
            tick,
            True
        )
        # Declare that the node is my avatar
        self.engine.db.avatar_set(
            self.character.name,
            g,
            n,
            branch,
            tick,
            True
        )
        if self.engine.caching:
            self.engine._nodes_cache[g][n][branch][tick] = True
            self.engine._avatarness_cache.remember(
                self.name, g, n, branch, tick, True
            )

    def del_avatar(self, a, b=None):
        """This is no longer my avatar, though it still exists on its own"""
        if b is None:
            if not isinstance(a, Node):
                raise TypeError(
                    "In single argument form, "
                    "del_avatar requires a Node object "
                    "(Thing or Place)."
                )
            g = a.character.name
            n = a.name
        else:
            g = a.name if isinstance(a, Character) else a
            n = b.name if isinstance(b, Node) else b
        (branch, tick) = self.engine.time
        self.engine.db.avatar_set(
            self.character.name,
            g,
            n,
            branch,
            tick,
            False
        )
        assert not self.engine.db.is_avatar_of(self.name, g, n, branch, tick)
        if self.engine.caching:
            self.engine._avatarness_cache.remember(
                self.character.name, g, n, branch, tick, False
            )

    def portals(self):
        """Iterate over all portals"""
        for o in self.portal:
            for port in self.portal[o].values():
                yield port

    def avatars(self):
        """Iterate over all my avatars, regardless of what character they are
        in.

        """
        if not self.engine.caching:
            for (g, n, a) in self._db_iter_avatar_rows():
                if a:
                    yield self.engine.character[g].node[n]
            return
        ac = self.engine._avatarness_cache.db_order[self.name]
        seen = set()
        for (branch, tick) in self.engine._active_branches():
            for g in ac:
                for n in ac[g]:
                    if (
                            (g, n) not in seen and
                            branch in ac[g][n]
                    ):
                        seen.add((g, n))
                        if ac[g][n][branch][tick]:
                            # the character or avatar may have been
                            # deleted from the world. It remains
                            # "mine" in case it comes back, but don't
                            # yield things that don't exist.
                            if (
                                    g in self.engine.character and
                                    n in self.engine.character[g]
                            ):
                                yield self.engine.character[g].node[n]

    def _db_iter_avatar_rows(self):
        yield from self.engine.db.avatars_now(
            self.character.name,
            *self.engine.time
        )
