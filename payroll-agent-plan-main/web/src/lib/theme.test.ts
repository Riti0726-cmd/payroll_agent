import { beforeEach, describe, expect, it } from "vitest";
import { applyTheme, getStoredTheme, resolveInitialTheme, THEME_STORAGE_KEY } from "./theme";

describe("theme", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to dark when nothing is stored", () => {
    expect(resolveInitialTheme()).toBe("dark");
  });

  it("persists and restores light theme", () => {
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(getStoredTheme()).toBe("light");
    expect(resolveInitialTheme()).toBe("light");
  });
});
