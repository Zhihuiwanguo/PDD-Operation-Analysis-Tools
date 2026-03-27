# Streamlit Community Cloud 部署指南（零基础版）

本文档用于把本项目部署到 **Streamlit Community Cloud**，并尽量避免新手常见报错。

---

## 1. 部署前准备

你需要：
1. 一个 GitHub 账号
2. 代码已推送到 GitHub 仓库
3. 可访问 https://share.streamlit.io/

本项目已包含部署需要的核心文件：
- `requirements.txt`（依赖）
- `app/main.py`（应用入口）
- `sample_data/`（样例数据，可用于云端演示）

> 推荐：首次部署前，先确认仓库里有最新代码（尤其是 `app/` 与 `sample_data/`）。

---

## 2. 在 Streamlit Community Cloud 创建应用

1. 打开 https://share.streamlit.io/ 并登录 GitHub。
2. 点击 **New app**。
3. 按下列信息填写：

- **Repository（仓库）**：选择你的项目仓库（本项目）
- **Branch（分支）**：`work`（如果你最终合并到 `main`，则填 `main`）
- **Main file path（主文件路径）**：`app/main.py`

4. 点击 **Deploy**。

---

## 3. 部署完成后如何更新

当你更新代码后：
1. 把变更 push 到你部署时选择的分支（例如 `work` 或 `main`）。
2. 回到 Streamlit 应用页面，点击 **Reboot app** 或 **Manage app -> Reboot**。
3. 页面会重新拉取最新代码并部署。

---

## 4. 常见报错与排查

### 报错 1：`ModuleNotFoundError`
**原因**：依赖缺失或 `requirements.txt` 未更新。  
**处理**：
- 检查 `requirements.txt` 是否包含对应包。
- 提交后 Reboot app。

### 报错 2：主文件找不到
**原因**：Main file path 填错。  
**处理**：
- 确认填的是：`app/main.py`

### 报错 3：样例数据加载失败
**原因**：`sample_data/` 未提交或路径错误。  
**处理**：
- 确认仓库中存在 `sample_data/` 目录及文件。
- 本项目已使用相对仓库根目录的稳健路径，无需改本地绝对路径。

### 报错 4：Excel 读取问题（`.xls`）
**原因**：缺少 `xlrd` 或文件格式异常。  
**处理**：
- 本项目 `requirements.txt` 已包含 `xlrd>=2.0`。
- 若仍异常，先用样例数据验证，再替换为业务文件。

### 报错 5：页面空白或数据为 0
**原因**：筛选条件过严或日期范围过窄。  
**处理**：
- 清空侧边栏筛选（店铺/产品/商品ID/是否百补）。
- 放宽日期范围。

---

## 5. 推荐部署检查清单

部署后请依次确认：
- 能打开页面
- `使用 sample_data 样例文件快速调试` 可跑通
- 各分析页有数据（总览、链接、产品、规格、百补vs日常、经营异常、异常清单）
- 可下载 Excel

---

## 6. 给新手的建议

- 第一次部署先不要改业务规则，先确保“能跑通”。
- 上传真实数据前，先用 sample_data 跑一遍对照字段。
- 任何字段报错，优先看“数据上传与校验”区域的缺失字段提示。

