import { Clock, MapPin, Navigation, Phone } from "lucide-react";

import { PHONES, STORE_LOCATION, WORKING_HOURS } from "../shop/contacts";

/** Карта склада с маршрутом в Яндекс.Картах, 2ГИС и Google Maps. */
export default function StoreMap() {
  if (!STORE_LOCATION) return null;

  const { address, latitude, longitude, yandexUrl } = STORE_LOCATION;
  const point = `${longitude},${latitude}`;
  // Чистая карта с меткой: панель организации Яндекса перекрывала нашу карточку
  const mapUrl = `https://yandex.ru/map-widget/v1/?ll=${point}&z=16&pt=${point},pm2brm`;
  const routes = [
    { name: "Яндекс Карты", href: yandexUrl },
    { name: "2ГИС", href: `https://2gis.ru/routeSearch/rsType/car/to/${point}` },
    { name: "Google Maps", href: `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}` },
  ];

  return (
    <div className="store-map">
      <iframe
        className="store-map-frame"
        src={mapUrl}
        title={`Склад на карте: ${address}`}
        loading="lazy"
        allowFullScreen
      />

      <div className="store-map-card">
        <span className="home-eyebrow">Как нас найти</span>
        <h3>
          <MapPin size={20} /> {address}
        </h3>
        <p>
          <Clock size={16} /> {WORKING_HOURS}
        </p>
        {PHONES.map((phone) => (
          <a key={phone.href} href={phone.href} className="store-map-phone">
            <Phone size={16} /> {phone.display}
          </a>
        ))}

        <div className="store-map-routes">
          {routes.map((route) => (
            <a key={route.name} href={route.href} target="_blank" rel="noreferrer">
              <Navigation size={15} /> {route.name}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
