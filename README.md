# MK Developer

MK 的个人开发者网站，用于发布软件、插件、Skill 与浏览器扩展。

## 自动同步

网站在访客打开页面时读取 GitHub 的公开仓库列表，并按最近更新时间排序。新增公开仓库不需要修改网站代码；仓库名称、简介、语言、Topics 和更新时间会自动展示。

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
