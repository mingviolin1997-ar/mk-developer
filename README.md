# MK Developer

MK 的个人开发者网站，用于发布软件、插件、Skill 与浏览器扩展。

## 自动同步

网站在访客打开页面时读取 GitHub 的公开仓库列表，并按最近更新时间排序。新增公开仓库不需要修改网站代码；仓库名称、简介、语言、Topics 和更新时间会自动展示。

Wonder GPT 采用“私有源码、公开安装包”的发行方式：源码保留在私有仓库，经校验的 ZIP、DMG 与 SHA-256 文件发布在本仓库的 GitHub Release，网站提供直接下载入口。

为了获得正确的分类，请为仓库添加合适的 Topics，例如：

- `browser-extension`：浏览器扩展
- `plugin`：插件
- `skill` 或 `codex`：Skill
- 其他公开仓库默认归为软件

## 网站

- 正式域名：<https://dev.mk-musician.com>
- GitHub Pages 备用地址：<https://mingviolin1997-ar.github.io/mk-developer/>

每次推送到 `main` 分支后，GitHub Actions 会自动发布网站。

## 本地开发

```bash
npm install
npm run dev
```

静态 GitHub Pages 版本位于 `docs/`，完整 React 源码位于 `app/`。

## 小铭读书使用说明

`docs/reader-guide/` 部署到 `/reader-guide/`，说明用户如何导入自己的书籍文件与书源配置，以及当前支持的格式。`/reader-sources/` 旧目录地址只保留通往新说明的入口，不再展示或推荐具体书源。

原有 JSON 文件暂予保留，以免破坏既有用户链接及回滚证据；页面不再链接它们。此网页变更不表示 App Store 拒审原因已经确定，也不表示应用安装包或审核提交已经改变。

## 朋友测试版发布规则（2026-09-07）

通过本网站、UDID 或 Ad Hoc 分发给朋友的应用，默认免费开放，不要求购买会员、订阅或付费凭证。只有小铭明确要求上架 App Store 时，才采用付费模式；朋友测试包继续保持免费。

保留 `/test/#hei-huang`、`/test/#other-friends` 和 `/test/#register` 固定入口。新增朋友需先取得其 UDID，登记并导出包含其设备的安装包，再添加昵称对应的安装区；不要将全部朋友的安装按钮自动替换为同一个最新包。

## 朋友安装包下载线路（2026-11-03）

Pages 发布时，`scripts/prepare_download_routes.py` 保持 `/test/packages/` 的源清单字节和主安装按钮不变，主线路使用 GitHub Pages。所有历史清单同时原样生成 `/test/direct/` 兼容路径，代理验证失败也保留这些路径。当前安装按钮另有经过验证才显示的“备用加速线路”，指向独立的 `/test/accelerated/` 清单；它不折叠隐藏，也不取代主线路。

加速沿用 GH-Proxy 和固定 Git 提交；首次必须完整下载核对 SHA-256 并检查 HTTP Range 和文件开头才启用。同一不可变包可复用完整哈希记录，但每次重新检查 Range；新包及 GitHub Release 大包重新完整验证。失败不阻断原线路。生成过程不改 IPA、朋友分组、版本、设备授权或注册入口；`download-routes.json` 记录实际启用版本和哈希，部署完成不能代替朋友设备安装验收。

发布者继续更新源清单和安装入口，不要提交生成清单、`docs/test/direct/`、`docs/test/accelerated/` 或 `download-routes.json`。本地只用任务 `work/` 中的小夹具/隔离发布目录运行生成器，禁止直接对生产源 `docs/` 运行。无需新账号、付费服务或 Virginia 服务器下载流量。

## 需求树与代码树：下载发布

本仓库沿用上级分发治理 `../../docs/REQUIREMENTS-TREE.md` 的 D-R01 和 `../../docs/CODING-TREE.md` 的 D-C01。以下是网站当前具体映射。

|需求节点|代码、验收与生命周期映射|
|---|---|
|WEB-R01 主线路与历史兼容|`scripts/prepare_download_routes.py` → WEB-C01；默认清单字节不变，所有 `/test/direct/` 清单继续可用；只给校验成功的当前包提供可见备用加速入口。|
|WEB-R02 发布完整性|`scripts/test_download_routes.py` → WEB-C02；覆盖 owner/friend 元数据、坏哈希、截断响应、首次/缓存 Range、新包缓存失效、外域/路径穿越/符号链接拒绝。|
|WEB-R03 GitHub 托管|`.github/workflows/pages.yml` → WEB-C03；开发站和 UDID 下载留 GitHub，主站/TeamTalk/Virginia 不承担本站下载。|
|WEB-R04 工作区整洁与存储生命周期|源码/Git/签名包/历史路径保留，沿用当前仓库；本次检查开始有 276 GiB 可用。复用已有源包，禁止克隆大仓库或拷贝完整媒体。新增至少 1 GiB 先预算；临时测试夹具、暂存及证据归活动任务 `work/dev-download-repair/`，源包不重签、不改写。|
|WEB-C04 清理与证据|2026-11-03 活动任务根为 `/Users/mingkong/Documents/Codex/2026-11-03/carnegie-library-apple-store-iphone-18-2`；`work/dev-download-repair/fixtures/` 为自动销毁的小夹具，`download-tests-red*.log` 与验证日志保留，CI 哈希回执复用有边界的 `~/.cache/mk-download-routes`。无通用清空脚本，收尾只核对明确归属且不再占用的临时路径；保留源码、Git、包、失败证据与回滚依据，不声称目录统计等于释放空间。|

Mac 每次真实启动异步检查新版本；iOS/iPadOS 免于启动更新查询，仍要求按版本/构建显示可关闭、VoiceOver 可读的首次新特性。本网站修复不改应用二进制或声称其行为已变。
