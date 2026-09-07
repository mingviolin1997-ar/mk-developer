"use client";

import { useEffect, useMemo, useState } from "react";

type Repository = {
  id: number;
  name: string;
  html_url: string;
  description: string | null;
  homepage: string | null;
  language: string | null;
  topics: string[];
  updated_at: string;
  stargazers_count: number;
  fork: boolean;
  archived: boolean;
  cta_label?: string;
};

const OWNER = "mingviolin1997-ar";
const API = `https://api.github.com/users/${OWNER}/repos?type=owner&sort=updated&per_page=100`;

const wonderReaderRelease: Repository = {
  id: -36, name: "Wonder Reader", html_url: "/wonder-reader/",
  description: "Mac 无障碍阅读器，语音阅读、OCR、翻译与总结全部免费。内置 Low 模型。适用于 Apple 芯片 Mac，macOS 14 或更新。",
  homepage: null, language: "Swift", topics: ["macos", "accessibility", "local-ai"],
  updated_at: "2026-09-07T20:00:00Z", stargazers_count: 0, fork: false, archived: false, cta_label: "免费下载",
};

const wonderGPTRelease: Repository = {
  id: -26,
  name: "WonderGPT",
  html_url: `https://github.com/${OWNER}/mk-developer/releases/download/wonder-gpt-v0.5.0-beta.6/Wonder-GPT-0.5.0-Build26.zip`,
  description: "以无障碍为首要目标的多模型 AI 工作空间。支持 VoiceOver、本地模型、在线模型、OCR、Skill 与可访问的项目管理；当前版本适用于 Apple Silicon Mac。",
  homepage: `https://github.com/${OWNER}/mk-developer/releases/tag/wonder-gpt-v0.5.0-beta.6`,
  language: "Swift",
  topics: ["macos", "accessibility", "local-ai", "beta"],
  updated_at: "2026-08-10T13:06:00Z",
  stargazers_count: 0,
  fork: false,
  archived: false,
  cta_label: "下载测试版",
};

const featuredFallback: Repository = {
  id: 1328609254,
  name: "photo-accessibility-studio",
  html_url: `https://github.com/${OWNER}/photo-accessibility-studio`,
  description: "Mac 与 Android 双端的本地批量照片无障碍描述工具。",
  homepage: null,
  language: "Swift",
  topics: ["macos", "android", "accessibility", "local-ai"],
  updated_at: "2026-08-09T00:00:00Z",
  stargazers_count: 0,
  fork: false,
  archived: false,
};

function titleFor(name: string) {
  if (name === "WonderGPT") return "Wonder GPT";
  if (name === "photo-accessibility-studio") return "照片无障碍描述";
  return name
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function typeFor(repo: Repository) {
  const haystack = `${repo.name} ${repo.description ?? ""} ${repo.topics.join(" ")}`.toLowerCase();
  if (/extension|browser|chrome|firefox|safari/.test(haystack)) return "浏览器扩展";
  if (/skill|codex|agent/.test(haystack)) return "Skill";
  if (/plugin|插件/.test(haystack)) return "插件";
  return "软件";
}

function ProjectCard({ repo, featured = false }: { repo: Repository; featured?: boolean }) {
  const date = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "short", day: "numeric" }).format(new Date(repo.updated_at));
  return (
    <article className={`project-card${featured ? " featured" : ""}`}>
      <div className="card-topline">
        <span className="project-type">{typeFor(repo)}</span>
        <span className="project-date">更新于 {date}</span>
      </div>
      <h3>{titleFor(repo.name)}</h3>
      <p>{repo.description || "一个正在持续完善的独立项目。"}</p>
      <div className="project-meta">
        {repo.language && <span>{repo.language}</span>}
        {repo.topics.slice(0, 3).map((topic) => <span key={topic}>{topic}</span>)}
      </div>
      <div className="card-actions">
        <a href={repo.html_url} target="_blank" rel="noreferrer">{repo.cta_label ?? "查看项目"} <span aria-hidden="true">↗</span></a>
        {repo.homepage && <a className="secondary-link" href={repo.homepage} target="_blank" rel="noreferrer">查看发行说明</a>}
      </div>
    </article>
  );
}

