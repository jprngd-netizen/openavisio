import {
  MonitorDot,
  Building,
  UserCog,
  Building2,
  UserPlus,
  ClipboardList,
  ScrollText,
  Bot,
  BadgeCheck,
  Shield,
  UsersRound,
  type LucideIcon,
} from "lucide-react";

/**
 * Single source of truth for the Admin navigation.
 *
 * The desktop sidebar and the mobile "More" sheet each kept their own copy of
 * this list, and the mobile copy silently lost /admin/prescriber — so on a phone
 * there was no way into the prescriber screen. Keep them in one place.
 */
export type AdminNavKey =
  | "System"
  | "Organization"
  | "Users"
  | "Groups"
  | "Invitations"
  | "AuditLog"
  | "Logs"
  | "Ollama"
  | "License"
  | "DataGovernance"
  | "Prescriber";

export type AdminNavItem = {
  href: string;
  labelKey: AdminNavKey;
  icon: LucideIcon;
  color: string;
};

export const ADMIN_NAV: AdminNavItem[] = [
  { href: "/admin/system", labelKey: "System", icon: MonitorDot, color: "text-cyan-600 dark:text-cyan-400" },
  { href: "/admin/organization", labelKey: "Organization", icon: Building, color: "text-indigo-600 dark:text-indigo-400" },
  { href: "/admin/users", labelKey: "Users", icon: UserCog, color: "text-amber-600 dark:text-amber-400" },
  { href: "/admin/groups", labelKey: "Groups", icon: Building2, color: "text-sky-600 dark:text-sky-400" },
  { href: "/admin/invitations", labelKey: "Invitations", icon: UserPlus, color: "text-emerald-600 dark:text-emerald-400" },
  { href: "/admin/audit", labelKey: "AuditLog", icon: ClipboardList, color: "text-violet-600 dark:text-violet-400" },
  { href: "/admin/logs", labelKey: "Logs", icon: ScrollText, color: "text-slate-500 dark:text-slate-400" },
  { href: "/admin/ollama", labelKey: "Ollama", icon: Bot, color: "text-fuchsia-600 dark:text-fuchsia-400" },
  { href: "/admin/license", labelKey: "License", icon: BadgeCheck, color: "text-lime-600 dark:text-lime-400" },
  { href: "/admin/data-governance", labelKey: "DataGovernance", icon: Shield, color: "text-rose-600 dark:text-rose-400" },
  { href: "/admin/prescriber", labelKey: "Prescriber", icon: UsersRound, color: "text-teal-600 dark:text-teal-400" },
];