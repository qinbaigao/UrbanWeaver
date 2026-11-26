# 基础城市参数规格（历史样例）

这 10 个规格用于验证 CityG 从低层住宅到高密度混合城区的基础参数范围，而不是最终
CityG-Bench。每个文件都必须满足：

- 可由 `CitySpec.from_dict` 解析；
- 当前确定性基线能生成指定数量建筑；
- 生成结果通过所有结构验证器；
- 使用固定 seed 可以精确重放。

`10_scalability_stress.json` 是 CPU 语义规划压力样例，不代表当前完整多智能体流程、
真实物理或高保真 Viewer 的性能。后续 CCWP/几何/交互已在项目中扩展；本目录不再作为
未来 Phase 1 待办，也不作为最终论文基准。当前研究设计见
[研究路线](../../docs/research_roadmap.md)，支持范围见[限制说明](../../docs/current_limits_and_resolution_plan.md)。

未显式填写布局参数的规格会使用可复现的 `organic_grid` 默认值。需要查看 30--50 栋建筑
的高密度视觉样例时可使用 `../mixed_district.json`；将 `layout_style` 设为
`regular_grid`、将 `road_pattern` 设为 `connected_grid` 并将
`buildings_per_block` 设为 1，可得到用于消融和调试的规则单建筑街区版本。

运行全部规格：

```bash
PYTHONPATH=src python scripts/validate_research_specs.py
```
