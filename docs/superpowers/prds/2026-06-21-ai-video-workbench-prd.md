# PRD: AI 短视频批量生产工作台

日期：2026-06-21  
状态：ready-for-agent  
来源：当前需求访谈与已确认设计稿

## Problem Statement

国内短视频代运营、本地生活商家、剪辑公司和矩阵号团队需要每天批量生产抖音竖屏短视频，但现有流程依赖人工找爆款文案、写脚本、剪辑、加字幕、配音、导出和混剪。这个流程慢、成本高、产能不稳定，也很难让低配置笔记本用户批量生产视频。

用户需要一个 Windows 桌面工作台：本地安装简单，重任务在云端处理，能围绕抖音场景自动生成爆款文案、自动字幕、可选配音、模板化剪辑和批量混剪，并通过积分计费支撑 SaaS 收费。

## Solution

建设一个“Windows 客户端 + 云端 SaaS 后台 + 云端 Worker”的 AI 短视频批量生产系统。

普通用户只安装 Windows 客户端。客户端负责登录、素材上传、客户/品牌管理、项目创建、脚本确认、任务状态查看、视频预览和下载。云端负责 AI 文案、素材识别、字幕、配音、剪辑、混剪、积分扣费、任务队列和扩容。运营方通过网页后台管理用户、团队、积分、行业模板、爆款样本、AI 模型、任务和充值流水。

第一版聚焦抖音竖屏短视频，不做完整时间线编辑器，不做第三方插件市场，不做网页用户端，不做自动支付。后续通过 provider/jobs/assets 结构接入数字人、AI 生图、生视频、声音克隆和 ComfyUI。

## User Stories

