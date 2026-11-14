import { describe, expect, it } from "vitest";
import { toCsv } from "./export";

const cols = [{ header: "Name", value: (r: { n: string }) => r.n }, { header: "Amount", value: (r: { n: string }) => r.n.length }];

describe("toCsv", () => {
  it("writes a header and CRLF rows", () => {
    expect(toCsv([{ n: "ab" }], cols)).toBe("Name,Amount\r\nab,2\r\n");
  });
  it("quotes commas, quotes and newlines", () => {
    expect(toCsv([{ n: 'a,"b"' }], cols)).toContain('"a,""b"""');
    expect(toCsv([{ n: "x\ny" }], cols)).toContain('"x\ny"');
  });
  it("neutralises spreadsheet formulas but keeps plain negative numbers", () => {
    expect(toCsv([{ n: "=SUM(A1)" }], cols)).toContain("'=SUM(A1)");
    expect(toCsv([{ n: "@cmd" }], cols)).toContain("'@cmd");
    expect(toCsv([{ n: "-250" }], cols)).toContain("-250");
  });
  it("writes empty cells for missing values", () => {
    expect(toCsv([{ n: "z" }], [{ header: "A", value: () => null }])).toBe("A\r\n\r\n");
  });
});
