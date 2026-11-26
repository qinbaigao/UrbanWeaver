# CityG 场景编辑模式

CityG 的编辑模式在已有场景上执行可追踪、可验证、可回滚的修改。原始场景默认只读，编辑结果写入新的版本目录。

## 命令

```bash
PYTHONPATH=src python -m cityg agent-edit \
  --scene outputs/city_001 \
  --instruction "将 building_03 的外立面改成玻璃幕墙" \
  --output outputs/city_001_edit_01
```

`--scene` 可以是运行目录、`final/`、`final/openusd/` 或一个 `city.json`。系统优先读取规范化的 `city.json`，不会把 USD 或 Viewer 派生文件当作编辑源。

## 安全行为

编辑 Agent 只输出结构化 `EditPlan`，不直接写 USD 或任意文件。确定性层负责：

- 根据场景实体索引绑定建筑、楼层、房间和物体；目标可使用旧 ID、稳定 UID、完整层级 path 或唯一 display name（见 `naming_convention.md`）；
- 检查目标置信度、补丁范围和实体版本；
- 通过 `PatchEngine` 在副本上原子应用低风险编辑；
- 运行语义验证、几何验证和交互验证；
- 编译新的 OpenUSD 和 Portable Viewer。

立面材质的精确字段编辑支持 `appearance_plan.material_family`（或带
`metadata.` 前缀）的窄范围别名，可取 brick/plaster/stone/metal/glass。
系统在副本中深度合并该字段，保留其它建筑元数据和室内；仍检查已接受的材质范围，
不允许任意嵌套 CCWP 路径。非法字段在提案阶段返回给模型预算内纠正，不等到发布时才失败。

对带唯一稳定目标 ID 的明确引号改名，以及绑定具体楼层的阿拉伯数字房间数，编辑器从原指令提取
有限的硬后置条件，模型不能遗漏或改低；发布前再次核验实际名称/非走廊房间数。
英文千位分隔符、independent offices、non-corridor rooms、非走廊房间等数量表达可以识别。
多个明确 ID/UID/path 可以用“每层 N 间”共享目标数量，或逐个分句指定不同数量。
“两个楼层共 N 间”没有明确分配时请求澄清，不自行解释为每层 N 间。
模型省略冗余 targets 数组时，只能从用户原文中的明确 ID 补全所有目标；
不会因为某个 ID 在场景中存在就赋予它编辑权限。明确超出当前楼层
子树替换的 1～64 间范围时不执行、不按旧数量重建。这不是任意自然语言的完整验收，
更复杂的多目标数量分配、非字面风格要求仍需其它契约和视觉证据。

单个明确建筑目标的字面层数及“每层 N 个房间”也会进入硬后置条件，
要求 `building_subtree` 提案保留精确数量并在发布前检查实际结果。
建筑替换支持 1～128 层；非法数量不再截断、夹取或改回原层数。
不同层高的楼层按前面所有楼层的累计高度确定标高，避免首层较高时出现重叠。

已有场景的房间编辑默认恢复该场景包固定的资产注册表，使用仅本地的 resolver；
不会因为读取一个已编译场景而自动获得资产生成权限。已接受的家具可以保留原型内
特定用途（如起居室工作角的办公椅），不修改全局资产标签。整房重排的验收同时检查
主要家具类别的 mesh 数量，不能靠重新命名物体绕过“GLB 退化成程序化方块”的检查。

回滚恢复目标版本的已编译几何和资产绑定，以及立面模块与是否编译室内的配置。
存在几何清单时直接重新导出该清单，不从精简后的便携注册表重新随机选择装饰资产。
源文件始终保留；生成器源码或外部资产文件本身不属于场景版本回滚的范围。

VLM 房间局部修复同时支持设计局部组 ID 和实际物体记录证明的编译组 ID；
只做本房间内的一对一绑定，不靠名称前缀猜测，不把未知组扩大为整房修改。

如果指令包含无法唯一确定的指代，例如“把这栋楼改成办公楼”“在这块空地增加喷泉”，并且场景中存在多个候选实体，系统返回 `needs_clarification`，不产生任何场景修改。请提供稳定 ID（例如 `building_03`）或更具体的位置、功能和相邻关系。