1. As a 短视频代运营, I want to install a Windows client, so that I can use the product without opening a browser workflow.
2. As a 短视频代运营, I want to log in with email and password, so that I can access my workspace quickly.
3. As a 新用户, I want to register only with an invitation code, so that the platform can prevent random account abuse.
4. As a 团队老板, I want a workspace, so that my team projects, credits, customers, and assets are managed together.
5. As a 团队老板, I want credits to belong to the workspace, so that multiple team members can consume the same balance.
6. As an 运营方, I want to manually recharge credits for a workspace, so that the first version can charge customers without integrating automatic payments.
7. As an 运营方, I want to see recharge records, so that credit changes are auditable.
8. As a 用户, I want failed tasks to refund frozen credits automatically, so that I do not pay for system failures.
9. As a 用户, I want credits to be frozen when a task is submitted, so that I know the estimated cost before processing starts.
10. As an 运营方, I want successful tasks to settle frozen credits, so that platform costs are covered.
11. As an 运营方, I want different models to have different credit prices, so that expensive models do not lose money.
12. As a 用户, I want to choose AI models in advanced settings, so that I can trade off speed, cost, and quality.
13. As an 运营方, I want API keys stored only on the server, so that users never see or steal provider credentials.
14. As an 运营方, I want to configure providers for LLM, TTS, ASR, vision, and future video generation, so that models can be changed without rewriting the product.
15. As a 剪辑公司, I want to create customer/brand profiles, so that each client has its own industry, selling points, forbidden words, and style preferences.
16. As a 剪辑公司, I want each customer to have reusable assets, so that I can repeatedly produce videos for the same brand.
17. As a 用户, I want to upload MP4/MOV videos, JPG/PNG/WEBP images, and MP3/WAV audio, so that common short-video materials are supported.
18. As a 用户, I want large files to upload from the client to cloud storage directly, so that uploads are faster and the API server is not overloaded.
19. As a 用户, I want uploaded assets to be automatically tagged, so that the editor knows which clips show products, people, price, process, store front, or details.
20. As a 用户, I want to correct AI-generated asset tags, so that wrong recognition does not ruin the generated video.
21. As a 用户, I want to import a Douyin link, so that the system can analyze public/copyable text structure when available.
22. As a 用户, I want to paste viral copy manually when link extraction fails, so that the workflow still works without scraping Douyin.
23. As an 运营方, I want Douyin imports to store only links, copy, analysis, tags, and rewrites, so that the platform avoids saving other people’s original videos by default.
24. As a 用户, I want to select an industry template, so that AI scripts match my business scenario.
25. As an 运营方, I want industry templates to be configurable content, so that new industries can be added without code changes.
26. As an 运营方, I want a system viral-copy library, so that all users can benefit from maintained high-performing patterns.
27. As a 团队, I want private viral-copy samples, so that my customer-specific examples are not shared with other teams.
28. As a 用户, I want AI to generate multiple Douyin-style scripts, so that I can choose a direction before spending video-render credits.
29. As a 用户, I want script duration to be controlled at 15s, 30s, or 60s, so that output matches Douyin short-video formats.
30. As a 用户, I want to edit generated scripts before rendering, so that the final video matches the customer’s actual offer.
31. As a 用户, I want to confirm scripts before cloud clipping starts, so that bad copy does not waste render credits.
32. As a 用户, I want optional AI voiceover, so that videos can be produced with narration when needed.
33. As a 用户, I want videos without voiceover to still support subtitles and music, so that silent/card-style videos are possible.
34. As a 用户, I want automatic subtitles for AI voiceover, so that narration videos are ready for Douyin viewing.
35. As a 用户, I want ASR subtitles for original audio clips, so that spoken source videos can be captioned.
36. As a 用户, I want to edit subtitle text, so that recognition mistakes can be fixed.
37. As a 用户, I want template-based automatic clipping, so that I can generate videos without learning a professional timeline editor.
38. As a 用户, I want batch remixing from the same asset pool, so that I can create many variants for matrix-account publishing.
39. As a 用户, I want each remix to vary script, opening hook, asset order, subtitles, cover text, and music, so that outputs are less repetitive.
40. As a 用户, I want only Douyin vertical MP4 export in the first version, so that the workflow stays simple and reliable.
41. As a 用户, I want generated videos in 1080x1920, so that output is ready for Douyin upload.
42. As a 用户, I want video tasks to show queued, running, succeeded, and failed states, so that I understand what is happening.
43. As a 用户, I want to see current processing steps like subtitle, voiceover, clipping, and export, so that long tasks feel transparent.
44. As a 用户, I want estimated wait time during high load, so that queueing is acceptable.
45. As a 用户, I want to preview generated MP4 files in the client, so that I can check results before downloading.
46. As a 用户, I want to download completed videos, so that I can upload them to Douyin.
47. As a 用户, I want to regenerate videos if I am unhappy, so that I can iterate on content.
48. As an 运营方, I want user dissatisfaction regenerations to consume credits again, so that cloud processing cost is covered.
49. As an 运营方, I want every heavy task to run in a queue, so that traffic spikes slow down instead of crashing the platform.
50. As an 运营方, I want per-team concurrency limits, so that one customer cannot monopolize all workers.
51. As an 运营方, I want worker autoscaling, so that high traffic can be handled by adding cloud servers.
52. As an 运营方, I want global platform concurrency limits, so that emergency cost and load can be controlled.
53. As an 运营方, I want old source materials to expire after 30 days, so that storage cost stays controlled.
54. As an 运营方, I want generated videos to expire after 90 days, so that object storage does not grow forever.
55. As a 用户, I want to delete assets manually, so that I can clean up private or unnecessary material.
56. As a 用户, I want the Windows client to auto-update, so that old versions do not break when cloud APIs change.
57. As an 运营方, I want a minimal admin backend, so that I can manage users, workspaces, credits, orders, templates, samples, providers, and jobs.
58. As an 运营方, I want a simple website/download page, so that users can download the Windows client and request trial access.
59. As a 访客, I want the website to look like a high-tech product launch page, so that I perceive the product as professional and advanced.
60. As a 产品负责人, I want Penpot used for design and prototype work, so that website and client screens can be reviewed before implementation.
61. As a 产品负责人, I want Penpot not to be embedded into the product code, so that the product does not inherit unnecessary complexity.
62. As a 产品负责人, I want future capabilities to use provider/job/assets interfaces, so that digital humans, image generation, video generation, ComfyUI, and voice cloning can be added later.

## Implementation Decisions

