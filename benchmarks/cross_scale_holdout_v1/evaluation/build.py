"""Authoring only. Writes a new bundle, never overwrites the frozen dataset."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from cityg.ccwp import build_world_program
from cityg.schemas import (Bounds2D, Building, City, District, Door, Floor, Junction, Parcel,
                           Point2D, RoadNetwork, RoadSegment, Room)
from cityg.serialization import to_primitive

# Each brief is used unchanged across its three counterfactual starting states.
# Site tuples: title, design brief, required frontage/depth, limiting feature, axis, mirror.
SITES = [
    ('旧报刊发行站','把发行站改成可并排收发晨报和包裹的街区配送点。',18,11,'parcel','x',False),
    ('社区修伞铺','雨季修伞铺要增设收件和晾伞工位，和旁边的便民亭继续共用这块地。',14,9,'neighbor','y',True),
    ('运河巡护所','巡护队想在巡护所内安排装备回收和换班区，请按改造通知调整首层。',16,12,'easement','y',False),
    ('公共洗衣站','把洗衣站的营业面扩开，顾客可以在同一层分开交件和取件。',20,10,'parcel','y',True),
    ('社区器材借用处','青少年活动日需要扩大器材借还点；同地块的维修亭照常使用。',17,10,'neighbor','x',False),
    ('临街花卉集配点','集配点需要扩容，临街装卸和花箱周转都在首层完成，检修用地要保留。',15,13,'easement','x',True),
]
# Relative coordinates are in frontage/depth coordinates, measured from a kit datum.
# Each part: asset category, centre u/v, size along u/v, height. Units: metres.
ROOMS = [
    ('街坊修理社','workshop','将维修工坊改为能同时拆装和分类零件的工作区。',[
        ('workbench',1,1,2,1,0.9),('storage_rack',4.4,1,1.6,.65,1.7)],.5,'x',False),
    ('长者服务处','waiting_room','到访量增加，请在等候室装好配送单上的双排候诊座位。',[
        ('waiting_bench',1,1,2,.75,.85),('waiting_bench',4,1,2,.75,.85),
        ('waiting_bench',1,2.65,2,.75,.85),('waiting_bench',4,2.65,2,.75,.85)],.6,'y',True),
    ('社区口述史档案室','study','为阅档室增加书架和资料核对桌，保留设备单给定的操作间隔。',[
        ('bookcase',.55,1,1.1,.5,1.8),('desk',3.05,1.8,1.8,.9,.75),
        ('bookcase',5,1,1.1,.5,1.8)],.4,'y',False),
    ('夜班调度站','control_room','把控制室布置成双人交接班工位，按装配图同时保留两把工作椅。',[
        ('desk',1,2,2,.9,.75),('office_chair',1,.8,.65,.65,1),
        ('desk',4.25,2,2,.9,.75),('office_chair',4.25,.8,.65,.65,1)],.45,'x',True),
    ('旧物寄售铺','shop','把陈列间改成三台展架组成的样品展示区，顾客浏览间距按交付图执行。',[
        ('display_shelf',.75,1,1.5,.7,1.4),('display_shelf',3,1.5,1.5,.7,1.4),
        ('display_shelf',5.25,1,1.5,.7,1.4)],.5,'x',False),
    ('片区周转库','storage','在分拣间安装成套货架，保留中间分拣位和周边操作带。',[
        ('storage_rack',.7,1,1.4,.8,1.8),('storage_rack',3.25,2,1.5,.8,1.8),
        ('storage_rack',5.65,1,1.3,.8,1.8)],.6,'y',True),
]
DEV_SITE=('校门失物招领站','运动会期间扩大招领站的首层接待面积。',13,8,'parcel','x',False)
DEV_ROOM=('园艺备料室','workshop','按设备清单装好一组园艺备料台。',[
    ('workbench',1,1,2,1,.9),('cabinet',3.6,1,1.2,.65,.8)],.45,'x',True)


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')


def build(split, family, kind, brief, condition, rng):
    title, axis, mirror = brief[0], brief[-2], brief[-1]
    key=rng.getrandbits(64)
    identifier=hashlib.sha256(str(key).encode()).hexdigest()[:12]
    origin=rng.randint(16,28)
    def pt(u,v):
        return Point2D(u,v) if axis=='x' else Point2D(v,u)
    def box(a,b,c,d):
        lo,hi=pt(a,b),pt(c,d)
        return Bounds2D(lo.x,lo.y,hi.x,hi.y)
    def shell(bid,name,fn,left,width,front,depth,partition=None):
        footprint=box(left,front,left+width,front+depth)
        entry=pt(left+width/2,front)
        fid=bid+'_g'
        if partition is None:
            hall=Room(fid+'_hall','营业厅','service_hall',box(left,front+2,left+width,front+depth))
            corridor=Room(fid+'_corr','公共门厅','corridor',box(left,front,left+width,front+2))
            rooms=[hall,corridor]
            doors=[Door(fid+'_entry',corridor.id,None,entry,1.2,'exterior'),
                   Door(fid+'_inside',hall.id,corridor.id,pt(left+width/2,front+2),1.0)]
        else:
            split_at, target_right, donor_door=partition
            wall=left+split_at
            lower=front+2.5
            a=Room(fid+'_a','业务室',fn,box(left,lower,wall,front+depth))
            b=Room(fid+'_b','后勤室','storage',box(wall,lower,left+width,front+depth))
            if target_right:
                a.name,a.function,b.name,b.function=b.name,b.function,a.name,a.function
            corridor=Room(fid+'_corr','沿街公共走廊','corridor',box(left,front,left+width,lower))
            rooms=[a,b,corridor]
            doors=[Door(fid+'_entry',corridor.id,None,entry,1.2,'exterior')]
            for index,rm in enumerate((a,b)):
                pos=(left+(width-1.5 if target_right else 1.5) if rm.name=='业务室' else donor_door)
                doors.append(Door(fid+f'_d{index}',rm.id,corridor.id,pt(pos,lower),1.0))
        use={'study':'public_service','waiting_room':'public_service','control_room':'industrial',
             'workshop':'industrial','shop':'commercial','storage':'industrial'}.get(fn,fn)
        return Building(bid,name,use,footprint,entry,[Floor(fid,0,0,3,rooms,doors)])
    target_id='pavilion'
    if kind=='site':
        _,intro,span,depth,feature,_,_=brief
        # All three regimes use the same permissions and the same goal.
        usable=span+([5,4,-2][condition])
        near=span/2+[1.25,-1.75,-1.5][condition]
        start=origin+4
        far=start+usable
        if mirror:
            center=far-near
        else:
            center=start+near
        # The external strip/neighbor limits the same side as the off-centre siting.
        extra=8 if feature!='parcel' else 0
        left=origin-(extra if not mirror else 0)
        right=far+4+(extra if mirror else 0)
        pbox=box(left,14,right,14+depth+12)
        middle=14+6+depth/2
        target=shell(target_id,title,'commercial',center-3.5,7,middle-3,6)
        buildings=[target]; reserves=[]
        if feature!='parcel':
            lo,hi=(far,far+extra) if mirror else (start-extra,start)
            if feature=='neighbor':
                # A real, separately owned shell; the strip extends across the fixed centreline.
                buildings.append(shell('kiosk','保留的便民亭','public_service',lo,hi-lo,middle-2.5,5))
            else:
                reserves=[to_primitive(box(lo,14,hi,14+depth+12))]
        rules=dict(kind='site',target=target_id,parcel='plot',span_axis=axis,min_span_m=span,
                   min_depth_m=depth,setback_m=4,keepout_boxes=reserves)
        instr=(intro+f'请在现有地块内实现至少 {span} 米临街面宽和 {depth} 米进深，四边退界至少 4 米。'
               '入口继续面向原道路，建筑中心到街道的垂直距离保持不变；沿街位置可以调整。'
               '保留道路、地块内其他建筑和图上标出的预留地。楼壳保持矩形。')
    else:
        _,fn,intro,parts,gap,_,_=brief
        maxu=max(u+w/2 for _,u,v,w,d,h in parts)
        minu=min(u-w/2 for _,u,v,w,d,h in parts)
        needed=round(maxu-minu+2*gap,4)
        target_width=round(needed+([1.1,-.75,-1.1][condition]),4)
        donor_min=[4.,4.5,4.,4.5,5.,5.5][family%6]
        # Alternate between a limiting donor width and a limiting fixed donor doorway.
        donor_width=donor_min+([2.,3.25,.45 if family%2==0 else 3.5][condition])
        width=round(target_width+donor_width,4); left=origin+5
        donor_offset=.86 if condition==2 and family%2 else donor_width-1.0
        donor_door=left+(width-target_width-donor_offset if mirror else target_width+donor_offset)
        target=shell(target_id,title,fn,left,width,20,11,
                     (width-target_width if mirror else target_width,mirror,donor_door))
        target_room=target.floors[0].rooms[int(mirror)]
        donor=target.floors[0].rooms[int(not mirror)]
        buildings=[target];pbox=box(origin,14,left+width+7,41)
        rules=dict(kind='interior',target=target_id,room=target_room.id,donor=donor.id,
                   floor=target.floors[0].id,span_axis=axis,min_donor_span_m=donor_min,
                   wall_gap_m=gap,door_jamb_m=.35,door_keep_clear_depth_m=1.35,
                   kit=[dict(id=f'kit_{n+1}',category=c,offset_uv_m=[u,v],
                             size_uvh_m=[w,d,h]) for n,(c,u,v,w,d,h) in enumerate(parts)])
        instr=(intro+f'设备放在业务室，按附件保持尺寸、相对位置及方向，各边距墙至少 {gap:g} 米。'
               f'后勤室沿街方向的净宽至少 {donor_min:g} 米。仅两室之间的隔墙可微调；'
               '现有门洞、公共走廊、楼壳和其他建筑都要保留，门两侧留足 0.35 米墙垛、门内 1.35 米净空。')
    parcels=[Parcel('plot',pbox,buildings)]
    for j in range(3+family%3):
        u=70+j*23
        neighbor=shell('shop_'+str(j),'沿街邻楼'+str(j+1),'commercial',u+5,10,20,10)
        parcels.append(Parcel('plot_'+str(j),box(u,14,u+21,40),[neighbor]))
    bounds=box(0,0,200,60)
    roads=RoadNetwork([Junction('j0',pt(0,8)),Junction('j1',pt(200,8))],
                      [RoadSegment('main','j0','j1',(pt(0,8),pt(200,8)),width_m=8)])
    city=City('city_'+identifier,title+'街区',bounds,roads,[District('district','沿街服务区','commercial',bounds,parcels)],
              metadata={'parcel_setback_m':4.})
    city.world_program=build_world_program(city,producer='benchmark_input',seed=key%1000000)
    public=dict(id=identifier,scene=f'scenes/{identifier}.json',instruction=instr,request=rules)
    private=dict(id=identifier,family=f'{kind}_{family:02d}',split=split,
                 expected=['local','cross_scale','infeasible'][condition])
    return public,private,city


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('new_directory',type=Path)
    root=parser.parse_args().new_directory
    root.mkdir(parents=True,exist_ok=False)
    rng=random.Random(519837102)
    for split,sites,rooms in [('development',[DEV_SITE],[DEV_ROOM]),('test',SITES,ROOMS)]:
        records=[];gold=[]
        for kind,briefs in [('site',sites),('interior',rooms)]:
            for family,brief in enumerate(briefs):
                for condition in range(3):
                    task,label,city=build(split,family,kind,brief,condition,rng)
                    dump(root/split/task['scene'],to_primitive(city))
                    records.append(task);gold.append(label)
        rng.shuffle(records)
        for path,rows in [(root/split/'tasks.jsonl',records),(root/'evaluation'/f'{split}_labels.jsonl',gold)]:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))


if __name__=='__main__':
    main()
