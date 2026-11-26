"""Bounded pedestrian routing with continuous segment/width clearance checks."""
import heapq
import math

from cityg.polygons import geos


def route_in_polygon(start, end, free, width=1.8, step=2.0, budget=6000):
    """Return a polyline whose complete round-capped surface fits free space.

    Grid A* is only the search scaffold. Every edge and simplified segment is
    tested continuously, so diagonal corners cannot cut across a flower bed.
    """
    s = geos(); clearance = free.buffer(-width/2-.03)
    a,b = tuple(start),tuple(end)
    if not clearance.covers(s.Point(a)) or not clearance.covers(s.Point(b)):
        return None
    def clear(x,y):
        return clearance.covers(s.LineString([x,y]))
    if clear(a,b):
        return [a,b]
    x0,y0,_,_ = clearance.bounds
    def point(key):return (x0+key[0]*step,y0+key[1]*step)
    origin=(round((a[0]-x0)/step),round((a[1]-y0)/step))
    scores={}; parents={}; queue=[]
    for dx in range(-1,2):
        for dy in range(-1,2):
            key=(origin[0]+dx,origin[1]+dy);p=point(key)
            if clear(a,p):
                cost=math.dist(a,p);scores[key]=cost;parents[key]=None
                heapq.heappush(queue,(cost+math.dist(p,b),cost,key))
    visited=set();goal=None
    while queue and len(visited)<budget:
        _,cost,key=heapq.heappop(queue)
        if key in visited:continue
        visited.add(key);p=point(key)
        if math.dist(p,b)<=step*2 and clear(p,b):
            goal=key;break
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nxt=(key[0]+dx,key[1]+dy);q=point(nxt)
            g=cost+math.dist(p,q)
            if g<scores.get(nxt,math.inf) and clear(p,q):
                scores[nxt]=g;parents[nxt]=key
                heapq.heappush(queue,(g+math.dist(q,b),g,nxt))
    if goal is None:return None
    chain=[b];key=goal
    while key is not None:
        chain.append(point(key));key=parents[key]
    chain.append(a);chain.reverse()
    simplified=[chain[0]];i=0
    while i<len(chain)-1:
        j=len(chain)-1
        while j>i+1 and not clear(chain[i],chain[j]):j-=1
        simplified.append(chain[j]);i=j
    surface=s.LineString(simplified).buffer(width/2,quad_segs=4)
    return simplified if free.covers(surface) else None
