import { describe, expect, it } from "vitest";
import { createGraphEdgeCurve, findGraphEdgeCandidates, type GraphEdgeCurve } from "./graph-edge-selection";

function horizontal(edgeId: string, y: number): GraphEdgeCurve { return { edgeId, path: "unused fixture line", points: [{ x: 0, y }, { x: 100, y }] }; }
describe("R17 fix1 pointer geometry independent of paint order", () => {
  it("selects the nearest curve instead of the last overlapping hit target", () => {
    expect(findGraphEdgeCandidates([horizontal("near", 0), horizontal("last-painted", 9)], { x: 50, y: 0 }, 1)).toEqual(["near"]);
  });
  it("offers both exactly overlapping inverse curves without silently selecting either", () => {
    const forward = createGraphEdgeCurve("forward", { x: 295, y: 145 }, { x: 485, y: 145 }, 1);
    const inverse = createGraphEdgeCurve("inverse", { x: 485, y: 145 }, { x: 295, y: 145 }, 5);
    const point = { x: 390, y: 196 };
    expect(new Set(findGraphEdgeCandidates([forward, inverse], point, 1))).toEqual(new Set(["forward", "inverse"]));
    expect(findGraphEdgeCandidates([inverse, forward], point, 1)).toEqual(findGraphEdgeCandidates([forward, inverse], point, 1));
  });
  it("retains near crossing ambiguity within four screen pixels", () => {
    expect(findGraphEdgeCandidates([horizontal("first", 0), horizontal("second", 3)], { x: 50, y: 0 }, 1)).toEqual(["first", "second"]);
  });
  it.each([0.8, 1, 1.8])("uses screen pixels at %s zoom for touch proximity", (zoom) => {
    expect(findGraphEdgeCandidates([horizontal("one", 0)], { x: 50, y: 21 / zoom }, zoom)).toEqual(["one"]);
    expect(findGraphEdgeCandidates([horizontal("one", 0)], { x: 50, y: 30 / zoom }, zoom)).toEqual([]);
  });
  it("uses segment endpoints rather than an infinite supporting line", () => {
    expect(findGraphEdgeCandidates([horizontal("one", 0)], { x: 150, y: 0 }, 1)).toEqual([]);
  });
  it("handles collapsed curve segments safely", () => {
    expect(findGraphEdgeCandidates([{ edgeId: "one", path: "fixture", points: [{ x: 5, y: 5 }, { x: 5, y: 5 }] }], { x: 5, y: 5 }, 1)).toEqual(["one"]);
  });
  it("bounds sampling and preserves exact curve endpoints", () => {
    const curve = createGraphEdgeCurve("one", { x: 295, y: 145 }, { x: 865, y: 22000 }, 399);
    expect(curve.points).toHaveLength(129); expect(curve.points[0]).toEqual({ x: 295, y: 145 }); expect(curve.points[128]).toEqual({ x: 865, y: 22000 });
  });
  it.each([0, Number.NaN])("rejects invalid scale %s rather than selecting arbitrary contents", (scale) => {
    expect(findGraphEdgeCandidates([horizontal("one", 0)], { x: 50, y: 0 }, scale)).toEqual([]);
  });
});
