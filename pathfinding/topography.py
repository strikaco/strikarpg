from django.conf import settings
from django.core.cache import caches

from evennia.utils import logger
from evennia.utils import class_from_module
from threading import Lock

from networkx.readwrite import json_graph
import networkx as nx
import json


class Topography(object):

    cache_name = 'default'
    TILE_BLANK = '|[X  |n'
    
    _network = nx.DiGraph()
    _lock = Lock()

    def __init__(self, obj, *args, **kwargs):
        self.obj = obj
        with self._lock:
            if not self._network.size():
                self.update()
                
        self.network = self.get_usable()

    def get_queryset(self):
        """
        Get all the Exit objects to be included in this graph.

        Returns:
            objs (iterable): Any iterable of Exit objects.

        """
        return class_from_module(settings.BASE_EXIT_TYPECLASS).objects.all()

    def update(self, *args, **kwargs):
        """
        Updates an existing network or creates a new one.

        Returns:
            network(DiGraph)

        """
        net = self._network

        # Get network scope
        edges = self.get_queryset()

        for edge in edges:
            if not edge: continue
            if not edge.location: continue
        
            net.add_edge(edge.location, edge.destination, obj=edge, key=edge.key)

        return net

    def get_usable(self, caller, *args, **kwargs):
        """
        Returns a subgraph comprised of exits the caller is allowed to traverse.

        """
        network = self._network

        # Figure out which exits the caller can actually use
        edges = ((u,v,data['obj']) for u,v,data in network.edges(data=True))
        edges = tuple((u,v) for u,v,obj in edges if obj.access(caller or self.obj, 'traverse', no_superuser_bypass=True, default=False))

        # Create subgraph based on usable paths
        return network.edge_subgraph(edges)

    def get_path(self, target, *args, source=None, caller=None, **kwargs):
        """
        Returns a path to the target from either a source location or the
        caller's current location.

        """
        assert any((source, caller))

        net = self.network
        assert net.size()

        src = source or caller
        if src.location:
            src = src.location

        dst = target
        if dst.location:
            dst = dst.location

        # Now that we have a graph of all possible ways the source can get to
        # the destination, calculate the shortest path
        try: path = nx.shortest_path(net, source=src, target=dst)
        except nx.NetworkXNoPath: path = []
        except nx.NodeNotFound: path = []

        return tuple(path)

    def get_tile(self, obj, *args, **kwargs) -> str:
        """
        Creates a generic 2-character "tile" representing a room on the grid.

        i.e. Dungeon = 'DN', Front Yard = 'FY'

        """
        # If a tile was explicitly set on the object, use that.
        tile = obj.db.tile
        if tile: return tile

        # If there are spaces in the room name, use the first letter
        # from the first and last words.
        if obj.key.count(' ') > 0:
            words = obj.key.split(' ')
            first = words[0][0]
            last = words[-1][0]

        # If no space in the room name, use the first letter and nearest consonant.
        else:
            first = obj.key[0]
            last = next((x for x in obj.key.lower()[1:] if x not in ('a','e','i','o','u')), obj.key[-1])

        return '|w'+(first + last).upper()+'|n'

    def get_map(self, location=None, *args, ttl=14, width=None, height=None, **kwargs):
        """
        Returns a 2d grid map of the caller's surroundings.

        """
        net = self.network

        # Center on caller location
        source = getattr(self.obj, 'location', None)

        # Create subgraph based on cardinal directions only
        edges = tuple((u,v,data['obj']) for u,v,data in net.edges(data=True) if data['obj'] == source or data['obj'].key in ('north', 'south', 'east', 'west', 'northwest', 'southwest', 'northeast', 'southeast'))
        try: subgraph = nx.ego_graph(net.edge_subgraph(edges), source, radius=ttl*2)
        except:
            # If source room does not exist, create a blank map
            subgraph = nx.DiGraph()
            if source: subgraph.add_node(source)
            
        targets = tuple(x for x in subgraph.nodes() if x != source)
            
        paths = nx.all_simple_paths(subgraph, source, targets, cutoff=ttl*2)

        # Create map grid
        grid = nx.grid_2d_graph(ttl, ttl)

        # Center at mid-grid
        x = y = ttl//2
        
        def color(chars):
            return f'|x{chars}|n'

        grid.add_node((x,y), key='|y**|n')
        for path in paths:
            # Re-center
            x = y = ttl//2

            for src, dst in nx.utils.pairwise(path):
                key = subgraph[src][dst]['key']

                if key == 'north':
                    y = y - 2
                    if x >= 0 and y >= 0: grid.add_node((x,y+1),key=color('::'))
                elif key == 'south':
                    y = y + 2
                    if x >= 0 and y >= 0: grid.add_node((x,y-1),key=color('::'))
                elif key == 'west':
                    x = x - 2
                    if x >= 0 and y >= 0: grid.add_node((x+1,y), key=color('=='))
                elif key == 'east':
                    x = x + 2
                    if x >= 0 and y >= 0: grid.add_node((x-1,y), key=color('=='))
                elif key == 'northeast':
                    x = x + 2
                    y = y - 2
                    if x >= 0 and y >= 0: grid.add_node((x-1,y+1), key=color('//'))
                elif key == 'southeast':
                    x = x - 2
                    y = y + 2
                    if x >= 0 and y >= 0: grid.add_node((x+1,y-1), key=color('\\\\'))
                elif key == 'northwest':
                    x = x - 2
                    y = y - 2
                    if x >= 0 and y >= 0: grid.add_node((x+1,y+1), key=color('\\\\'))
                elif key == 'southwest':
                    x = x - 2
                    y = y + 2
                    if x >= 0 and y >= 0: grid.add_node((x+1,y-1), key=color('//'))

                if not (x >= 0 and y >= 0): continue
                if not grid.nodes[(x,y)]:
                    grid.add_node((x,y),key=self.get_tile(self.ndb.lookups.get(dst)))

        rows = []
        for y in range(ttl):
            rows.append(tuple(grid.nodes[(x,y)].get('key', self.TILE_BLANK) for x in range(ttl)))

        # Do cropping and rendering
        try: map_height = len(rows)
        except: map_height = 0
        
        try: map_width = len(rows[0])
        except: map_width = 0
        
        height = min((x for x in (height, settings.CLIENT_DEFAULT_HEIGHT) if x))
        width = min((x for x in (width, settings.CLIENT_DEFAULT_WIDTH) if x))
        
        # Pad to requested height
        if height > map_height:
            diff = height - map_height
            padding = [[self.TILE_BLANK for x in range(map_width)] for y in range(diff//2)]
            rows = padding + list(rows) + padding
            map_height = len(rows)
            
        # Pad to requested width
        if width > map_width * 2:
            diff = width - map_width * 2
            padding = [self.TILE_BLANK for x in range(diff//2)]
            rows = [padding + list(r) + padding for r in rows]
            map_width = len(rows[0])
        
        # Crop to requested height
        if height < map_height:
            diff = height // 2
            midpoint = map_height // 2
            
            start = midpoint - diff
            final = midpoint + diff
            if final % 2 == 0:
                final = final + 1
            
            rows = rows[start:final]
            
        # Crop to requested width
        if width < map_width * 2:
            diff = (width // 2)
            midpoint = map_width // 2
            
            start = midpoint - (diff//2)
            final = midpoint + (diff//2)
            if final % 2 == 0:
                final = final + 1
            
            rows = [row[start:final] for row in rows]
            map_width = len(rows[0])
        
        rows = (''.join(x) for x in rows)
        return '\n'.join(rows)