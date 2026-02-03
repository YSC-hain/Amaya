## 关于项目的需求与设计文档
请查看 `/docs/PRD.zh-CN.md` 与 `/docs/HLD.zh-CN.md`。

## 关于开发规范
请使用中文编写注释和日志。

## Python watchdog 自动监听与重启
```bash
watchmedo auto-restart --patterns="*.py" --recursive -- python src/main.py
```
