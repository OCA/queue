# copyright 2019 Camptocamp
# license agpl-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import mock
import unittest

from odoo.addons.queue_job.delay import Delayable, DelayableGraph


class TestDelayable(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.recordset = mock.MagicMock(name='recordset')

    def test_delayable_set(self):
        dl = Delayable(self.recordset)
        dl.set(priority=15)
        self.assertEqual(dl.priority, 15)
        dl.set({'priority': 20, 'description': 'test'})
        self.assertEqual(dl.priority, 20)
        self.assertEqual(dl.description, 'test')

    def test_delayable_set_unknown(self):
        dl = Delayable(self.recordset)
        with self.assertRaises(ValueError):
            dl.set(foo=15)

    def test_graph_add_vertex_edge(self):
        graph = DelayableGraph()
        graph.add_vertex('a')
        self.assertEqual(graph._graph, {'a': set()})
        graph.add_edge('a', 'b')
        self.assertEqual(graph._graph, {'a': {'b'}, 'b': set()})
        graph.add_edge('b', 'c')
        self.assertEqual(graph._graph, {'a': {'b'}, 'b': {'c'}, 'c': set()})

    def test_graph_vertices(self):
        graph = DelayableGraph({'a': {'b'}, 'b': {'c'}, 'c': set()})
        self.assertEqual(graph.vertices(), {'a', 'b', 'c'})

    def test_graph_edges(self):
        graph = DelayableGraph({
            'a': {'b'},
            'b': {'c', 'd'},
            'c': {'e'},
            'd': set(),
            'e': set()
        })
        self.assertEqual(
            sorted(graph.edges()),
            sorted([
                ('a', 'b'),
                ('b', 'c'),
                ('b', 'd'),
                ('c', 'e'),
            ])
        )

    def test_graph_connect(self):
        node_tail = Delayable(self.recordset)
        node_tail2 = Delayable(self.recordset)
        node_middle = Delayable(self.recordset)
        node_top = Delayable(self.recordset)
        node_middle.done(node_tail)
        node_middle.done(node_tail2)
        node_top.done(node_middle)
        collected = node_top._graph._connect_graphs()
        self.assertEqual(
            collected._graph,
            {
                node_tail: set(),
                node_tail2: set(),
                node_middle: {node_tail, node_tail2},
                node_top: {node_middle},
            }
        )

    def test_graph_paths(self):
        graph = DelayableGraph({
            'a': {'b'},
            'b': {'c', 'd'},
            'c': {'e'},
            'd': set(),
            'e': set()
        })
        paths = list(graph.paths('a'))
        self.assertEqual(
            sorted(paths),
            sorted([['a', 'b', 'd'], ['a', 'b', 'c', 'e']])
        )
        paths = list(graph.paths('b'))
        self.assertEqual(
            sorted(paths),
            sorted([['b', 'd'], ['b', 'c', 'e']])
        )
        paths = list(graph.paths('c'))
        self.assertEqual(paths, [['c', 'e']])
        paths = list(graph.paths('d'))
        self.assertEqual(paths, [['d']])
        paths = list(graph.paths('e'))
        self.assertEqual(paths, [['e']])

    def test_graph_repr(self):
        graph = DelayableGraph({
            'a': {'b'},
            'b': {'c', 'd'},
            'c': {'e'},
            'd': set(),
            'e': set()
        })
        actual = repr(graph)
        expected = (
            "'a' → 'b' → 'c' → 'e'\n"
            "'a' → 'b' → 'd'"
        )
        self.assertEqual(actual, expected)
