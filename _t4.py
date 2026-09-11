# -*- coding: utf-8 -*-
"""0.1.5 T4：forge-files 端点 + 路由/导航"""
from pathlib import Path

# 1. forge-files 端点（读 ~/.yuanzhu/templates/forge/ 下所有 YAML）
p = Path("src/yuanzhu/api/core.py")
src = p.read_text(encoding="utf-8")
old = '''@router.get("/templates")'''
new = '''@router.get("/templates/forge-files")
async def get_forge_files():
    """v0.1.5 知识库页：列出 forge 生成的模板源码（用户目录 YAML）"""
    from yuanzhu.template.forge import FORGE_ROOT
    if not FORGE_ROOT.is_dir():
        return []
    result = []
    for tpl_dir in sorted(FORGE_ROOT.iterdir()):
        if not tpl_dir.is_dir():
            continue
        files = {}
        for f in sorted(tpl_dir.rglob("*.yaml")):
            rel = str(f.relative_to(tpl_dir))
            try:
                files[rel] = f.read_text(encoding="utf-8")[:5000]   # 防超大
            except Exception:
                files[rel] = "# 读取失败"
        if files:
            result.append({"name": tpl_dir.name, "path": str(tpl_dir), "files": files})
    return result


@router.get("/templates")'''
assert src.count(old) == 1
p.write_text(src.replace(old, new), encoding="utf-8")
print("forge-files endpoint added")

# 2. 路由+导航
p = Path("web/src/router.ts")
src = p.read_text(encoding="utf-8")
old = "import Usage from './views/Usage.vue'"
new = "import Usage from './views/Usage.vue'\\nimport Knowledge from './views/Knowledge.vue'"
assert src.count(old) == 1
src = src.replace(old, new)
old2 = "    { path: '/usage', component: Usage },"
new2 = "    { path: '/usage', component: Usage },\\n    { path: '/knowledge', component: Knowledge },"
assert src.count(old2) == 1
src = src.replace(old2, new2)
p.write_text(src, encoding="utf-8")
print("router patched")

p = Path("web/src/App.vue")
src = p.read_text(encoding="utf-8")
old = '''      <router-link class="nav-item" to="/usage">用量与审计</router-link>'''
new = '''      <router-link class="nav-item" to="/knowledge">知识库</router-link>
      <router-link class="nav-item" to="/usage">用量与审计</router-link>'''
assert src.count(old) == 1
p.write_text(src.replace(old, new), encoding="utf-8")
print("nav patched")
