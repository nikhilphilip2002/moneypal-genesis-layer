'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { auth } from '@/lib/api';
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
    SidebarMenuSub,
    SidebarMenuSubButton,
    SidebarMenuSubItem,
    SidebarRail,
} from '@/components/ui/sidebar';
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from '@radix-ui/react-collapsible';
import {
    MessageSquare,
    Zap,
    MessageCircle,
    Building,
    Search,
    Database,
    BarChart3,
    Briefcase,
    ChevronRight,
    Mail,
    Network,
    ClipboardCheck,
    Sparkles,
} from 'lucide-react';

interface NavItem {
    title: string;
    url: string;
    icon: React.ElementType;
}

interface NavSection {
    title: string;
    icon: React.ElementType;
    items: NavItem[];
}

const chatSection: NavSection = {
    title: 'Chat',
    icon: MessageSquare,
    items: [
        { title: 'Company Intel', url: '/intel', icon: Zap },
        { title: 'General Intel', url: '/general-chat', icon: MessageCircle },
    ],
};

const insightsSection: NavSection = {
    title: 'Insights',
    icon: Sparkles,
    items: [
        { title: 'YouTube Snippets', url: '/youtube-chat', icon: Zap },
        { title: 'iBridge Analysis', url: '/ibridge-analysis', icon: ClipboardCheck },
    ],
};

function getStandaloneItems(userRole: string): NavItem[] {
    if (userRole === 'admin') {
        return [
            { title: 'Job Requirements', url: '/intel/requirements', icon: Briefcase },
            { title: 'Companies', url: '/companies', icon: Building },
            { title: 'Email KB', url: '/email-knowledge-base', icon: Mail },
            { title: 'Curiosity Graph', url: '/curiosity-graph', icon: Network },
            { title: 'Search History', url: '/search-history', icon: Search },
            { title: 'Retrieval', url: '/retrieval', icon: Database },
            { title: 'Usage', url: '/usage', icon: BarChart3 },
        ];
    }
    if (userRole === 'manager') {
        return [
            { title: 'Job Requirements', url: '/intel/requirements', icon: Briefcase },
            { title: 'Companies', url: '/companies', icon: Building },
            { title: 'Retrieval', url: '/retrieval', icon: Database },
            { title: 'Usage', url: '/usage', icon: BarChart3 },
        ];
    }
    return [
        { title: 'Companies', url: '/companies', icon: Building },
    ];
}

const adminExclusivePaths = ['/search-history', '/email-knowledge-base', '/curiosity-graph'];
const standardAllowedChatPaths = ['/general-chat'];
const standardAllowedInsightsPaths = ['/youtube-chat', '/ibridge-analysis'];
const standardAllowedStandalonePaths = ['/companies'];

