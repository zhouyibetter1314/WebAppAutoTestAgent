import asyncio
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import dotenv_values
from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    async_playwright,
)

from .config import Settings
from .schemas import Action, Application, LocatorSpec, Observation

CONTROL_SNAPSHOT = """elements => elements.filter(el => {
  const rect = el.getBoundingClientRect();
  return rect.width && rect.height && getComputedStyle(el).visibility !== 'hidden';
}).slice(0, 100).map(el => {
  const tag = el.tagName.toLowerCase();
  let selector = '';
  const attrs = ['id', 'data-testid', 'name', 'placeholder', 'aria-label', 'title'];
  for (const attr of attrs) {
    const value = el.getAttribute(attr);
    if (!value) continue;
    const candidate = tag + '[' + attr + '=' + JSON.stringify(value) + ']';
    try {
      if (document.querySelectorAll(candidate).length === 1) { selector = candidate; break; }
    } catch {}
  }
  if (!selector) {
    const parts = [];
    let node = el;
    while (node && node.tagName.toLowerCase() !== 'body') {
      const type = node.tagName.toLowerCase();
      let index = 1;
      for (let sibling = node.previousElementSibling; sibling;
           sibling = sibling.previousElementSibling)
        if (sibling.tagName === node.tagName) index++;
      parts.unshift(type + ':nth-of-type(' + index + ')');
      node = node.parentElement;
    }
    selector = 'body > ' + parts.join(' > ');
  }
  return {tag, selector, type: el.getAttribute('type') || '', name: el.getAttribute('name') || '',
    label: el.getAttribute('aria-label') || '', placeholder: el.getAttribute('placeholder') || '',
    text: tag === 'input' || tag === 'textarea' ? '' : (el.textContent || '').trim().slice(0, 200),
    disabled: Boolean(el.disabled)};
})"""


class StepLimit(RuntimeError):
    pass


class BrowserSession:
    def __init__(
        self, settings: Settings, application: Application, directory: Path, max_steps: int
    ) -> None:
        self.settings = settings
        self.application = application
        self.directory = directory
        self.max_steps = max_steps
        self.steps = 0
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.trace_saved = False
        environment = {**dotenv_values(".env"), **os.environ}
        self.secrets = {
            "{{username}}": environment.get(application.username_env, "") or ""
            if application.username_env
            else "",
            "{{password}}": environment.get(application.password_env, "") or ""
            if application.password_env
            else "",
        }

    def redact(self, value: str) -> str:
        for placeholder, secret in self.secrets.items():
            if secret:
                value = value.replace(secret, placeholder)
        return value

    async def start(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.playwright = await async_playwright().start()
        kwargs: dict[str, Any] = {"headless": self.settings.headless}
        if self.settings.browser_executable:
            kwargs["executable_path"] = self.settings.browser_executable
        self.browser = await self.playwright.chromium.launch(**kwargs)
        self.context = await self.browser.new_context(viewport={"width": 1440, "height": 960})
        self.context.set_default_timeout(self.settings.action_timeout_ms)
        await self.context.tracing.start(screenshots=True, snapshots=True, sources=False)
        self.page = await self.context.new_page()

    def locate(self, spec: LocatorSpec) -> Locator:
        assert self.page is not None
        match spec.by:
            case "role":
                return self.page.get_by_role(spec.value, name=spec.name, exact=True)  # type: ignore[arg-type]
            case "label":
                return self.page.get_by_label(spec.value, exact=True)
            case "text":
                return self.page.get_by_text(spec.value, exact=True)
            case "placeholder":
                return self.page.get_by_placeholder(spec.value, exact=True)
            case "test_id":
                return self.page.get_by_test_id(spec.value)
            case "css":
                return self.page.locator(spec.value)

    async def execute(self, action: Action) -> None:
        if self.steps >= self.max_steps:
            raise StepLimit("浏览器操作已达到上限")
        self.steps += 1  # Count BEFORE dispatch: failures and retries consume the same budget.
        assert self.page is not None
        match action.kind:
            case "navigate":
                allowed = urlsplit(str(self.application.base_url))
                target = urlsplit(str(action.url))
                if (target.scheme, target.netloc) != (allowed.scheme, allowed.netloc):
                    raise ValueError("导航地址必须属于配置的被测应用")
                await self.page.goto(str(action.url), wait_until="domcontentloaded")
            case "click":
                await self.locate(action.target).click()
            case "fill":
                value = action.value
                for placeholder, secret in self.secrets.items():
                    if placeholder in value:
                        if not secret:
                            raise ValueError(f"缺少 {placeholder} 对应的环境配置")
                        value = value.replace(placeholder, secret)
                await self.locate(action.target).fill(value)
            case "select":
                await self.locate(action.target).select_option(action.value)
            case "scroll":
                await self.page.mouse.wheel(0, action.delta_y)
            case "drag":
                await self.locate(action.source).drag_to(self.locate(action.destination))
            case "press":
                await self.locate(action.target).press(action.key)

    async def observe(self) -> Observation:
        assert self.page is not None
        for attempt in range(3):
            before_url = self.page.url
            before_title = await self.page.title()
            aria = await self.page.locator("body").aria_snapshot()
            controls = await self.page.locator(
                'input:not([type="hidden"]), textarea, select, button, a, [role="button"]'
            ).evaluate_all(CONTROL_SNAPSHOT)
            observation = Observation(
                url=self.redact(before_url),
                title=self.redact(before_title),
                aria=self.redact(aria),
                controls=json.loads(self.redact(json.dumps(controls))),
                screenshot="",
                snapshot="",
            )
            observation.screenshot = f"{observation.id}.png"
            observation.snapshot = f"{observation.id}.json"
            await self.page.screenshot(
                path=str(self.directory / observation.screenshot),
                full_page=True,
                mask=[self.page.locator('input[type="password"]')],
            )
            after_title = await self.page.title()
            if before_url == self.page.url and before_title == after_title:
                (self.directory / observation.snapshot).write_text(
                    observation.model_dump_json(indent=2), encoding="utf-8"
                )
                return observation
            # Discard evidence assembled across two pages; observing never consumes action budget.
            (self.directory / observation.screenshot).unlink(missing_ok=True)
            if attempt < 2:
                await asyncio.sleep(0.1)
        raise RuntimeError("页面仍在切换，无法获取一致的页面观察")

    async def close(self) -> None:
        try:
            if self.context:
                try:
                    await self.context.tracing.stop(path=str(self.directory / "trace.zip"))
                    self.trace_saved = True
                finally:
                    await self.context.close()
        finally:
            try:
                if self.browser:
                    await self.browser.close()
            finally:
                if self.playwright:
                    await self.playwright.stop()
