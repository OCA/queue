# Copyright 2019 Camptocamp
# Copyright 2019 Guewen Baconnier
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import itertools
import logging

from collections import deque

from .job import Job

_logger = logging.getLogger(__name__)


def group(*delayables):
    return DelayableGroup(*delayables)


def chain(*delayables):
    return DelayableChain(*delayables)


class Graph:
    __slots__ = ('_graph')

    def __init__(self, graph=None):
        if graph:
            self._graph = graph
        else:
            self._graph = {}

    def add_vertex(self, vertex):
        self._graph.setdefault(vertex, set())

    def add_edge(self, parent, child):
        self.add_vertex(child)
        self._graph.setdefault(parent, set()).add(child)

    def vertices(self):
        return set(self._graph)

    def edges(self):
        links = []
        for vertex, neighbours in self._graph.items():
            for neighbour in neighbours:
                links.append((vertex, neighbour))
        return links

    # from
    # https://codereview.stackexchange.com/questions/55767/finding-all-paths-from-a-given-graph
    def paths(self, vertex):
        """Generate the maximal cycle-free paths in graph starting at vertex.

        >>> g = {1: [2, 3], 2: [3, 4], 3: [1], 4: []}
        >>> sorted(self.paths(1))
        [[1, 2, 3], [1, 2, 4], [1, 3]]
        >>> sorted(self.paths(3))
        [[3, 1, 2, 4]]

        """
        path = [vertex]   # path traversed so far
        seen = {vertex}   # set of vertices in path

        def search():
            dead_end = True
            for neighbour in self._graph[path[-1]]:
                if neighbour not in seen:
                    dead_end = False
                    seen.add(neighbour)
                    path.append(neighbour)
                    yield from search()
                    path.pop()
                    seen.remove(neighbour)
            if dead_end:
                yield list(path)
        yield from search()

    def root_vertices(self):
        dependency_vertices = set()
        for dependencies in self._graph.values():
            dependency_vertices.update(dependencies)
        return set(self._graph.keys()) - dependency_vertices

    def __repr__(self):
        paths = [
            path for vertex in self.root_vertices()
            for path in sorted(self.paths(vertex))
        ]
        lines = []
        for path in paths:
            lines.append(' → '.join(repr(vertex) for vertex in path))
        return '\n'.join(lines)


class DelayableGraph(Graph):
    """Directed Graph for Delayable dependencies"""

    def _merge_graph(self, graph):
        for vertex, neighbours in graph._graph.items():
            tails = vertex._tail()
            for tail in tails:
                # connect the tails with the heads of each node
                heads = {head for n in neighbours for head in n._head()}
                self._graph.setdefault(tail, set()).update(heads)

    def _connect_graphs(self):
        graph = DelayableGraph()
        graph._merge_graph(self)

        seen = set()
        visit_stack = deque([self])
        while visit_stack:
            current = visit_stack.popleft()
            if current in seen:
                continue

            vertices = current.vertices()
            for vertex in vertices:
                vertex_graph = vertex._graph
                graph._merge_graph(vertex_graph)
                visit_stack.append(vertex_graph)

            seen.add(current)

        return graph

    def delay(self):
        graph = self._connect_graphs()
        vertices = graph.vertices()

        for vertex in vertices:
            vertex._build_job()

        for vertex, neighbour in graph.edges():
            neighbour._generated_job.add_depends({vertex._generated_job})

        # If all the jobs of the graph have another job with the same identity,
        # we do not create them. Maybe we should check that the found jobs are
        # part of the same graph, but not sure it's really required...
        # Also, maybe we want to check only the root jobs.
        existing_mapping = {}
        for vertex in vertices:
            if not vertex.identity_key:
                continue
            generated_job = vertex._generated_job
            existing = generated_job.job_record_with_same_identity_key()
            if not existing:
                # at least one does not exist yet, we'll delay the whole graph
                existing_mapping.clear()
                break
            existing_mapping[vertex] = existing

        # We'll replace the generated jobs by the existing ones, so callers
        # can retrieve the existing job in "_generated_job".
        # existing_mapping contains something only if *all* the job with an
        # identity have an existing one.
        for vertex, existing in existing_mapping.items():
            vertex._generated_job = existing
            return

        for vertex in vertices:
            vertex._generated_job.store()


class DelayableChain:
    __slots__ = ('_graph', '__head', '__tail')

    def __init__(self, *delayables):
        self._graph = DelayableGraph()
        iter_delayables = iter(delayables)
        head = next(iter_delayables)
        self.__head = head
        self._graph.add_vertex(head)
        for neighbour in iter_delayables:
            self._graph.add_edge(head, neighbour)
            head = neighbour
        self.__tail = head

    def _head(self):
        return self.__head._tail()

    def _tail(self):
        return self.__tail._head()

    def __repr__(self):
        return 'DelayableChain({})'.format(self._graph)

    def done(self, *delayables):
        for delayable in delayables:
            self._graph.add_edge(self.__tail, delayable)
        return self

    def delay(self):
        self._graph.delay()


