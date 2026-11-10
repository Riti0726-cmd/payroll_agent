import { useTheme } from "../theme/ThemeProvider";
import styles from "./ThemeToggle.module.css";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={toggleTheme}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      <span className={styles.track} aria-hidden="true">
        <span className={styles.thumb} data-theme-active={theme} />
      </span>
      <span className={styles.label}>{theme === "dark" ? "Dark" : "Light"}</span>
    </button>
  );
}
