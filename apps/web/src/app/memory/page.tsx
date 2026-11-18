"use client";
import { SettingsNavigation } from "@/components/shared/SettingsNavigation";
import { AppShell } from "@/components/AppShell";
import { MemoryCenter } from "@/features/memory/MemoryCenter";
export default function MemoryPage() { return <AppShell activeNav="memory"><div className="campus-settings-page"><header className="campus-page-heading"><div><h1>Bộ nhớ trợ lý</h1><p>Xem và quản lý thông tin trợ lý được phép ghi nhớ.</p></div></header><SettingsNavigation active="memory" /><MemoryCenter /></div></AppShell>; }
