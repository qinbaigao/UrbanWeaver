# Third-party notices

Model weights, downloaded meshes, robot models, and textures are obtained separately under their upstream licenses. The registries keep source and license metadata for these optional assets.

## Redistributed browser dependency

Name: Three.js
Category: code
Version: 0.179.1
Upstream URL: https://github.com/mrdoob/three.js
Local paths: viewer/package.json, src/cityg/viewer_static/assets/
License and URL: MIT, https://github.com/mrdoob/three.js/blob/r179/LICENSE
Copyright/attribution: Copyright 2010-2025 three.js authors
Redistribution allowed: yes
Modifications: bundled and minified by Vite; CityG imports OrbitControls
Acquisition and checksum: pinned by viewer/package-lock.json
Notes: The complete MIT license text is retained below.

```text
The MIT License

Copyright (c) 2010-2025 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

When third-party source is added, record at least:

- project and upstream URL;
- copied files and local modifications;
- license and copyright notice;
- model, dataset, and asset licenses when applicable.

Use one entry per dependency or asset bundle:

```text
Name:
Category: code | model | dataset | mesh | texture | other
Version or commit:
Upstream URL:
Local paths:
License and URL:
Copyright/attribution:
Redistribution allowed: yes | no | conditional
Modifications:
Acquisition and checksum:
Notes:
```

Resources that cannot legally be redistributed must not be committed. CityG may
instead provide an acquisition/conversion script that requires users to accept the
upstream terms themselves.

## Optional runtime dependencies (not redistributed)

Name: ovphysx
Category: other (physics runtime dependency)
Version: 0.5.9
Upstream URL: https://github.com/NVIDIA-Omniverse/PhysX
Local paths: requirements/ovphysx.txt, environments/ovphysx.yml
License: LicenseRef-NVIDIA-Omniverse as published in the PyPI package metadata
Redistribution allowed: not evaluated; no wheel or source is redistributed by CityG
Notes: pre-release; installed separately by the user for Gate G2

Name: ovstage
Category: other (scene data runtime dependency)
Version: 0.1.0.346039
Upstream URL: https://github.com/NVIDIA-Omniverse/ovstage
Local paths: requirements/ovphysx.txt, environments/ovphysx.yml
License: NVIDIA Proprietary Software as published in the PyPI package metadata
Redistribution allowed: no CityG redistribution
Notes: exact transitive version required by ovphysx 0.5.9

Name: Tencent Hunyuan3D-2
Category: code and model (optional local integration; not redistributed)
Version: reference package 2.0.2; locally supplied checkpoints
Upstream URL: https://github.com/Tencent-Hunyuan/Hunyuan3D-2
Local paths: environments/hunyuan-assets.yml, src/cityg/hunyuan_asset_service.py
License: Tencent Hunyuan 3D 2.0 Community License Agreement
Redistribution allowed: conditional; CityG redistributes neither source nor weights
Notes: users must obtain the implementation and weights themselves, accept the
upstream license, and observe its territorial, use, notice, and commercial terms.
Generated records retain the model license identifier and generated-content flag.

Name: Innerscene construction equipment (seven models)
Category: optional downloaded 3D assets (not bundled with the code release)
Upstream URL: https://www.innerscene.com/tools/library/3d-parts/tag/vehicles
Local paths: assets/incoming/construction_innerscene, assets/prepared/construction_innerscene
License: CC0-1.0, as declared on each source model page
Author: Innerscene
Notes: backhoe loader, dump truck, concrete mixer truck, site cabin, mobile
scaffold, portable site toilet, and tower crane. Source pages, download URLs and
SHA256 hashes are retained in the preparation registry. Converted to Z-up unit
bounds with physical dimensions restored at placement; static equipment only.
Acquisition and preparation: scripts/prepare_construction_assets.py.

Name: HunyuanDiT-v1.1-Diffusers-Distilled
Category: model (optional local integration; not redistributed)
Version: v1.1 distilled Diffusers checkpoint
Upstream URL: https://huggingface.co/Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled
Local paths: environments/hunyuan-assets.yml, src/cityg/hunyuan_asset_service.py
License: Tencent Hunyuan Community License as identified by the model card
Redistribution allowed: conditional; CityG redistributes no weights
Notes: used only to produce an isolated reference image before image-to-3D.

Name: Exterior Aircon Unit (clean and rusted variants)
Category: optional downloaded 3D assets (not bundled with the code release)
Upstream URL: https://polyhaven.com/a/exterior_aircon_unit
Provider: Poly Haven
License: CC0-1.0
Local paths: assets/prepared/rooftop_v1
Notes: 1K textured GLB, split by source node into clean/aged variants and
normalized to Z-up, front +X. Physical height estimated at 1.2 m including
the hanging pipe; wall-mount brackets require support. Download URLs,
source metadata and hashes retained in the staging manifest and registry.
Rebuild using configs/roof_asset_pack.json and scripts/prepare_exterior_assets.py.

Name: Fir Sapling Medium, Fern 02, Shrub Sorrel 01, Grass Medium 01
Category: optional downloaded 3D assets (not bundled with the code release)
Provider: Poly Haven
Upstream URLs: https://polyhaven.com/a/fir_sapling_medium,
https://polyhaven.com/a/fern_02, https://polyhaven.com/a/shrub_sorrel_01,
https://polyhaven.com/a/grass_medium_01
License: CC0-1.0
Local paths: assets/prepared/urban_greenery_v1
Notes: 1K textures, selected standalone root nodes, Z-up normalization and
estimated physical heights. Seven of nine reviewed variants promoted; sorrel G
and tall grass remain candidate-only. Source metadata, URLs and hashes retained.
Rebuild using configs/urban_greenery_assets.json and scripts/prepare_exterior_assets.py.

## Figure 1 and the delivery film

The UrbanWeaver authors staged and rendered the city, interiors, robot poses and delivery sequence. The waterfront district and the two furnished interiors appear in both the paper overview and the film. The robot action is a scripted demonstration.

| Asset | Source and attribution |
|---|---|
| Fetch mobile manipulator | [Fetch Robotics, Fetch ROS](https://github.com/fetchrobotics/fetch_ros/tree/d22b98f6c21577895f4d2e3a8bd54e329083732b). The model was converted and posed or animated for these renders. The upstream model package declares [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). |
| Stretch mobile manipulator in Figure 1 | [Hello Robot Stretch, MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/62ab00f2bc44f6f20c1c9b7a13f3fb1dd41a4e35/hello_robot_stretch), BSD-3-Clause-Clear. The room illustration uses a staged serving pose. |
| Furnishings, plants and street props | [Poly Haven](https://polyhaven.com/models) (CC0), [HSSD](https://huggingface.co/datasets/hssd/hssd-models) and [OpenGameArt lamp, bench and trash can](https://opengameart.org/content/lamp-post-bench-trashcan) (CC0). |
| Pedestrians | [Microsoft Rocketbox avatars](https://github.com/microsoft/Microsoft-Rocketbox), MIT. |
| Vehicles and street fixtures | [Gazebo model database](https://github.com/osrf/gazebo_models), including the bus, bus stop, fountain, hatchback, pickup and Prius. The model directories provide their individual source and license information. |
