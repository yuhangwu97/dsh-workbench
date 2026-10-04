# 发布 SDK

## Python

```bash
python -m pip install build twine
python -m build packages/python
python -m twine upload packages/python/dist/*
```

发布前确认 `packages/python/pyproject.toml` 的版本号已更新，且 `PYTHONPATH=packages/python python -m pytest tests -q` 通过。

## TypeScript

```bash
cd packages/typescript
npm ci
npm run typecheck
npm test
npm publish --access public
```

发布前确认 `package.json` 版本号已更新，且 `npm pack --dry-run` 只包含 `dist`、README 和 LICENSE。

## 服务端

参考服务通过 Docker Compose 发布。生产环境需要设置 `WORKBENCH_AUTH_TOKEN`、`DSH_CALLBACK_SECRET`、`DSH_ENDPOINT`，并将 SQLite 换成外部数据库或持久化服务。SDK 和 HTTP 契约遵循 SemVer，破坏性字段变更必须提升主版本。
