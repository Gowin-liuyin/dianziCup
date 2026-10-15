import { describe, expect, it } from "vitest";
import { formatShanghaiTimestamp } from "./date-time";

describe("Beijing reporting timestamps", () => {
  it.each([
    ["2026-10-15T06:19:29.380687Z", "2026-10-15T14:19:29+08:00"],
    ["2026-12-31T23:59:59.999Z", "2027-01-01T07:59:59+08:00"],
    ["2026-10-15T23:10:09-07:00", "2026-10-16T14:10:09+08:00"],
    ["2026-10-15T14:19:29+08:00", "2026-10-15T14:19:29+08:00"],
  ])("formats %s at second precision", (value, expected) => {
    expect(formatShanghaiTimestamp(value)).toBe(expected);
  });

  it("does not turn an invalid timestamp into a fabricated date", () => {
    expect(() => formatShanghaiTimestamp("unknown")).toThrow(RangeError);
  });
});
