export function formatPrice(price: number) {
  return new Intl.NumberFormat("ru-RU").format(price) + " ₽";
}

export function formatQuantity(value: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 3 }).format(
    value,
  );
}

export function pluralize(
  count: number,
  [one, few, many]: [string, string, string],
) {
  const lastTwo = count % 100;
  const last = count % 10;

  if (lastTwo >= 11 && lastTwo <= 14) return many;
  if (last === 1) return one;
  if (last >= 2 && last <= 4) return few;

  return many;
}
