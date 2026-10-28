import { describe, expect, it } from "vitest";
import { formatFen, formatFenInput, parseYuanToFen } from "./money";

describe("budget money helpers", () => {
  it("parses decimal text exactly to integer fen", () => {
    expect(parseYuanToFen("6000")).toBe(600000);
    expect(parseYuanToFen("12.3")).toBe(1230);
    expect(parseYuanToFen("0.01")).toBe(1);
    expect(parseYuanToFen("")).toBeNull();
  });

  it.each(["1.001", "-1", "1e3", "NaN", "1."]) (
    "rejects unsupported decimal text %s",
    (value) => expect(() => parseYuanToFen(value)).toThrow(),
  );

  it("rejects values beyond safe integer fen and formats null distinctly from zero", () => {
    expect(() => parseYuanToFen("90071992547409.92")).toThrow("安全计算");
    expect(formatFen(null)).toBe("待核实");
    expect(formatFen(0)).toContain("0.00");
    expect(formatFenInput(1)).toBe("0.01");
  });
});
