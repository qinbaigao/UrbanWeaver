# Viewer 无头渲染

[English](headless_rendering.md) | **简体中文**

UrbanWeaver 可以直接用 Web Viewer 截图。Playwright 在无桌面的环境中启动 Chromium，`headless_capture.py` 使用 SwiftShader，在没有 RTX 显卡或 Isaac Sim 的服务器上也能运行。

Viewer 每次刷新几何都会开启新一轮资产加载。`window.citygObservation.waitForAssets` 跟踪尚未就绪的 GLB；当前资产全部加载成功或已采用替代几何后，渲染器才截图。`--wait-ms` 用于加载完成后短暂等待画面稳定。`render_observation_plan.py` 另有 `--asset-timeout-ms`，并将结果写入 `asset_load_status.json`。

如果截图用于判断家具或立面细节，应同时查看 `failed`、替代资产和代理几何的计数以及当前渲染模式。`ready=true` 也可能包含代理几何。自动截图不打开桌面浏览器标签页。每个视点的耗时分为相机调整、等待资产和截图三个部分。

自动截图会在页面初始化前注入第一个观察视点，默认采用 `review` 画质，从而避免提前加载整座城市的 HDR 和 PBR 资源。一组观察共用一个页面和场景图。只移动相机时可以复用几何，切换层级时也会复用已实例化的 GLB。报告包含 `render_profile`、`geometry_rebuild_count`、`visible_primitive_count`、`cached` 和加载计数。

## 安装

在运行项目的 Python 环境中安装 Playwright 和配套的 Chromium。下面以 `cityG` 环境为例。

```bash
conda activate cityG
python -m pip install playwright
python -m playwright install chromium
```

升级 Playwright 后，请重新安装与该版本匹配的浏览器二进制文件。浏览器保存在 Playwright 的缓存中。详见[官方安装文档](https://playwright.dev/python/docs/browsers)。

若 Linux 报告缺少共享库，且当前账号有系统安装权限，可以执行：

```bash
python -m playwright install --with-deps chromium
```

没有管理员权限时，可以先安装 Python 包和浏览器，再请管理员补齐缺少的系统库。

## 为单个视点截图

在仓库根目录打开两个终端。以下命令假设自然语言生成结果位于 `outputs/mixed_district`。终端 A 启动 Viewer 服务：

```bash
conda activate cityG
PYTHONPATH=src python -m cityg view outputs/mixed_district/final/openusd \
  --host 127.0.0.1 --port 5187 --no-browser
```

终端 B 设置视点并截图：

```bash
conda activate cityG
python scripts/headless_capture.py \
  --url http://127.0.0.1:5187 \
  --output outputs/mixed_district/visual_review/view.png \
  --width 1600 --height 1000 --wait-ms 5000 \
  --quality-profile review --mode overview
```

论文定稿图可用 `--quality-profile presentation`，需要与手动浏览的效果对应时可用 `interactive`。如需用 VLM 核对这张截图，执行：

```bash
PYTHONPATH=src python -m cityg visual-review \
  outputs/mixed_district/visual_review/view.png \
  --output outputs/mixed_district/visual_review/report.json
```

## 完整的自适应复查

以下命令会自行启动和关闭 Viewer 服务，负责修复前的观察以及修复后的局部复查：

```bash
PYTHONPATH=src python -m cityg adaptive-review \
  outputs/mixed_district/final/openusd \
  --output outputs/adaptive_review_run \
  --base-url http://127.0.0.1:8000/v1 \
  --model cityg-llm --max-tokens 1536 \
  --max-views 8 --max-building-refinements 1 --max-room-refinements 1
```

流程依次规划多尺度视点、分批调用 VLM、将问题绑定到指定类型的场景实体，然后在限定范围内调整街道、建筑或房间，重新编译 OpenUSD，并渲染变更区域。把 `--max-streetscape-refinements` 设为正数，可以对已绑定到街道的问题进行语义修复。

整组观察在同一个页面中进行。每次截图前更新对应的相机参数并等待资产就绪。WebGL 读回和合成器备用截图路径均设有超时，以免 SwiftShader 过载时一直等待。

Chromium 默认使用沙箱。仅在受限容器或当前账号无法创建 Chromium 命名空间时使用 `--no-sandbox`。
