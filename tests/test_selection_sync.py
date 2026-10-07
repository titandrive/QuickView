import sys
from pathlib import Path
from types import SimpleNamespace as S
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dolphin_view as d
class Selection:
 def __init__(self):self.selected=[0];self.refuse=False
 def get_n_selected_children(self):return len(self.selected)
 def get_selected_child(self,i):return S(get_index_in_parent=lambda:self.selected[i])
 def clear_selection(self):self.selected=[];return True
 def select_child(self,i):
  if self.refuse and i==1:return False
  self.selected.append(i);return True
 def is_child_selected(self,i):return i in self.selected
selection=Selection()
child=S(get_name=lambda:'b.png',get_component_iface=lambda:None)
d._bound_view=S(get_child_at_index=lambda _:child,get_selection_iface=lambda:selection)
d._bound_items={'/example/b.png':{'source_index':1}}
assert d.select_path('/example/b.png')=={'selected':True}
assert selection.selected==[1]
selection.selected=[0,2]
assert 'error' in d.select_path('/example/b.png')
assert selection.selected==[0,2]
selection.selected=[0];selection.refuse=True
assert 'error' in d.select_path('/example/b.png')
assert selection.selected==[0]
selection.refuse=False;child.get_name=lambda:'changed.png'
assert 'error' in d.select_path('/example/b.png')
assert selection.selected==[0]
d._bound_view=None
assert 'error' in d.select_path('/example/b.png')
print('Passed selection following, multiple-selection preservation, failure rollback, stale model, and ambiguous-view protection.')
