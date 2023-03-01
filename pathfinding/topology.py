from evennia.objects.objects import DefaultExit
from evennia.locks.lockhandler import check_lockstring
from collections import defaultdict


class Topology(object):

    def __init__(self, obj=None, *args, queryset=DefaultExit.objects, **kwargs):
        self._obj = obj
        self._model = obj.__dbclass__.__class__
        self._qs = queryset.all()
        self._graph = self.get_graph(caller=obj)

    def __get__(self, instance, model):
        self._obj = instance
        self._model = model
        self._graph = self.get_graph(caller=instance)
        return self
        
    def to_json(self, *args, indent=2, **kwargs):
        import json
        return json.dumps({k.id:tuple(v.id for v in vs) for k,vs in self._graph.items()}, indent=indent)
        
    def get_graph(self, *args, caller=None, **kwargs):
        graph = defaultdict(set)
        for edge in self._qs:
            if caller:
                if not edge.access(caller, 'traverse', default=True, no_superuser_bypass=True):
                    continue
            
            graph[edge.location].add(edge)
            graph[edge].add(edge.destination)
                
        return {k:tuple(v) for k,v in graph.items()}
        
    def get_path(self, source, target, *args, caller=None, **kwargs):
        """
        Function to find the shortest path between two nodes of a graph.
        
        https://www.geeksforgeeks.org/building-an-undirected-graph-and-finding-shortest-path-using-dictionaries-in-python/
        
        """
        graph = self.get_graph(*args, caller=caller, **kwargs)
        
        explored = []
         
        # Queue for traversing the graph in the BFS
        queue = [[source]]
         
        # If the desired node is reached
        if source == target:
            return
         
        # Loop to traverse the graph with the help of the queue
        while queue:
            path = queue.pop(0)
            node = path[-1]
             
            # Condition to check if the current node is not visited
            if node not in explored:
                neighbours = graph[node]
                 
                # Loop to iterate over the neighbours of the node
                for neighbour in neighbours:
                    new_path = list(path)
                    new_path.append(neighbour)
                    queue.append(new_path)
                     
                    # Condition to check if the neighbour node is the target
                    if neighbour == target:
                        return tuple(x for x in new_path if x.destination)

                explored.append(node)
     
        # Condition when the nodes are not connected
        return