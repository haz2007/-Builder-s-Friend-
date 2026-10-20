/**
 * Поиск по ключевым словам: слова запроса в любом порядке, без учёта
 * регистра, «ё», окончаний и записи размеров.
 *
 *   «доски 50х150»   → «Доска обрезная 50×150×6000»
 *   «обрезная доска» → то же самое
 *   «саморезы»       → «Саморезы по дереву 4,2×75»
 */

// Окончания, которые отбрасываем: «доски» и «доску» ищутся как «доск»
const ENDINGS = /(ами|ями|ов|ев|ей|ой|ий|ый|ая|яя|ое|ее|ые|ие|ую|юю|ом|ем|ах|ях|ам|ям|а|я|ы|и|у|ю|е|о|ь)$/;

// Одно и то же разными словами
const SYNONYMS: Record<string, string> = {
  osb: "осб",
  осп: "осб",
  мм: "",
  шт: "",
};

export function normalize(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/ё/g, "е")
      // Размеры: 50x150, 50х150 (русская «х»), 50×150, 50*150 → «50 150»
      .replace(/(\d)\s*[xх×*]\s*(?=\d)/g, "$1 ")
      // 4,2 и 4.2 — одно число
      .replace(/(\d),(\d)/g, "$1.$2")
      .replace(/[^a-zа-я0-9.]+/g, " ")
      .trim()
  );
}

function stem(word: string): string {
  if (/^\d/.test(word)) return word;
  const synonym = SYNONYMS[word];
  if (synonym !== undefined) return synonym;
  if (word.length <= 4) return word;
  const short = word.replace(ENDINGS, "");
  return short.length >= 3 ? short : word;
}

export function searchTokens(query: string): string[] {
  return normalize(query)
    .split(" ")
    .map(stem)
    .filter(Boolean);
}

/**
 * Сколько очков набирает текст по запросу; 0 — не подходит.
 * Каждое слово запроса должно найтись: число — точно, слово — по началу.
 * Совпадения в названии весят больше, чем в описании.
 */
export function matchScore(
  tokens: string[],
  fields: { title: string; extra?: string[] },
): number {
  if (tokens.length === 0) return 1;

  const titleWords = normalize(fields.title).split(" ");
  const extraWords = normalize((fields.extra ?? []).join(" ")).split(" ");

  const fits = (words: string[], token: string) =>
    words.some((word) =>
      /^\d/.test(token) ? word === token : word.startsWith(token),
    );

  let score = 0;
  for (const token of tokens) {
    if (fits(titleWords, token)) score += 3;
    else if (fits(extraWords, token)) score += 1;
    else return 0;
  }
  return score;
}
