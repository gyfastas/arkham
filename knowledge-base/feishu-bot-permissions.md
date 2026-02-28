# 飞书机器人权限清单

> 最后更新: 2026-02-28
> App ID: cli_a91e8bccdff8dbca

## 权限总览

- **Tenant 级权限**: 155 个
- **User 级权限**: 14 个

## 按模块分类

### 多维表格 (Bitable) — 30 个
| 权限 | 说明 |
|------|------|
| `base:app:copy` | 复制多维表格应用 |
| `base:app:create` | 创建多维表格应用 |
| `base:app:read` | 读取多维表格应用 |
| `base:app:update` | 更新多维表格应用 |
| `base:collaborator:create` | 添加协作者 |
| `base:collaborator:delete` | 删除协作者 |
| `base:collaborator:read` | 读取协作者 |
| `base:dashboard:copy` | 复制仪表盘 |
| `base:dashboard:read` | 读取仪表盘 |
| `base:field:create` | 创建字段 |
| `base:field:delete` | 删除字段 |
| `base:field:read` | 读取字段 |
| `base:field:update` | 更新字段 |
| `base:form:read` | 读取表单 |
| `base:form:update` | 更新表单 |
| `base:record:create` | 创建记录 |
| `base:record:delete` | 删除记录 |
| `base:record:read` | 读取记录 |
| `base:record:retrieve` | 检索记录 |
| `base:record:update` | 更新记录 |
| `base:role:create` | 创建角色 |
| `base:role:delete` | 删除角色 |
| `base:role:read` | 读取角色 |
| `base:role:update` | 更新角色 |
| `base:table:create` | 创建数据表 |
| `base:table:delete` | 删除数据表 |
| `base:table:read` | 读取数据表 |
| `base:table:update` | 更新数据表 |
| `base:view:read` | 读取视图 |
| `base:view:write_only` | 写入视图 |

### 文档 (Docs/Docx) — 23 个
| 权限 | 说明 |
|------|------|
| `docs:document.comment:create` | 创建评论 |
| `docs:document.comment:read` | 读取评论 |
| `docs:document.comment:update` | 更新评论 |
| `docs:document.comment:write_only` | 写入评论 |
| `docs:document.content:read` | 读取文档内容 |
| `docs:document.media:download` | 下载媒体 |
| `docs:document.media:upload` | 上传媒体 |
| `docs:document.subscription` | 文档订阅 |
| `docs:document.subscription:read` | 读取订阅 |
| `docs:document:copy` | 复制文档 |
| `docs:document:export` | 导出文档 |
| `docs:document:import` | 导入文档 |
| `docs:event.document_deleted:read` | 文档删除事件 |
| `docs:event.document_edited:read` | 文档编辑事件 |
| `docs:event.document_opened:read` | 文档打开事件 |
| `docs:event:subscribe` | 事件订阅 |
| `docs:permission.member:*` | 权限管理（auth/create/retrieve/transfer/update） |
| `docs:permission.setting:*` | 权限设置（read/readonly/write_only） |
| `docx:document.block:convert` | 块转换 |
| `docx:document:create` | 创建文档 |
| `docx:document:readonly` | 只读文档 |
| `docx:document:write_only` | 写入文档 |

### 云盘 (Drive) — 9 个
| 权限 | 说明 | 备注 |
|------|------|------|
| `drive:drive.metadata:readonly` | 读取文件元数据 | ✅ |
| `drive:drive.search:readonly` | 搜索文件 | ✅ |
| `drive:drive:version:readonly` | 查看版本历史 | ✅ |
| `drive:file.meta.sec_label.read_only` | 安全标签读取 | ✅ |
| `drive:file:favorite` | 收藏文件 | ✅ |
| `drive:file:favorite:readonly` | 读取收藏 | ✅ |
| `drive:file:upload` | 上传文件 | ✅ |
| `drive:file:view_record:readonly` | 查看记录 | ✅ |
| ~~`drive:drive`~~ | 完整云盘权限 | ❌ **未授权！** 导致内置 delete 返回 400 |

### 电子表格 (Sheets) — 5 个
| 权限 | 说明 |
|------|------|
| `sheets:spreadsheet.meta:read` | 读取表格元数据 |
| `sheets:spreadsheet.meta:write_only` | 写入表格元数据 |
| `sheets:spreadsheet:create` | 创建表格 |
| `sheets:spreadsheet:read` | 读取表格 |
| `sheets:spreadsheet:write_only` | 写入表格 |

