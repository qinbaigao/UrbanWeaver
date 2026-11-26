"""Paired saved-image diagnostic: add raw local metric evidence, not verdicts.

This is a precursor calibration for M2, NOT a joint acquisition policy or a
precision/recall benchmark. No scene changes or new rendering occur.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from cityg.adaptive_review import aggregate_visual_reviews
from cityg.run_provenance import source_snapshot
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.validation.visual_grounding import ground_review
from cityg.visual_review import VisualReviewAgent
from summarize_development_suite import visual_metrics


def local_geometry(city):
    result={}
    for b in city.iter_buildings():
        for f in b.floors:
            for r in f.rooms:
                if r.metadata.get('room_design',{}).get('status')!='accepted':continue
                result[r.id]={'coordinate_system':city.coordinate_system,
                    'building_orientation_deg':b.metadata.get('orientation_deg',0),
                    'room_bounds':to_primitive(r.bounds),
                    'objects':[{'id':o.id,'category':o.category,'group_id':o.metadata.get('group_key'),
                        'anchor_id':o.metadata.get('group_anchor_id'),'position':to_primitive(o.position),
                        'width_m':o.width_m,'depth_m':o.depth_m,'rotation_deg':o.rotation_deg,
                        'front_axis':o.metadata.get('front_axis'),
                        'orientation_confidence':o.metadata.get('orientation_confidence')}
                        for o in f.objects if o.room_id==r.id],
                    'doors':[to_primitive(d) for d in f.doors if r.id in (d.room_a_id,d.room_b_id)]}
    return result


class MetricReviewer(VisualReviewAgent):
    def __init__(self,*args,metrics,**kwargs):
        super().__init__(*args,**kwargs);self.metrics=metrics;self.payloads=[]

    def review(self,prompt,image_paths,*,context=None):
        context=deepcopy(context or {})
        context['queried_local_geometry']={k:self.metrics[k]
            for k in context.get('allowed_entity_ids',[]) if k in self.metrics}
        self.payloads.append(context['queried_local_geometry'])
        # Same inspection prompt and schema. Only the available evidence differs.
        return super().review(prompt,image_paths,context=context)


def run(config,sources,output):
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    endpoint=replace(ModelEndpoint(**config['endpoint']),seed=101,max_tokens=6144)
    save_json({'config':config,'overrides':{'seed':101,'max_tokens':6144},
        'sources':[str(p) for p in sources],'batch_size':2,'max_attempts':2,
        'manipulated_factor':'raw_geometry_context_available'},output/'config.json')
    rows=[]
    for index,source in enumerate(sources):
        source=source.resolve()
        city_path=source/'final/openusd/city.json'
        plan_path=source/'visual_review/observation_plan_before.json'
        images=source/'visual_review/observations_before'
        city=load_city(city_path);plan=json.loads(plan_path.read_text())
        plan['selected_views']=[v for v in plan['selected_views'] if v['kind']=='room_interior']
        plan.pop('issue_recheck_queue',None)
        paths=[city_path,plan_path,images/'asset_load_status.json']+[
            images/(v['view_id']+'.png') for v in plan['selected_views']]
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        if not plan['selected_views']:raise ValueError('Source has no room observations')
        save_json(hashes,output/f'{index}_input_fingerprints.json')
        metrics=local_geometry(city)
        order=['current_context','raw_metric_context'];random.Random(index+101).shuffle(order)
        for method in order:
            print('evidence_start',index,method,flush=True)
            service=OpenAICompatibleService(endpoint)
            reviewer=(MetricReviewer(service,metrics=metrics,max_images=2,max_attempts=2)
                      if method=='raw_metric_context' else
                      VisualReviewAgent(service,max_images=2,max_attempts=2))
            report=aggregate_visual_reviews(plan,images,reviewer,scene_id=city.id,batch_size=2)
            report=ground_review(city,report)
            save_json(report,output/f'{index}_{method}_review.json')
            if method=='raw_metric_context':
                save_json(reviewer.payloads,output/f'{index}_{method}_queried_geometry.json')
            row={'source':str(source),'method':method,'images':len(plan['selected_views']),
                **visual_metrics(report),
                'source_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())}
            rows.append(row)
            save_json({'evidence_type':'development_saved_image_raw_metric_evidence_ablation',
                'rows':rows,'scene_mutations':0,'joint_policy_tested':False,
                'limitations':['Existing generated rooms, not a balanced controlled defect dataset.',
                    'Raw object geometry is disclosed, never checker verdicts or expected issue labels.',
                    'The same production grounding checker labels reports; no independent human visual truth.',
                    'Fewer unsupported reports cannot establish improved recall or visual precision.',
                    'No adaptive action selection or shared structure/vision budget has been implemented here.',
                    'This is an availability ablation with measured costs, not an equal-token policy comparison.']},
                output/'summary.json')
            print('evidence_end',index,method,row,flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    a=p.parse_args();run(json.loads(a.config.read_text()),a.sources,a.output)