- Product is a Windows desktop client backed by a cloud SaaS system.
- Ordinary users do not get a web user portal in v1; they use only the Windows client.
- The operator/admin gets a web admin backend.
- The client is Tauri + React + TypeScript.
- The backend is Django + PostgreSQL.
- Redis is used for cache/queue in v1; high-scale deployment may upgrade to managed RabbitMQ/RocketMQ.
- Python Workers process AI calls, FFmpeg clipping, subtitle generation, voiceover, remixing, and export.
- Object storage is Aliyun OSS. Large files are uploaded directly with signed upload credentials.
- Cloud vendor is Aliyun. API can run on SAE. Workers run on ECS pay-as-you-go instances with autoscaling.
- All heavy work is asynchronous and queue-based. API requests only create records and enqueue jobs.
- Workspace is the main commercial container. Credits, projects, customers, assets, members, and jobs belong to a workspace.
- Registration is invite-code based using email and password. No phone verification in v1.
- No device binding or machine-code licensing in v1.
- Credits are manually recharged by the operator in v1. Automatic payment is out of scope.
- Credit flow is freeze on submission, settle on success, refund on system failure.
- User-requested regeneration after a successful task consumes credits again.
- AI providers are configured centrally by the operator. Users can choose enabled models in advanced settings.
- API keys are stored only on the server and never exposed to the client.
- Provider types are LLM, TTS, ASR, vision, and future video generation.
- First AI provider target is Volcengine/火山, with later providers added through the same interface.
- Industry templates are data/configuration, not separate code modules.
- Douyin import is compliance-first: save link, copy, structure analysis, tags, and rewrites; do not default to saving other people’s original videos.
- Video output in v1 is limited to Douyin vertical 9:16, 1080x1920 MP4, with 15s/30s/60s duration targets.
- Subtitles are burned into the MP4 by default.
- Batch remixing uses rule-based variation over scripts, hooks, asset order, subtitles, cover text, and music.
- First version does not implement a full timeline editor.
- First version does not implement a third-party plugin marketplace or SDK.
- Future digital human, image generation, video generation, voice cloning, and ComfyUI are reserved as providers/jobs, not included as core v1 features.
- Penpot is used for design/prototype work only, not as product runtime code.
- Website/download page uses a high-tech launch-page direction, with real workbench sections lower on the page.

## Testing Decisions

- Highest-value test seam: the end-to-end product workflow from workspace creation through project creation, script confirmation, credit freeze, queued job, worker success, credit settlement, and downloadable output.
- Tests should verify external behavior and state transitions, not internal implementation details.
- No prior test patterns exist because the repository is currently greenfield.
- Auth/workspace tests should cover invite-code registration, login, workspace creation, and workspace-scoped access.
- Credit ledger tests should cover manual recharge, task freeze, success settlement, failure refund, and insufficient-credit rejection.
- Provider tests should use fake providers, not real AI APIs, to prove model selection, pricing, success, and failure handling.
- Asset tests should cover signed upload creation, asset records, retention metadata, and tag correction behavior.
- Template/script tests should cover industry template selection, private sample priority, generated script drafts, duration target metadata, and user confirmation before rendering.
- Job queue tests should cover pending/running/succeeded/failed states, retries, timeout handling, and idempotent worker completion.
- Render workflow tests should use the smallest possible fixture media or generated test clips to prove FFmpeg integration creates a valid MP4.
- Client smoke tests should cover login, create project, upload, generate script, submit job, see status, preview result, and download.
- Admin tests should cover managing users, workspaces, credits, providers, templates, samples, and jobs.
- Scaling behavior should be tested at the API/job-state seam with many queued jobs, not by trying to render thousands of real videos in normal tests.

## Out of Scope

- Web user portal for ordinary customers.
- Offline mode.
- Full professional timeline editor.
- PR/剪映/AE/PSD project import.
- Device binding, hardware fingerprinting, or license dongles.
- Automatic WeChat/Alipay payment integration.
- Third-party plugin marketplace or public plugin SDK.
- Digital human generation as a v1 core feature.
- AI image generation as a v1 core feature.
- AI video generation as a v1 core feature.
- Voice cloning as a v1 core feature.
- ComfyUI as a required core runtime.
- Scraping Douyin at scale or bypassing anti-bot protections.
- Saving other people’s Douyin videos by default.
- Multi-platform deep optimization beyond Douyin.
- 4K, horizontal video, multiple export codecs, or advanced bitrate controls.
- Complex BI, CRM, distribution/affiliate systems, or enterprise SSO.

## Further Notes

- The product should be designed so that high load causes queueing, not crashes.
- If 10,000 users submit tasks at the same time, the system accepts jobs into the queue, freezes credits, displays waiting status, and expands workers within configured budget/concurrency limits.
- The first version should prefer mature libraries and cloud services over custom infrastructure.
- Open-source projects should be used as libraries, templates, or tools, not as large products to fork and heavily modify.
- The website visual direction is “AI video production launch event”: deep dark tech palette, blue/cyan/purple energy accents, animated engine core, and real workbench sections.
- The implementation plan should be split into small vertical slices: account/workspace/credits, asset upload, script generation, queued job processing, render pipeline, client workflow, admin, and download page.
