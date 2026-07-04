'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    Sidebar,
    SidebarContent,
    SidebarGroup,
    SidebarGroupContent,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
    SidebarRail,
} from '@/components/ui/sidebar';
import { useUserRole, ROLE_ROUTES, type UserRole } from '@/lib/useUserRole';
import {
    LayoutDashboard,
    TrendingUp,
    Building,
    Scale,
    Settings2,
    ClipboardCheck,
    FileText,
} from 'lucide-react';

interface NavItem {
    title: string;
    url: string;
    icon: React.ElementType;
}

const ALL_NAV_ITEMS: NavItem[] = [
    { title: 'Executive Dashboard', url: '/', icon: LayoutDashboard },
    { title: 'Macro Intelligence', url: '/macro', icon: TrendingUp },
    { title: 'Competitive Intelligence', url: '/competitive', icon: Building },
    { title: 'Regulatory Intelligence', url: '/regulatory', icon: Scale },
    { title: 'Administration', url: '/admin', icon: Settings2 },
    { title: 'Intelligence Review', url: '/review', icon: ClipboardCheck },
    { title: 'Policy Workspace', url: '/policy', icon: FileText },
];

function navForRole(role: UserRole | null): NavItem[] {
    if (!role) return [];
    const allowed = ROLE_ROUTES[role];
    return allowed
        .map((url) => ALL_NAV_ITEMS.find((item) => item.url === url))
        .filter((item): item is NavItem => Boolean(item));
}

export default function AppSidebar() {
    const pathname = usePathname();
    const { role, ready } = useUserRole();

    if (!ready) return null;
    if (pathname === '/login') return null;

    const visibleItems = navForRole(role);

    const isActive = (url: string) => {
        if (url === '/') return pathname === '/';
        return pathname === url || pathname.startsWith(url + '/');
    };

    return (
        <Sidebar collapsible="icon">
            <SidebarHeader className="p-3">
                <SidebarMenu>
                    <SidebarMenuItem>
                        <SidebarMenuButton
                            size="lg"
                            asChild
                            className="h-auto rounded-md border border-sidebar-border/70 p-3 group-data-[collapsible=icon]:!size-8 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:border-0"
                        >
                            <Link href="/">
                                <div className="flex h-10 w-20 shrink-0 items-center justify-center group-data-[collapsible=icon]:h-8 group-data-[collapsible=icon]:w-8 overflow-hidden group-data-[collapsible=icon]:justify-start">
                                    <Image
                                        src="/moneypal.png"
                                        alt="Moneypal"
                                        width={160}
                                        height={80}
                                        className="h-9 w-[72px] object-contain group-data-[collapsible=icon]:h-8 group-data-[collapsible=icon]:w-[64px] group-data-[collapsible=icon]:object-cover group-data-[collapsible=icon]:object-left"
                                    />
                                </div>
                                <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                                    <span className="truncate font-semibold tracking-tight text-[13px]">Moneypal</span>
                                    <span className="truncate font-mono text-[9px] uppercase tracking-widest text-sidebar-foreground/40">Genesis Console</span>
                                </div>
                            </Link>
                        </SidebarMenuButton>
                    </SidebarMenuItem>
                </SidebarMenu>
            </SidebarHeader>

            <SidebarContent>
                <SidebarGroup className="px-3 py-2">
                    <SidebarGroupLabel className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/40 mb-1">
                        Intelligence Modules
                    </SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            {visibleItems.map((item) => (
                                <SidebarMenuItem key={item.url}>
                                    <SidebarMenuButton
                                        asChild
                                        isActive={isActive(item.url)}
                                        tooltip={item.title}
                                        className="rounded-md text-[13px] text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground data-[active=true]:bg-primary data-[active=true]:text-primary-foreground"
                                    >
                                        <Link href={item.url}>
                                            <item.icon className="size-4" />
                                            <span>{item.title}</span>
                                        </Link>
                                    </SidebarMenuButton>
                                </SidebarMenuItem>
                            ))}
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>

                {/* GICC partner mark */}
                <SidebarGroup className="mt-auto px-3 py-2 group-data-[collapsible=icon]:hidden">
                    <SidebarGroupContent>
                        <div className="flex items-center gap-2 rounded-md border border-sidebar-border/70 p-2.5">
                            <div className="flex size-8 shrink-0 items-center justify-center overflow-hidden">
                                <Image
                                    src="/gicc.png"
                                    alt="GICC"
                                    width={32}
                                    height={32}
                                    className="size-8 object-contain"
                                />
                            </div>
                            <div className="grid text-left leading-tight">
                                <span className="truncate text-[11px] font-semibold">GICC</span>
                                <span className="truncate text-[9px] text-sidebar-foreground/40">Intelligence Partner</span>
                            </div>
                        </div>
                    </SidebarGroupContent>
                </SidebarGroup>
            </SidebarContent>

            <SidebarRail />
        </Sidebar>
    );
}