export default function AppSidebar() {
    const pathname = usePathname();
    const [role, setRole] = useState<string>('standard');
    const [isInitialized, setIsInitialized] = useState(false);

    useEffect(() => {
        auth.me()
            .then(user => {
                const userRole = user.role || (user.is_staff ? 'admin' : 'standard');
                setRole(userRole);
            })
            .catch(() => setRole('standard'))
            .finally(() => setIsInitialized(true));
    }, [pathname]);

    if (!isInitialized) return null;
    if (pathname === '/login' || pathname === '/register' || pathname === '/callback') return null;

    const visibleChatItems = chatSection.items.filter(item => {
        if (role === 'admin' || role === 'manager') return true;
        return standardAllowedChatPaths.includes(item.url);
    });

    const visibleInsightsItems = insightsSection.items.filter(item => {
        if (role === 'admin' || role === 'manager') return true;
        return standardAllowedInsightsPaths.includes(item.url);
    });

    const visibleItems = getStandaloneItems(role).filter(item => {
        if (role === 'admin') return true;
        if (role === 'manager') return !adminExclusivePaths.includes(item.url);
        return standardAllowedStandalonePaths.includes(item.url);
    });

    const isActive = (url: string) => {
        if (url === '/') return pathname === '/';
        return pathname === url || pathname.startsWith(url + '/');
    };

    const isChatSectionActive = chatSection.items.some(item => isActive(item.url));
    const isInsightsSectionActive = insightsSection.items.some(item => isActive(item.url));

    return (
        <Sidebar collapsible="icon">
            <SidebarHeader className="p-3">
                <SidebarMenu>
                    <SidebarMenuItem>
                        <SidebarMenuButton
                            size="lg"
                            asChild
                            className="h-auto rounded-md border border-sidebar-border/70 p-3 group-data-[collapsible=icon]:p-2"
                        >
                            <Link href="/">
                                <div className="flex size-12 items-center justify-center rounded-lg bg-white shadow-sm ring-1 ring-black/5 group-data-[collapsible=icon]:size-8">
                                    <Image
                                        src="/aroha.png"
                                        alt="Aroha"
                                        width={48}
                                        height={48}
                                        className="size-11 object-contain group-data-[collapsible=icon]:size-7"
                                    />
                                </div>
                                <div className="grid flex-1 text-left text-sm leading-tight">
                                    <span className="truncate font-semibold tracking-tight text-[13px]">Aroha Technologies</span>
                                    <span className="truncate font-mono text-[9px] uppercase tracking-widest text-sidebar-foreground/40">Company Intel</span>
                                </div>
                            </Link>
                        </SidebarMenuButton>
                    </SidebarMenuItem>
                </SidebarMenu>
            </SidebarHeader>

            <SidebarContent>
                {/* Chat section */}
                <SidebarGroup className="px-3 py-2">
                    <SidebarGroupLabel className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/40 mb-1">
                        Platform
                    </SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            <Collapsible
                                defaultOpen={isChatSectionActive}
                                className="group/collapsible"
                            >
                                <SidebarMenuItem>
                                    <CollapsibleTrigger asChild>
                                        <SidebarMenuButton
                                            tooltip="Chat"
                                            className="rounded-md text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
                                        >
                                            <MessageSquare className="size-4" />
                                            <span className="text-[13px]">Chat</span>
                                            <ChevronRight className="ml-auto size-3.5 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                                        </SidebarMenuButton>
                                    </CollapsibleTrigger>
                                    <CollapsibleContent>
                                        <SidebarMenuSub>
                                            {visibleChatItems.map((item) => (
                                                <SidebarMenuSubItem key={item.url}>
                                                    <SidebarMenuSubButton
                                                        asChild
                                                        isActive={isActive(item.url)}
                                                        className="rounded-md text-[12px] data-[active=true]:bg-foreground data-[active=true]:text-background"
                                                    >
                                                        <Link href={item.url}>
                                                            <item.icon className="size-3.5" />
                                                            <span>{item.title}</span>
                                                        </Link>
                                                    </SidebarMenuSubButton>
                                                </SidebarMenuSubItem>
                                            ))}
                                        </SidebarMenuSub>
                                    </CollapsibleContent>
                                </SidebarMenuItem>
                            </Collapsible>
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>

                {/* Insights section */}
                {visibleInsightsItems.length > 0 && (
                    <SidebarGroup className="px-3 py-2">
                        <SidebarGroupContent>
                            <SidebarMenu>
                                <Collapsible
                                    defaultOpen={isInsightsSectionActive}
                                    className="group/collapsible"
                                >
                                    <SidebarMenuItem>
                                        <CollapsibleTrigger asChild>
                                            <SidebarMenuButton
                                                tooltip="Insights"
                                                className="rounded-md text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
                                            >
                                                <Sparkles className="size-4" />
                                                <span className="text-[13px]">Insights</span>
                                                <ChevronRight className="ml-auto size-3.5 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                                            </SidebarMenuButton>
                                        </CollapsibleTrigger>
                                        <CollapsibleContent>
                                            <SidebarMenuSub>
                                                {visibleInsightsItems.map((item) => (
                                                    <SidebarMenuSubItem key={item.url}>
                                                        <SidebarMenuSubButton
                                                            asChild
                                                            isActive={isActive(item.url)}
                                                            className="rounded-md text-[12px] data-[active=true]:bg-foreground data-[active=true]:text-background"
                                                        >
                                                            <Link href={item.url}>
                                                                <item.icon className="size-3.5" />
                                                                <span>{item.title}</span>
                                                            </Link>
                                                        </SidebarMenuSubButton>
                                                    </SidebarMenuSubItem>
                                                ))}
                                            </SidebarMenuSub>
                                        </CollapsibleContent>
                                    </SidebarMenuItem>
                                </Collapsible>
                            </SidebarMenu>
                        </SidebarGroupContent>
                    </SidebarGroup>
                )}

                {/* Management section */}
                <SidebarGroup className="px-3 py-2">
                    <SidebarGroupLabel className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/40 mb-1">
                        Management
                    </SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            {visibleItems.map((item) => (
                                <SidebarMenuItem key={item.url}>
                                    <SidebarMenuButton
                                        asChild
                                        isActive={isActive(item.url)}
                                        tooltip={item.title}
                                        className="rounded-md text-[13px] text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground data-[active=true]:bg-foreground data-[active=true]:text-background"
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
            </SidebarContent>

            <SidebarRail />
        </Sidebar>
    );
}
