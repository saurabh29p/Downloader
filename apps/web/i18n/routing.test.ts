import { describe, expect, it } from "vitest";

import ar from "@/messages/ar.json";
import en from "@/messages/en.json";
import hi from "@/messages/hi.json";

import { dirFor } from "./routing";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe("i18n", () => {
  it("uses RTL only for Arabic", () => {
    expect(dirFor("ar")).toBe("rtl");
    expect(dirFor("en")).toBe("ltr");
    expect(dirFor("hi")).toBe("ltr");
  });

  it("has the same message keys in every language", () => {
    const expected = keys(en).sort();
    expect(keys(hi).sort()).toEqual(expected);
    expect(keys(ar).sort()).toEqual(expected);
  });
});
