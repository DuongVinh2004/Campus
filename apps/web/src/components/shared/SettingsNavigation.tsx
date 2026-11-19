import Link from "next/link";
import { ShieldCheck, Brain, Bell } from "lucide-react";

export function SettingsNavigation({ active }: { active: "privacy" | "memory" | "notifications" }) {
  return <nav className="campus-settings-tabs" aria-label="Cài đặt cá nhân">{[
    { key: "privacy", href: "/privacy", label: "Quyền riêng tư", icon: ShieldCheck },
    { key: "memory", href: "/memory", label: "Bộ nhớ trợ lý", icon: Brain },
    { key: "notifications", href: "/notifications", label: "Thông báo", icon: Bell },
  ].map(item => <Link key={item.key} href={item.href} aria-current={active === item.key ? "page" : undefined}><item.icon size={17} />{item.label}</Link>)}</nav>;
}
