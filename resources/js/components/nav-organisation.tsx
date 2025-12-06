import { OrganisationMenuContent } from '@/components/organisation-menu-content';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar';
import { useIsMobile } from '@/hooks/use-mobile';
import { type SharedData } from '@/types';
import { usePage } from '@inertiajs/react';
import { ChevronsUpDown } from 'lucide-react';

export function NavOrganisation() {
  const { organisations, currentOrganisation } = usePage<SharedData>().props;
  const { state } = useSidebar();
  const isMobile = useIsMobile();

  if (!organisations || organisations.length === 0) {
    return null;
  }

  const displayName = currentOrganisation?.name ?? 'Select Organisation';

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="group text-sidebar-accent-foreground data-[state=open]:bg-sidebar-accent"
              data-test="organisation-menu-button"
            >
              <div className="flex items-center gap-2">
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">
                    Current Org: {displayName}
                  </span>
                </div>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            align="end"
            side={
              isMobile ? 'bottom' : state === 'collapsed' ? 'left' : 'bottom'
            }
          >
            <OrganisationMenuContent
              organisations={organisations}
              currentOrganisation={currentOrganisation}
            />
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
