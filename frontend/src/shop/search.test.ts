import { describe, expect, it } from "vitest";

import { matchScore, normalize, searchTokens } from "./search";

const board = { title: "Доска обрезная 50×150×6000", extra: ["Хвоя, для каркаса и стропил", "Пиломатериалы"] };
const screws = { title: "Саморезы по дереву 4,2×75" };

const score = (query: string, fields: { title: string; extra?: string[] }) =>
  matchScore(searchTokens(query), fields);

describe("normalize", () => {
  it("приводит размеры, ё и запятые к одному виду", () => {
    expect(normalize("Ёлка 50х150")).toBe("елка 50 150");
    expect(normalize("50x150*6000")).toBe("50 150 6000");
    expect(normalize("4,2×75")).toBe("4.2 75");
  });
});

describe("поиск по ключевым словам", () => {
  it("находит по словам в любом порядке и с другим окончанием", () => {
    expect(score("доски 50х150", board)).toBeGreaterThan(0);
    expect(score("обрезную доску", board)).toBeGreaterThan(0);
    expect(score("саморезы 4.2", screws)).toBeGreaterThan(0);
  });

  it("числа сравниваются целиком: 50 не находит 500", () => {
    expect(score("доска 500", board)).toBe(0);
    expect(score("доска 15", board)).toBe(0);
  });

  it("каждое слово должно найтись", () => {
    expect(score("доска брус", board)).toBe(0);
  });

  it("совпадение в названии весит больше, чем в описании", () => {
    expect(score("доска", board)).toBeGreaterThan(score("каркас", board));
    expect(score("каркас", board)).toBeGreaterThan(0);
  });

  it("пустой запрос подходит ко всему", () => {
    expect(score("   ", board)).toBe(1);
  });

  it("OSB и ОСП — синонимы ОСБ", () => {
    const osb = { title: "ОСБ-3 9 мм" };
    expect(score("osb", osb)).toBeGreaterThan(0);
    expect(score("осп 9", osb)).toBeGreaterThan(0);
  });
});