### 消息 (IM) — 35 个
| 权限 | 说明 |
|------|------|
| `im:message:send_as_bot` | 以机器人身份发消息 |
| `im:message:readonly` | 读取消息 |
| `im:message:update` | 更新消息 |
| `im:message:recall` | 撤回消息 |
| `im:message.group_msg` | 群聊消息 |
| `im:message.p2p_msg:readonly` | 读取私聊消息 |
| `im:message.pins:*` | 消息置顶 |
| `im:message.reactions:*` | 消息 reaction |
| `im:chat:create` | 创建群聊 |
| `im:chat:read` | 读取群聊信息 |
| `im:chat:update` | 更新群聊 |
| `im:chat:delete` | 删除群聊 |
| `im:chat.members:*` | 群成员管理 |
| `im:chat.announcement:*` | 群公告 |
| `im:chat.tabs:*` | 群标签页 |
| `im:chat.menu_tree:*` | 群菜单 |
| `im:resource` | 资源管理 |
| `im:app_feed_card:write` | 应用 feed 卡片 |

### 知识库 (Wiki) — 7 个
| 权限 | 说明 |
|------|------|
| `wiki:node:copy` | 复制节点 |
| `wiki:node:create` | 创建节点 |
| `wiki:node:move` | 移动节点 |
| `wiki:node:read` | 读取节点 |
| `wiki:node:retrieve` | 检索节点 |
| `wiki:setting:read` | 读取设置 |
| `wiki:space:read` | 读取空间 |
| `wiki:wiki:readonly` | 只读知识库 |

### 云空间 (Space) — 6 个
| 权限 | 说明 |
|------|------|
| `space:document:create` | 创建文档 |
| `space:document:delete` | 删除文档 |
| `space:document:move` | 移动文档 |
| `space:document:retrieve` | 检索文档 |
| `space:document:shortcut` | 快捷方式 |
| `space:folder:create` | 创建文件夹 |

### 任务 (Task) — 10 个
| 权限 | 说明 |
|------|------|
| `task:task:writeonly` | 写入任务 |
| `task:task:delete` | 删除任务 |
| `task:tasklist:read` | 读取任务列表 |
| `task:tasklist:writeonly` | 写入任务列表 |
| `task:comment:readonly` | 读取评论 |
| `task:comment:writeonly` | 写入评论 |
| `task:section:writeonly` | 写入分区 |
| `task:personnel:writeonly` | 写入人员 |
| `task:custom_field:read/delete` | 自定义字段 |
| `task:attachment:upload` | 上传附件 |

### 其他
| 权限 | 说明 |
|------|------|
| `board:whiteboard:node:*` | 白板操作 |
| `cardkit:card:read/write` | 卡片套件 |
| `contact:contact.base:readonly` | 通讯录基础信息 |
| `document_ai:*` | AI 文档处理（分块、识别等） |
| `docs_tool:docs_tool` | 文档工具 |
| `component:url_preview` | URL 预览 |
| `comment_sdk:comment_sdk` | 评论 SDK |

## 已知限制

1. **❌ 无 `drive:drive` 完整权限** — 内置 `feishu_drive delete` 返回 400；需用 `feishu-extra` 的 `drive-delete` 命令（走 `DELETE /drive/v1/files/{token}?type=<type>` 接口）
2. **文档导入仅支持 .docx/.xlsx** — `docs:document:import` 不支持 .md 文件
3. **User 级权限仅 14 个** — 大部分操作走 Tenant 级（bot 身份）

## 常见问题 FAQ

**Q: 机器人能删除云盘文件吗？**
A: 不能直接用内置工具（缺 `drive:drive` scope），但可以通过 `feishu-extra` skill 的 `drive-delete` 命令实现。

**Q: 机器人能读/写电子表格吗？**
A: 可以。有完整的 sheets CRUD 权限。

**Q: 机器人能管理群聊吗？**
A: 可以。有创建/删除群聊、管理成员、公告、标签页等全套权限。

**Q: 机器人能操作多维表格吗？**
A: 可以。有完整的 bitable CRUD 权限（应用/表/字段/记录/视图/角色）。

**Q: 机器人能操作知识库吗？**
A: 可以。有创建/移动/复制/读取节点的权限，但大部分是只读。
