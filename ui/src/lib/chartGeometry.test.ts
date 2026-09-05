import { test } from "node:test";
import assert from "node:assert/strict";
import { BOTTOM, HEIGHT, LEFT, RIGHT, TOP, WIDTH, calloutOrigin, sessionIndexAt } from "./chartGeometry.ts";

const MIDPOINT = (LEFT + RIGHT) / 2;

test("x at or before the plot's left edge maps to the first session", () => {
  assert.equal(sessionIndexAt(LEFT, 90), 0);
  assert.equal(sessionIndexAt(0, 90), 0);
  assert.equal(sessionIndexAt(-50, 90), 0);
});

test("x at or after the plot's right edge maps to the last session", () => {
  assert.equal(sessionIndexAt(RIGHT, 90), 89);
  assert.equal(sessionIndexAt(WIDTH, 90), 89);
  assert.equal(sessionIndexAt(RIGHT + 500, 90), 89);
});

test("x at the horizontal midpoint maps to the middle session for odd counts", () => {
  assert.equal(sessionIndexAt(MIDPOINT, 5), 2);
  assert.equal(sessionIndexAt(MIDPOINT, 91), 45);
});

test("x at the horizontal midpoint rounds up to the upper middle session for even counts", () => {
  assert.equal(sessionIndexAt(MIDPOINT, 4), 2);
  assert.equal(sessionIndexAt(MIDPOINT, 90), 45);
});

test("two sessions split the plot in half", () => {
  assert.equal(sessionIndexAt(MIDPOINT - 1, 2), 0);
  assert.equal(sessionIndexAt(MIDPOINT + 1, 2), 1);
});

const BOX = { width: 118, height: 46 };

function assertInside({ x, y }: { x: number; y: number }) {
  assert.ok(x >= 0, `x ${x} is left of the canvas`);
  assert.ok(y >= 0, `y ${y} is above the canvas`);
  assert.ok(x + BOX.width <= WIDTH, `x ${x} overflows the right of the canvas`);
  assert.ok(y + BOX.height <= HEIGHT, `y ${y} overflows the bottom of the canvas`);
}

test("callout stays inside the canvas when the point is at the left edge", () => {
  assertInside(calloutOrigin(LEFT, 100, BOX.width, BOX.height));
});

test("callout stays inside the canvas when the point is at the right edge", () => {
  assertInside(calloutOrigin(RIGHT, 100, BOX.width, BOX.height));
});

test("callout stays inside the canvas when the point is at the top edge", () => {
  assertInside(calloutOrigin(300, TOP, BOX.width, BOX.height));
});

test("callout stays inside the canvas when the point is at the bottom edge", () => {
  assertInside(calloutOrigin(300, BOTTOM, BOX.width, BOX.height));
});

test("callout sits above and to the left of an interior point", () => {
  assert.deepEqual(calloutOrigin(300, 100, BOX.width, BOX.height), { x: 300 - BOX.width + 6, y: 100 - BOX.height - 10 });
});