结构性修改不会被伪装成简单属性补丁，而是通过三种子树级事务完成：`floor_layout` 重建一个楼层的房间、门和家具引用；`building_subtree` 重建整栋楼的楼层栈和垂直交通，并逐层重建房间；`urban_subgraph` 在城市、区域或地块子图内更新功能、边界、建筑和道路属性。每种事务都在副本上重建 CCWP 并完整验证，失败时源场景不变。

`building_profile` 仍调用 Building Refinement Agent 更新受约束的建筑外观/体量元数据；`room_furnishing` 仍调用 Room Program Agent 重新生成目标房间的家具程序。结构性请求必须绑定到正确的根节点类型（floor/building/city-district-parcel）。

低层 API 也可以直接使用：

```python
from cityg.subtree_transactions import FloorSubtreePlanner, BuildingSubtreePlanner, UrbanSubgraphPlanner

edited = FloorSubtreePlanner().replace(city, "building_000_floor_02", {"room_count": 12}).city
edited = BuildingSubtreePlanner().replace(edited, "building_000", {"floor_count": 18}).city
edited = UrbanSubgraphPlanner().replace(edited, "district_00", {"function": "commercial"}).city
```

事务结果包含 `created_ids`、`removed_ids`、`replaced_ids`、验证报告和可审计的 `metadata`。调用方应把结果作为新版本保存，不覆盖输入场景。

编辑计划还可以提出 `asset_requests`。当使用 `--asset-registry` 时，系统先查本地资产库；配合 `--generate-missing-assets` 和 Hunyuan Worker，可在有缺失资产时有界生成，并把成功资产绑定到明确的室内物体。

编辑后可选运行 VLM 复查：

```bash
PYTHONPATH=src python -m cityg agent-edit \
  --scene outputs/city_001 \
  --instruction "检查 building_03 的外立面并修复明显错位" \
  --output outputs/city_001_edit_02 \
  --visual-review --auto-vlm-refine
```

`--visual-review` 生成局部自适应观察和报告；`--auto-vlm-refine` 才允许有界的 Building/Room/Streetscape 修复写回新版本。VLM 不可用时，已经通过确定性验证的编辑仍然保留，错误记录在 `visual_review_result.json`。

## 输出

```text
city_001_edit_01/
├── base_scene_ref.json       # 原场景路径、规范文件和哈希
├── edit_request.json
├── edit_plan.json            # 模型计划和尝试记录
├── patch.json                # 已提交的低风险补丁
├── validation_before.json
├── validation_after.json
├── edit_result.json
├── final/city.json
├── final/openusd/             # OpenUSD 后端输出
└── viewer/                    # Portable Viewer（未使用 --no-viewer 时）
```

当输入场景包含旧的 `geometry_manifest.json` 时，建筑、楼层、房间和家具编辑会尝试使用现有的建筑级增量编译；道路、城市边界等全局编辑仍应回退到全量编译。

规划重试耗尽时，不发布最终目录；私有 `.目标名.pending-*` 诊断目录中保存
`edit_plan_failure.json` 的原始响应、错误、usage 和提示词，以及 `publication_failure.json`。

## 批量编辑和回滚

批量文件可以是 JSON 字符串数组，也可以是每行一条指令：

```bash
PYTHONPATH=src python -m cityg batch-edit \
  --scene outputs/city_001 \
  --instructions-file edits.txt \
  --output outputs/city_001_batch
```

每一步保存在 `steps/step_NN/`。遇到模糊指代或结构性未支持操作时，批处理会暂停，不会继续猜测后续指令。

从编辑版本恢复到其 `base_scene_ref.json` 记录的源场景：

```bash
PYTHONPATH=src python -m cityg rollback \
  --scene outputs/city_001_edit_01 \
  --output outputs/city_001_rollback
```

也可以用 `--to PATH` 显式指定任意历史场景。回滚同样写入新目录，不覆盖已有版本。

## 当前支持范围

通过 `building_site` 可以在原地块内整体平移建筑，或调整外壳建筑、规则精装低层及具有可验证楼板的精装塔楼的面积和宽深比。例如“把 building_002 向东移动 0.5 米”或“将 building_000 的占地扩大到 125 平方米，保留现有家具”。精装缩放会检查现有家具组合能否放进调整后的房间。高层示例：“把 building_000 的占地改成 1845 平方米，保留会议室原有桌椅；如果隔墙调整仍放不下，允许在相同面积下调整建筑长宽比。” 单纯给出面积会保留原有长宽比。参数与适用范围见[城市空间协同](urban_spatial_coordination.md)。
