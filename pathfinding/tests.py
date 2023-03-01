from .topology import *
from evennia.utils.test_resources import EvenniaTest
from evennia.utils.utils import class_from_module


class TopologyTest(EvenniaTest):
    
    def setUp(self):
        super().setUp()
        plans = (
            ('node1', 'node2', 'north'),
            ('node7', 'node1', 'northeast'),
            ('node1', 'node7', 'southeast'),
            ('node2', 'node3', 'north'),
            ('node3', 'node4', 'east'),
            ('node4', 'node5', 'south'),
            ('node5', 'node6', 'south'),
            ('node1', 'node6', 'east'),
        )
        Room = self.Room = class_from_module(self.room_typeclass)
        Exit = self.Exit = class_from_module(self.exit_typeclass)
        
        for src, dst, way in plans:
            source = Room.objects.filter(db_key=src).first() or Room.create(src, self.account)[0]
            target = Room.objects.filter(db_key=dst).first() or Room.create(dst, self.account)[0]
            self.assertTrue(source.id)
            self.assertTrue(target.id)
            exit = Exit.create(way, source, target, account=self.account)[0]
    
    def test_stuff(self):
        topo = Topology(self.char1, queryset=self.Exit.objects.all())
        
        print(topo.to_json())
        
        node1 = self.Room.objects.get(db_key='node1')
        node6 = self.Room.objects.get(db_key='node6')
        print(topo.get_path(node1, node6))