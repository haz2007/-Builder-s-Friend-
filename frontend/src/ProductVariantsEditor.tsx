import { useState, type FormEvent } from "react";

import {
  createVariant,
  deleteVariant,
  updateVariant,
  type ApiProduct,
  type ApiProductVariant,
} from "./api";

type VariantDraft = {
  name: string;
  unit: string;
  price: string;
  base_quantity: string;
};

const emptyDraft: VariantDraft = {
  name: "",
  unit: "",
  price: "",
  base_quantity: "1",
};

const CUBIC_UNITS = ["м3", "м³", "куб", "куб.м", "м.куб"];

function isCubicUnit(unit: string) {
  return CUBIC_UNITS.includes(unit.trim().toLowerCase().replace(/\.$/, ""));
}

type Props = {
  product: ApiProduct;
  token: string;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

function toDraft(variant: ApiProductVariant): VariantDraft {
  return {
    name: variant.name,
    unit: variant.unit,
    price: String(variant.price),
    base_quantity: String(variant.base_quantity),
  };
}

function parseDraft(draft: VariantDraft) {
  const price = Number(draft.price.replace(",", "."));
  const baseQuantity = Number(draft.base_quantity.replace(",", "."));

  if (!draft.name.trim() || !draft.unit.trim()) {
    throw new Error("Укажи название и единицу измерения варианта.");
  }

  if (!Number.isFinite(price) || price <= 0) {
    throw new Error("Цена варианта должна быть больше нуля.");
  }

  if (!Number.isFinite(baseQuantity) || baseQuantity <= 0) {
    throw new Error("Количество в единице варианта должно быть больше нуля.");
  }

  return {
    name: draft.name.trim(),
    unit: draft.unit.trim(),
    price,
    base_quantity: baseQuantity,
  };
}

/** Варианты продажи товара: например, доска за м³ и за штуку. */
export default function ProductVariantsEditor({
  product,
  token,
  onChanged,
  onError,
  onNotice,
}: Props) {
  const [drafts, setDrafts] = useState<Record<number, VariantDraft>>({});
  const [newDraft, setNewDraft] = useState<VariantDraft>(emptyDraft);
  const [busyId, setBusyId] = useState<number | "new" | null>(null);

  const primaryId =
    product.variants.find((variant) => variant.is_active === 1)?.id ?? null;

  // У досок с размерами кубы пересчитываются автоматически
  function isAutoBase(unit: string) {
    return product.pieces_per_cubic_meter !== null && isCubicUnit(unit);
  }

  function baseLabel(unit: string) {
    return `${product.unit} в 1 ${unit.trim() || "ед."}`;
  }

  function getDraft(variant: ApiProductVariant) {
    return drafts[variant.id] ?? toDraft(variant);
  }

  function changeDraft(
    variant: ApiProductVariant,
    field: keyof VariantDraft,
    value: string,
  ) {
    setDrafts((current) => ({
      ...current,
      [variant.id]: { ...getDraft(variant), [field]: value },
    }));
  }

  async function run(
    id: number | "new",
    action: () => Promise<unknown>,
    successMessage: string,
  ) {
    setBusyId(id);
    onError("");

    try {
      await action();
      await onChanged();
      onNotice(successMessage);
      return true;
    } catch (error) {
      onError(
        error instanceof Error ? error.message : "Не удалось сохранить вариант.",
      );
      return false;
    } finally {
      setBusyId(null);
    }
  }

  async function saveVariant(variant: ApiProductVariant) {
    const saved = await run(
      variant.id,
      () => updateVariant(product.id, variant.id, parseDraft(getDraft(variant)), token),
      "Вариант сохранён.",
    );

    if (saved) {
      setDrafts((current) => {
        const next = { ...current };
        delete next[variant.id];
        return next;
      });
    }
  }

  async function toggleVariant(variant: ApiProductVariant) {
    const isActive = variant.is_active === 1;

    await run(
      variant.id,
      () =>
        updateVariant(
          product.id,
          variant.id,
          { is_active: isActive ? 0 : 1 },
          token,
        ),
      isActive ? "Вариант скрыт из каталога." : "Вариант снова в продаже.",
    );
  }

  async function removeVariant(variant: ApiProductVariant) {
    if (!window.confirm(`Удалить вариант «${variant.name}»?`)) return;

    await run(
      variant.id,
      () => deleteVariant(product.id, variant.id, token),
      "Вариант удалён. Если он был в заказах — он просто скрыт.",
    );
  }

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    let data;
    try {
      data = parseDraft(newDraft);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Проверь поля варианта.");
      return;
    }

    const saved = await run(
      "new",
      () => createVariant(product.id, data, token),
      "Вариант добавлен.",
    );

    if (saved) setNewDraft(emptyDraft);
  }

  return (
    <div className="admin-variants admin-full" id="product-variants">
      <div className="admin-variants-heading">
        <strong>Варианты продажи</strong>
        <p>
          Склад у товара общий — в единице «{product.unit}». Каждый вариант
          продаётся по своей цене и списывает со склада указанное количество.
          Например, «Куб» списывает столько досок, сколько целых входит в
          1 м³. Цена основного варианта совпадает с ценой в форме выше.
        </p>
      </div>

      <div className="admin-variant-list">
        {product.variants.map((variant) => {
          const draft = getDraft(variant);
          const busy = busyId === variant.id;

          return (
            <div
              className={`admin-variant-row ${
                variant.is_active === 1 ? "" : "is-inactive"
              }`}
              key={variant.id}
            >
              <input
                aria-label="Название варианта"
                value={draft.name}
                onChange={(event) =>
                  changeDraft(variant, "name", event.target.value)
                }
              />
              <input
                aria-label="Единица измерения"
                value={draft.unit}
                onChange={(event) =>
                  changeDraft(variant, "unit", event.target.value)
                }
              />
              <input
                aria-label="Цена, ₽"
                inputMode="decimal"
                value={draft.price}
                onChange={(event) =>
                  changeDraft(variant, "price", event.target.value)
                }
              />
              <label className="admin-variant-base">
                <input
                  aria-label={baseLabel(draft.unit)}
                  inputMode="decimal"
                  value={
                    isAutoBase(draft.unit)
                      ? String(product.pieces_per_cubic_meter)
                      : draft.base_quantity
                  }
                  disabled={isAutoBase(draft.unit)}
                  onChange={(event) =>
                    changeDraft(variant, "base_quantity", event.target.value)
                  }
                />
                <small>
                  {baseLabel(draft.unit)}
                  {isAutoBase(draft.unit) && " · авто"} · в наличии{" "}
                  {variant.stock_quantity}
                </small>
              </label>

              <div className="admin-variant-actions">
                {variant.id === primaryId && (
                  <span className="admin-variant-badge">основной</span>
                )}
                {variant.is_active !== 1 && (
                  <span className="admin-variant-badge is-muted">скрыт</span>
                )}
                <button
                  type="button"
                  className="admin-secondary"
                  disabled={busy || !drafts[variant.id]}
                  onClick={() => saveVariant(variant)}
                >
                  Сохранить
                </button>
                <button
                  type="button"
                  className="admin-secondary"
                  disabled={busy}
                  onClick={() => toggleVariant(variant)}
                >
                  {variant.is_active === 1 ? "Скрыть" : "Вернуть"}
                </button>
                <button
                  type="button"
                  className="admin-secondary"
                  disabled={busy}
                  onClick={() => removeVariant(variant)}
                >
                  Удалить
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Отдельная форма, а не вложенная: форма товара — родительская */}
      <form className="admin-variant-row is-new" onSubmit={handleAdd}>
        <input
          placeholder="Название, например «Штука»"
          aria-label="Название нового варианта"
          value={newDraft.name}
          onChange={(event) =>
            setNewDraft({ ...newDraft, name: event.target.value })
          }
        />
        <input
          placeholder="Ед., например «шт»"
          aria-label="Единица измерения нового варианта"
          value={newDraft.unit}
          onChange={(event) =>
            setNewDraft({ ...newDraft, unit: event.target.value })
          }
        />
        <input
          placeholder="Цена, ₽"
          aria-label="Цена нового варианта"
          inputMode="decimal"
          value={newDraft.price}
          onChange={(event) =>
            setNewDraft({ ...newDraft, price: event.target.value })
          }
        />
        <label className="admin-variant-base">
          <input
            aria-label={baseLabel(newDraft.unit)}
            inputMode="decimal"
            value={
              isAutoBase(newDraft.unit)
                ? String(product.pieces_per_cubic_meter)
                : newDraft.base_quantity
            }
            disabled={isAutoBase(newDraft.unit)}
            onChange={(event) =>
              setNewDraft({ ...newDraft, base_quantity: event.target.value })
            }
          />
          <small>
            {baseLabel(newDraft.unit)}
            {isAutoBase(newDraft.unit) && " · авто"}
          </small>
        </label>
        <div className="admin-variant-actions">
          <button className="admin-primary" disabled={busyId === "new"}>
            {busyId === "new" ? "Добавляем..." : "Добавить вариант"}
          </button>
        </div>
      </form>
    </div>
  );
}
