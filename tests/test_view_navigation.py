import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from view_navigation import target_index

def grid(names,cols=3):
 return [{'path':n,'rect':[i%cols*140,i//cols*137,125,88 if i%2 else 124]} for i,n in enumerate(names)]
items=grid(['z','a','q','b','m','c','x','d'])
assert target_index(items,'a','right')==2
assert target_index(items,'a','down')==4
assert target_index(items,'m','up')==1
assert target_index(items,'c','down')==7  # partial last row chooses nearest column
assert target_index(items,'z','left')==0
assert target_index(items,'d','down')==7
assert target_index(items,'missing','right') is None
for direction,expected in [('left',0),('up',0),('right',2),('down',2)]:
 assert target_index(grid(['z','a','q'],1),'a',direction)==expected
assert target_index([], 'a','right') is None
# Scrolling translates all y values and does not change navigation.
scrolled=[{'path':i['path'],'rect':[i['rect'][0],i['rect'][1]-318,*i['rect'][2:]]} for i in items]
assert target_index(scrolled,'a','down')==4
for p in Path(__file__).resolve().parents[1].glob('*.py'):compile(p.read_text(),str(p),'exec')
print('Passed display order, grid rows, list mode, variable heights, boundaries, partial rows, scroll offsets, and syntax checks.')
