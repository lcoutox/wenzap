import Link from "next/link";

const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/dashboard/agents", label: "Agentes" },
  { href: "/dashboard/members", label: "Membros" },
  { href: "/dashboard/settings", label: "Configurações" },
  { href: "/dashboard/plan", label: "Plano e uso" },
];

export function Sidebar() {
  return (
    <aside className="w-56 min-h-screen bg-gray-900 text-gray-100 flex flex-col">
      <div className="px-4 py-5 border-b border-gray-700">
        <span className="font-bold text-lg tracking-tight">Nexbrain</span>
      </div>
      <nav className="flex-1 px-2 py-4 space-y-1">
        {nav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
