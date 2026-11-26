"""First, offline cross-level integration checkpoint; never mutate a saved city."""
import argparse
from pathlib import Path
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.urban_prototypes import UrbanPrototypeLibrary
from cityg.planning.prototype_integration import integration_preflight
from cityg.serialization import load_city,save_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--city',type=Path)
    source.add_argument('--urban-prototype')
    p.add_argument('--library',type=Path,default=Path('configs/layout_prototypes/v1'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-buildings',type=int,default=3)
    p.add_argument('--max-floors',type=int,default=2)
    p.add_argument('--variation-limit',type=float,default=.2)
    a=p.parse_args()
    if a.output.exists():p.error('Use a fresh report path')
    city=load_city(a.city) if a.city else UrbanPrototypeLibrary(a.library).plan(a.urban_prototype)
    report=integration_preflight(city,FloorPrototypeLibrary(a.library),max_buildings=a.max_buildings,
        max_floors=a.max_floors,variation_limit=a.variation_limit)
    save_json(report,a.output)
    print(report['summary']);print('Read-only preflight:',a.output)


if __name__=='__main__':main()
