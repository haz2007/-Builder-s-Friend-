import type { InputHTMLAttributes } from "react";

import { formatPhone, PHONE_PATTERN, PHONE_PREFIX } from "../shop/phone";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & {
  value: string;
  onChange: (value: string) => void;
};

/** Поле телефона: «+7» подставляется само, номер форматируется по мере ввода. */
export default function PhoneInput({ value, onChange, ...rest }: Props) {
  return (
    <input
      {...rest}
      type="tel"
      inputMode="tel"
      autoComplete="tel"
      placeholder="+7 999 123-45-67"
      pattern={PHONE_PATTERN}
      title="Номер из 10 цифр после +7"
      maxLength={16}
      value={value}
      onFocus={(event) => {
        if (!value) onChange(PHONE_PREFIX);
        rest.onFocus?.(event);
      }}
      onBlur={(event) => {
        // Пустое «+7 » не отправляем — поле снова показывает подсказку
        if (!formatPhone(value)) onChange("");
        rest.onBlur?.(event);
      }}
      onChange={(event) => onChange(formatPhone(event.target.value) || PHONE_PREFIX)}
    />
  );
}
