export const WIDTH = 620;
export const HEIGHT = 230;
export const LEFT = 48;
export const RIGHT = 600;
export const TOP = 14;
export const BOTTOM = 195;
export const BAR_MAX = 100;

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

export function sessionIndexAt(viewBoxX: number, count: number) {
  const lastIndex = count - 1;
  if (viewBoxX <= LEFT) return 0;
  if (viewBoxX >= RIGHT) return lastIndex;
  return Math.round(((viewBoxX - LEFT) / (RIGHT - LEFT)) * lastIndex);
}

export function calloutOrigin(pointX: number, pointY: number, boxWidth: number, boxHeight: number) {
  return {
    x: clamp(pointX - boxWidth + 6, 0, RIGHT - boxWidth),
    y: clamp(pointY - boxHeight - 10, 0, HEIGHT - boxHeight),
  };
}
