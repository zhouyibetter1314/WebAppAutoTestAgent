<template>
  <div class="shell">
    <aside>
      <div class="brand">W<span> / </span>A</div>
      <h2>自主测试工作台</h2>
      <p class="subtle">WebAppAutoTestAgent</p>
      <nav>
        <RouterLink to="/">场景与应用</RouterLink><RouterLink to="/runs">运行与报告</RouterLink
        ><RouterLink to="/settings">环境与设置</RouterLink>
      </nav>
      <div class="sidebar-note">LOCAL WORKSPACE<br />本机运行 · 证据可追溯</div>
    </aside>
    <main>
      <header>
        <span>工程实践 / Web 应用自主测试</span><span class="local-dot">本地工作空间</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>
