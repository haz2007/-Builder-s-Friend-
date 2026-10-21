import { Link } from "react-router-dom";

/**
 * Галочка согласия при регистрации. Согласие — отдельный документ (/consent),
 * политика — отдельная ссылка (152-ФЗ в редакции 156-ФЗ). Не отмечена заранее.
 */
export default function ConsentCheckbox({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="checkout-consent">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        required
      />
      <span>
        Даю{" "}
        <Link to="/consent" target="_blank" rel="noopener">
          согласие на обработку персональных данных
        </Link>
        . С{" "}
        <Link to="/privacy" target="_blank" rel="noopener">
          политикой конфиденциальности
        </Link>{" "}
        ознакомлен(а).
      </span>
    </label>
  );
}
