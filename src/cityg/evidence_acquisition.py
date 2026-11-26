"""Budgeted, version-bound acquisition of structural queries and visual views.

Coverage/cost is an explicit heuristic, not calibrated information gain. A
provider must attest what its evidence actually supports. Selecting an action
alone never marks a requirement satisfied, and evidence cannot authorize edits.
"""
from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class EvidenceAction:
    id: str
    kind: str  # query or view
    target_id: str
    version: str
    supports: tuple[str, ...]
    estimated_cost: float
    payload: dict = field(default_factory=dict)


class EvidenceSession:
    def __init__(self, target_id, version, requirements, *, budget, max_actions=3, max_views=2):
        if not target_id or not version or not requirements:
            raise ValueError('Evidence needs a bound target, version and requirements')
        if (type(budget) not in (int,float) or not math.isfinite(budget) or budget<=0
                or type(max_actions) is not int or max_actions<1
                or type(max_views) is not int or max_views<0):
            raise ValueError('Invalid acquisition budget')
        self.target_id,self.version=target_id,version
        self.pending=set(requirements);self.budget=float(budget)
        self.max_actions,self.max_views=max_actions,max_views
        self.spent=0.;self.views=0;self.receipts=[];self.seen=set()

    def eligible(self, action):
        if (action.kind not in {'query','view'} or type(action.estimated_cost) not in (int,float)
                or not math.isfinite(action.estimated_cost) or action.estimated_cost<=0):
            raise ValueError('Invalid evidence action')
        return (action.target_id==self.target_id and action.version==self.version
            and action.id not in self.seen and len(self.receipts)<self.max_actions
            and bool(self.pending.intersection(action.supports))
            and self.spent+action.estimated_cost<=self.budget+1e-9
            and (action.kind!='view' or self.views<self.max_views))

    def choose(self, actions):
        if len({a.id for a in actions})!=len(actions):raise ValueError('Duplicate evidence action IDs')
        available=[a for a in actions if self.eligible(a)]
        if not available:return None
        return min(available,key=lambda a:(-len(self.pending.intersection(a.supports))/a.estimated_cost,
                                           a.estimated_cost,a.id))

    def acquire(self, action, provider):
        if not self.eligible(action):raise ValueError('Stale, irrelevant, duplicate or over-budget action')
        # Failed attempts still cost resources; retries require a distinct action.
        self.seen.add(action.id);self.spent+=action.estimated_cost;self.views+=action.kind=='view'
        row={'action_id':action.id,'kind':action.kind,'estimated_cost':action.estimated_cost,
             'pending_before':sorted(self.pending),'accepted':False}
        self.receipts.append(row)
        try:
            evidence=provider(action)
            matched=(evidence.get('target_id')==self.target_id and evidence.get('version')==self.version)
            supported=set(evidence.get('supports',()))
            ready=evidence.get('ready') is True
            # Providers cannot promote a query into a visual observation or
            # answer unrelated needs by inventing broader coverage.
            if matched and ready and supported<=set(action.supports):
                self.pending.difference_update(supported);row['accepted']=True
            row.update(evidence=evidence,pending_after=sorted(self.pending))
        except Exception as exc:
            row.update(error=f'{type(exc).__name__}: {exc}',pending_after=sorted(self.pending))
        return row

    def report(self):
        return {'target_id':self.target_id,'version':self.version,'complete':not self.pending,
                'pending':sorted(self.pending),'estimated_cost':self.spent,'budget':self.budget,
                'views':self.views,'receipts':self.receipts,
                'cost_units':'declared acquisition proxy units; not actual token counts',
                'state_mutation_authorized':False}
