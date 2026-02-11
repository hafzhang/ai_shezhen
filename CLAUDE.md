
在写文档时，不写代码，只写方案和细节

### 1.1 规划 vs 实施分离

```markdown
## Planning vs Implementation

When asked for plans, documentation, or analysis, provide ONLY the requested document first. Do NOT autonomously generate code, implementation files, or explore the codebase unless explicitly requested. Wait for user confirmation before moving from planning to implementation phase.
```

### 1.2 文件操作检查

```markdown
## File Operations

Always check file existence and current project context before attempting modifications. If user references content that cannot be located in the current project, explicitly confirm whether it belongs to a different codebase rather than attempting blind modifications.
```

### 1.3 Git 操作策略

```markdown
## Git Operations

For git operations with large files (>100MB) or many files, always discuss strategy first. Consider Git LFS for large images, test network connectivity before pushes, and handle encoding issues proactively for Chinese character content.
```

### 1.4 数据库操作验证

```markdown
## Database Operations

Before implementing database or API changes, verify table existence and schema matches expectations. When path resolution issues occur, use absolute paths or detect script location dynamically.
```

### 1.5 MCP 服务器配置

```markdown
## MCP Server Configuration

When working with MCP servers or external APIs, add explicit API key checks and validation steps in documentation. Test basic connectivity before attempting complex operations.
```
