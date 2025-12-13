import { NavFooter } from '@/components/nav-footer';
import { NavMain } from '@/components/nav-main';
import { NavOrganisation } from '@/components/nav-organisation';
import { NavUser } from '@/components/nav-user';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from '@/components/ui/sidebar';
import { dashboard } from '@/routes';
import { index as conversationsIndex } from '@/routes/organisations/conversations';
import { index } from '@/routes/organisations/datasets';
import { type NavItem, type SharedData } from '@/types';
import { usePage } from '@inertiajs/react';
import {
  BookOpen,
  Database,
  Folder,
  LayoutGrid,
  MessageSquare,
} from 'lucide-react';

const footerNavItems: NavItem[] = [
  {
    title: 'Repository',
    href: 'https://github.com/laravel/react-starter-kit',
    icon: Folder,
  },
  {
    title: 'Documentation',
    href: 'https://laravel.com/docs/starter-kits#react',
    icon: BookOpen,
  },
];

export function AppSidebar() {
  const { currentOrganisation } = usePage<SharedData>().props;

  const mainNavItems: NavItem[] = [
    {
      title: 'Dashboard',
      href: dashboard(),
      icon: LayoutGrid,
    },
  ];

  if (currentOrganisation) {
    mainNavItems.push(
      {
        title: 'Datasets',
        href: index(currentOrganisation.uuid),
        icon: Database,
      },
      {
        title: 'Conversations',
        href: conversationsIndex(currentOrganisation.uuid),
        icon: MessageSquare,
      },
    );
  }

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader>
        <NavOrganisation />
      </SidebarHeader>

      <SidebarContent>
        <NavMain items={mainNavItems} />
      </SidebarContent>

      <SidebarFooter>
        <NavFooter items={footerNavItems} className="mt-auto" />
        <NavUser />
      </SidebarFooter>
    </Sidebar>
  );
}
