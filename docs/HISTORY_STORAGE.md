# 历史数据存储说明

- 默认数据库：`sqlite:///data/aland_history.db`（本地开发/临时使用）。
- 若配置 `DATABASE_URL`（优先读取 Streamlit Secrets，其次环境变量），系统将连接外部数据库（推荐 Supabase/PostgreSQL）用于长期持久化。
- Streamlit Community Cloud 的本地文件不保证长期持久化，`SQLite` 可能在重启/迁移后丢失历史数据。
- 生产配置示例：

```toml
DATABASE_URL = "postgresql+psycopg2://user:password@host:5432/dbname"
```
