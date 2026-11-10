import { animate, stagger } from "animejs";

export function animateEnter(root: HTMLElement | null) {
  if (!root || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }

  animate(root.querySelectorAll("[data-enter]"), {
    opacity: [0, 1],
    translateY: [8, 0],
    ease: "outQuad",
    duration: 420,
    delay: stagger(40),
  });
}
