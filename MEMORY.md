# MEMORY.md - 长期记忆

## 我的飞书 Workspace

- **主文件夹**: https://bytedance.larkoffice.com/drive/folder/Sd1wflp6MlrUeYd0GQoc92KGnpc
- **子文件夹**:
  - 论文调研
  - Skills
  - 实验汇总
  - 每日总结

## 用户偏好

- **文档创建位置**: 用户的飞书 workspace（默认创建，这样用户有编辑权限）
- **如果没有特别指定子文件夹，就放到根目录**
- **文档格式**: 链接用"文档名 (链接)"格式

## 常用文档

- **gyf的QAs**: [gyf的QAs](https://feishu.cn/docx/YNdbdejcco0b7ZxzIP7lTdwEgUe)

## 工作习惯

- 每日工作总结: 放到「每日总结」文件夹
- 论文相关: 放到「论文调研」文件夹
- 定时任务: Heartbeat 配置每日论文更新

## 工作模式配置

- 工作模式文档: Agent工作模式配置 (https://feishu.cn/docx/FqSmdAN1To05Alxsye3lUsJogGr)
- 新 Agent 初始化时：优先读取该文档，获取飞书 workspace、子文件夹结构和已配置任务

## 飞书 Docx Table API 关键限制

- **markdown 表格不支持**：`feishu_doc append/write` 不支持 `|table|` markdown 语法
- **单次创建最多 9 行**：block_type=31 table，超过 9 行返回 1770001
- **不能追加行**：已创建的 table block 不支持 create children（1770028）
- **解决方案**：按分类拆多个小表格，每个 ≤ 9 行
- **正确 property 格式**：必须有 `row_size` 和 `column_size`，勿加 `column_width`/`border_visible`
- **删除 block API**：`DELETE /open-apis/docx/v1/documents/{doc_id}/blocks/{parent_id}/children/batch_delete`

## 已安装 Skills

### Workspace Skills
- **feishu-extra**: 飞书扩展 API（drive search/upload/copy/delete，doc copy/import，sheets CRUD）
  - 脚本：`skills/feishu-extra/feishu_api.py`，自动从 openclaw.json 读取 appId/appSecret
  - 使用：`python3 ~/.openclaw/workspace/skills/feishu-extra/feishu_api.py <cmd>`
- **feishu-sheets**: 飞书电子表格操作指南（区别于 Bitable）
- **agent-browser**: headless 浏览器自动化（v0.15.1），基于 Playwright + Chromium
  - 注意：内网站点（Merlin/飞书）需先 `--headed` 登录保存 session
- **arxiv-watcher**: 搜索和汇总 ArXiv 论文
- **feishu-interactive-cards**: 飞书交互式卡片（按钮、表单、投票等）
- **feishu-docx-powerwrite**: 飞书文档强力写入（支持更复杂的文档操作）
- **xiaohongshu-cn**: 小红书分析
- **xiaohongshu-mcp**: 小红书内容运营

- **pkm**: 个人知识库（RAG），支持 URL/文本收藏和语义搜索
- **tech-news-digest**: 138 源科技新闻聚合（RSS/Twitter/Reddit/GitHub/Web），每日飞书文档投递

### 内置飞书 Skills (feishu extension)
- **feishu-doc**: 飞书文档读写
- **feishu-drive**: 飞书云盘管理
- **feishu-perm**: 飞书权限管理
- **feishu-wiki**: 飞书知识库

## exp-helper Skill (实验助手)

**用途**: 处理 Merlin training trial 参数，自动创建实验文档

**触发条件**: 用户给到 Merlin trial 参数时

**工作流**:
1. 解析 trial 参数 (--dataset, --model, --learning_rate 等)
2. 验证数据集路径（查飞书表格）
3. 确认实验信息
4. 创建实验文档

**关键资源**:
- 数据集表格: `OSyWbrg8TaJQ53spbpDlbaMYgif / tblO56UPt8R14xtV`
- 实验汇总文件夹: https://bytedance.larkoffice.com/drive/folder/PxPbfaCeclA7ObdwF3hcSEypnlf
