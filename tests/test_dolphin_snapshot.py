import sys,tempfile,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dolphin_view
S=types.SimpleNamespace
calls={'bridge':0}
class Node:
 def __init__(self,role,name='',children=(),active=False,selected=False,rect=(0,0,100,100)):
  self.role,self.name,self.children,self.active,self.selected,self.rect=role,name,list(children),active,selected,rect
 def get_role_name(self):return self.role
 def get_name(self):return self.name
 def get_child_count(self):return len(self.children)
 def get_child_at_index(self,i):return self.children[i]
 def get_state_set(self):return S(contains=lambda state:self.active if state==1 else self.selected)
 def get_component_iface(self):return S(get_extents=lambda _:S(x=self.rect[0],y=self.rect[1],width=self.rect[2],height=self.rect[3]))
class Bus:
 def call_sync(self,*a):calls['bridge']+=1
root=Node('desktop')
atspi=S(set_timeout=lambda *a:None,StateType=S(ACTIVE=1,SELECTED=2),CoordType=S(SCREEN=1),get_desktop=lambda _:root)
gio=S(bus_get_sync=lambda *a:Bus(),BusType=S(SESSION=1),DBusCallFlags=S(NONE=0))
glib=S(Variant=lambda *a:a)
old_gi = sys.modules.get('gi')
old_repository = sys.modules.get('gi.repository')
sys.modules['gi']=S(require_version=lambda *a:None)
sys.modules['gi.repository']=S(Atspi=atspi,Gio=gio,GLib=glib)
with tempfile.TemporaryDirectory() as folder:
 names=['z.png','b.png','a.png']
 for name in names:Path(folder,name).touch()
 children=[Node('list item',name,selected=name=='b.png',rect=(i*140,10,100,100)) for i,name in enumerate(names)]
 view=Node('list',Path(folder).name,children)
 # Irrelevant lists must not be mistaken for the file view.
 wrong=Node('list','Elsewhere',[Node('list item','z.png')])
 root.children=[Node('application','Dolphin',[Node('frame',children=[wrong,Node('filler',children=[view])],active=True)])]
 for _ in range(2):
  result=dolphin_view.snapshot(str(Path(folder,'b.png')))
  assert [Path(i['path']).name for i in result['items']]==names,result
 assert calls['bridge']==1
for key, old in [('gi', old_gi), ('gi.repository', old_repository)]:
 if old is None:sys.modules.pop(key, None)
 else:sys.modules[key] = old
print('Passed source-view traversal, display order, coordinates, unrelated-view pruning, and single bridge activation.')
