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

## 外部书源文件下载页

`docs/reader-sources/` 部署到 `/reader-sources/`。页面为静态 HTML，JSON 与页面同域，不依赖 GitHub API、外部字体或脚本。按钮明确是“下载”，当前构建14仍需通过系统文件打开/分享或应用内选择文件完成导入，不声称网页已自动配置。

更新 `sources-v1.json` 后，同步页面文件摘要与更新日期。JSON只存名称、模板、公开网站根地址，不存书籍正文、账户或凭据。GitHub Pages 的本地访问成功不能代替中国大陆线路验证；当前没有大陆可用性保证。
