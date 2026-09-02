# Security Policy

## 密钥与隐私保护

Book Soul 是一款**本地优先**的桌面应用，**所有用户数据**（作品、章节、人物卡、灵感）**均存储在用户本地**。但项目本身需要 LLM API Key 来调用云端模型。

### 绝对不提交到 Git 的内容

- `**/.env` （环境变量，含 API Key）
- `**/.env.*` （除 `.env.example`）
- `data/` （运行时数据，可能含作品内容）
- `*.key`, `*.pem` （密钥文件）
- 任何真实 API Key

### 已配置的保护机制

1. **`.gitignore`** —— 严格排除上述文件
2. **`.gitleaks.toml`** —— 提交前自动扫描密钥泄露
3. **`.pre-commit-config.yaml`** —— 包含 `gitleaks` 钩子，泄露时阻断 commit
4. **GitHub Actions** —— CI 二次验证
5. **AGENTS.md 强制规范** —— agent 不得硬编码 Key

### 如何正确管理 API Key

```bash
# 1. 复制示例文件
cp .env.example .env

# 2. 编辑 .env，填入真实 Key
#    ⚠️ .env 永远不被 git 跟踪

# 3. 提交时检查
git status  # 确认 .env 不在列表里

# 4. 如发现 .env 不小心被 git 跟踪
git rm --cached .env
git commit -m "Remove .env from tracking"
# 然后**立即**撤销并重生成泄露的 Key
```

### 如果你的 API Key 泄露了

1. **立即**在 LLM provider 撤销该 Key
2. 生成新 Key
3. 检查账单，确认没有被盗刷
4. 在新 commit 中更新 .env（本地）
5. 考虑是否需要回滚到泄露前的 commit（破坏性操作，谨慎）

### 数据加密（可选）

- 默认**不加密**用户数据（方便用户备份、跨设备同步）
- 可在设置中开启 Fernet 加密
- 加密 key 存在系统 Keyring
- ⚠️ **警告**：启用加密后，**卸载应用 = 数据可能无法解密**
- ⚠️ **警告**：启用加密后，**重装系统 = 数据无法解密**
- 建议：定期手动备份 `~/Documents/BookSoul/`

### 依赖安全

- 所有 Python 依赖通过 `uv` 管理，锁定在 `pyproject.toml` / `uv.lock`
- 所有 Node 依赖通过 `pnpm` 管理，锁定在 `pnpm-lock.yaml`
- GitHub Dependabot 建议开启（未来）

## 报告漏洞

如发现 Book Soul 存在安全漏洞：

- 邮件：your-email@example.com（请替换为真实邮箱）
- 或开 GitHub Issue 标记 `security`

**不要**在公开 Issue 中泄露漏洞细节。

## 数据流向

```
用户本地 ──→ Book Soul 桌面应用 ──→ LLM Provider (HTTPS)
  │                                    │
  │                                    └─→ 发送：prompt（含小说上下文）
  │                                    └─→ 接收：生成内容
  │                                    
  └─→ 数据存储：本地 SQLite + md 文件
```

**注意**：使用云端 LLM 时，prompt 中的小说内容**会发送到第三方**（minimax/OpenAI/Anthropic）。
- 如需完全本地化，请使用 Ollama 配置本地模型
- 本项目不收集任何遥测数据