class DelayableGroup:
    __slots__ = ('_graph', '_delayables')

    def __init__(self, *delayables):
        self._graph = DelayableGraph()
        self._delayables = set(delayables)
        for delayable in delayables:
            self._graph.add_vertex(delayable)

    def _head(self):
        return itertools.chain.from_iterable(
            node._head() for node in self._delayables
        )

    def _tail(self):
        return itertools.chain.from_iterable(
            node._tail() for node in self._delayables
        )

    def __repr__(self):
        return 'DelayableGroup({})'.format(self._graph)

    def done(self, *delayables):
        for parent in self._delayables:
            for child in delayables:
                self._graph.add_edge(parent, child)
        return self

    def delay(self):
        self._graph.delay()


class Delayable:
    _properties = (
        'priority', 'eta', 'max_retries', 'description',
        'channel', 'identity_key'
    )
    __slots__ = _properties + (
        'recordset', '_graph', '_job_method', '_job_args', '_job_kwargs',
        '_generated_job',
    )

    def __init__(self, recordset, priority=None, eta=None,
                 max_retries=None, description=None, channel=None,
                 identity_key=None):
        self._graph = DelayableGraph()
        self._graph.add_vertex(self)

        self.recordset = recordset

        self.priority = priority
        self.eta = eta
        self.max_retries = max_retries
        self.description = description
        self.channel = channel
        self.identity_key = identity_key

        self._job_method = None
        self._job_args = ()
        self._job_kwargs = {}

        self._generated_job = None

    def _head(self):
        return [self]

    def _tail(self):
        return [self]

    def __repr__(self):
        return 'Delayable({}.{}({}, {}))'.format(
            self.recordset, self._job_method.__name__,
            self._job_args, self._job_kwargs
        )

    def __del__(self):
        if not self._generated_job:
            _logger.warning(
                'Delayable %s was prepared but never delayed', self
            )

    def _set_from_dict(self, properties):
        for key, value in properties.items():
            if key not in self._properties:
                raise ValueError('No property %s' % (key,))
            setattr(self, key, value)

    def set(self, *args, **kwargs):
        if args:
            # args must be a dict
            self._set_from_dict(*args)
        self._set_from_dict(kwargs)
        return self

    def done(self, *delayables):
        for child in delayables:
            self._graph.add_edge(self, child)
        return self

    def delay(self):
        self._graph.delay()

    def _build_job(self):
        if self._generated_job:
            return self._generated_job
        self._generated_job = Job(
            self._job_method,
            args=self._job_args,
            kwargs=self._job_kwargs,
            priority=self.priority,
            max_retries=self.max_retries,
            eta=self.eta,
            description=self.description,
            channel=self.channel,
            identity_key=self.identity_key,
        )
        return self._generated_job

    def _store_args(self, *args, **kwargs):
        self._job_args = args
        self._job_kwargs = kwargs
        return self

    def __getattr__(self, name):
        if name in self.__slots__:
            return super().__getattr__(name)
        if name in self.recordset:
            raise AttributeError(
                'only methods can be delayed (%s called on %s)' %
                (name, self.recordset)
            )
        recordset_method = getattr(self.recordset, name)
        self._job_method = recordset_method
        return self._store_args


class DelayableRecordset(object):
    """Allow to delay a method for a recordset (shortcut way)

    Usage::

        delayable = DelayableRecordset(recordset, priority=20)
        delayable.method(args, kwargs)

    ``method`` must be a method of the recordset's Model, decorated with
    :func:`~odoo.addons.queue_job.job.job`.

    The method call will be processed asynchronously in the job queue, with
    the passed arguments.

    This class will generally not be used directly, it is used internally
    by :meth:`~odoo.addons.queue_job.models.base.Base.with_delay`
    """

    __slots__ = ('delayable',)

    def __init__(self, recordset, priority=None, eta=None,
                 max_retries=None, description=None, channel=None,
                 identity_key=None):
        self.delayable = Delayable(
            recordset,
            priority=priority,
            eta=eta,
            max_retries=max_retries,
            description=description,
            channel=channel,
            identity_key=identity_key,
        )

    @property
    def recordset(self):
        return self.delayable.recordset

    def __getattr__(self, name):
        def _delay_delayable(*args, **kwargs):
            getattr(self.delayable, name)(*args, **kwargs).delay()
            return self.delayable._generated_job
        return _delay_delayable

    def __str__(self):
        return "DelayableRecordset(%s%s)" % (
            self.delayable.recordset._name,
            getattr(self.delayable.recordset, '_ids', "")
        )

    __repr__ = __str__