export default function Home() {
  const [repos, setRepos] = useState<Repository[]>([wonderReaderRelease, wonderGPTRelease, featuredFallback]);
  const [status, setStatus] = useState<"loading" | "live" | "fallback">("loading");
  const [filter, setFilter] = useState("全部");

  useEffect(() => {
    fetch(API, { headers: { Accept: "application/vnd.github+json" } })
      .then((response) => {
        if (!response.ok) throw new Error("GitHub API unavailable");
        return response.json();
      })
      .then((data: Repository[]) => {
        const visible = data.filter((repo) => !repo.fork && !repo.archived && repo.name !== "mk-developer");
        setRepos([wonderReaderRelease, wonderGPTRelease, ...(visible.length ? visible : [featuredFallback])]);
        setStatus("live");
      })
      .catch(() => {
        setRepos([wonderReaderRelease, wonderGPTRelease, featuredFallback]);
        setStatus("fallback");
      });
  }, []);

  const types = useMemo(() => ["全部", ...Array.from(new Set(repos.map(typeFor)))], [repos]);
  const shown = filter === "全部" ? repos : repos.filter((repo) => typeFor(repo) === filter);

  return (
    <main>
      <nav className="nav shell" aria-label="主导航">
        <a className="brand" href="#top" aria-label="MK Developer 首页"><span>MK</span> Developer</a>
        <div className="nav-links">
          <a href="#projects">项目</a>
          <a href={`https://github.com/${OWNER}`} target="_blank" rel="noreferrer">GitHub</a>
          <a className="music-link" href="https://mk-musician.com" target="_blank" rel="noreferrer">音乐人主页 ↗</a>
        </div>
      </nav>

      <section className="hero shell" id="top">
        <p className="eyebrow"><span className="status-dot" /> 独立开发者 · 持续构建中</p>
        <h1>为真实需求，<br /><em>做简单好用的工具。</em></h1>
        <p className="hero-copy">这里收录我开发的软件、插件、Skill 与浏览器扩展。重视无障碍、隐私和清晰的使用体验。</p>
        <div className="hero-actions">
          <a className="primary-button" href="#projects">浏览项目 <span aria-hidden="true">↓</span></a>
          <a className="text-button" href={`https://github.com/${OWNER}`} target="_blank" rel="noreferrer">关注 GitHub <span aria-hidden="true">↗</span></a>
        </div>
        <div className="code-note" aria-label="网站更新方式">
          <span className="prompt">$</span><span>github repos --sync</span><span className={`sync-state ${status}`}>{status === "live" ? "已实时同步" : status === "loading" ? "正在连接" : "稍后重试"}</span>
        </div>
      </section>

      <section className="projects shell" id="projects">
        <div className="section-heading">
          <div><p className="section-number">01 / PROJECTS</p><h2>项目</h2></div>
          <p>公开项目与安装包会同步到这里，最近更新的内容排在最前。</p>
        </div>
        <div className="filters" aria-label="项目类型筛选">
          {types.map((type) => <button key={type} className={filter === type ? "active" : ""} onClick={() => setFilter(type)}>{type}</button>)}
        </div>
        <div className="project-grid">
          {shown.map((repo, index) => <ProjectCard key={repo.id} repo={repo} featured={index === 0 && filter === "全部"} />)}
        </div>
      </section>

      <section className="principles shell">
        <p className="section-number">02 / PRINCIPLES</p>
        <div className="principle-grid">
          <h2>少一点噪音，<br />多一点用处。</h2>
          <div className="principle-list">
            <div><span>01</span><h3>需求先行</h3><p>从真实问题出发，不为功能而堆功能。</p></div>
            <div><span>02</span><h3>隐私优先</h3><p>能在本地完成的处理，尽量留在设备上。</p></div>
            <div><span>03</span><h3>人人可用</h3><p>把无障碍作为产品基础，而不是附加选项。</p></div>
          </div>
        </div>
      </section>

      <footer className="footer shell">
        <div><a className="brand" href="#top"><span>MK</span> Developer</a><p>Software · Plugins · Skills · Extensions</p></div>
        <div className="footer-right"><p>© {new Date().getFullYear()} MK Developer</p><p>与 GitHub 公开项目及发行版同步</p></div>
      </footer>
    </main>
  );
}
