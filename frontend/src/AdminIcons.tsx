import {
  ArrowRight,
  Camera,
  Check,
  Download,
  Eye,
  EyeOff,
  KeyRound,
  Layers,
  LogOut,
  Pencil,
  Printer,
  RefreshCw,
  Store,
  Trash2,
  UserMinus,
  X,
} from "lucide-react";

// Иконки кнопок админки — те же lucide, что и на сайте
const ICONS = {
  edit: Pencil,
  layers: Layers,
  eye: Eye,
  eyeOff: EyeOff,
  trash: Trash2,
  camera: Camera,
  arrow: ArrowRight,
  close: X,
  refresh: RefreshCw,
  save: Check,
  userMinus: UserMinus,
  logout: LogOut,
  store: Store,
  key: KeyRound,
  print: Printer,
  download: Download,
};

export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  const Component = ICONS[name];
  return <Component className="admin-icon" size={size} strokeWidth={1.9} aria-hidden="true" />;
}
