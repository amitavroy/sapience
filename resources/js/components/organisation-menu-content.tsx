import {
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { useMobileNavigation } from '@/hooks/use-mobile-navigation';
import { join } from '@/routes/organisations';
import { store as selectStore } from '@/routes/organisations/select';
import { type Organisation } from '@/types';
import { Link, router } from '@inertiajs/react';
import { Plus } from 'lucide-react';

interface OrganisationMenuContentProps {
    organisations: Organisation[];
    currentOrganisation: Organisation | null;
}

export function OrganisationMenuContent({
    organisations,
    currentOrganisation,
}: OrganisationMenuContentProps) {
    const cleanup = useMobileNavigation();

    const handleSelectOrganisation = (organisationId: number) => {
        router.post(selectStore().url, {
            organisation_id: organisationId,
        });
    };

    return (
        <>
            {currentOrganisation && (
                <>
                    <DropdownMenuLabel className="p-0 font-normal">
                        <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                            <span className="truncate font-medium">
                                {currentOrganisation.name}
                            </span>
                        </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                </>
            )}
            <DropdownMenuGroup>
                {organisations.map((organisation) => (
                    <DropdownMenuItem
                        key={organisation.id}
                        asChild
                        className={
                            currentOrganisation?.id === organisation.id
                                ? 'bg-sidebar-accent'
                                : ''
                        }
                    >
                        <button
                            type="button"
                            className="block w-full text-left"
                            onClick={() => {
                                if (
                                    currentOrganisation?.id !== organisation.id
                                ) {
                                    handleSelectOrganisation(organisation.id);
                                }
                                cleanup();
                            }}
                        >
                            {organisation.name}
                        </button>
                    </DropdownMenuItem>
                ))}
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
                <Link
                    className="block w-full"
                    href={join().url}
                    onClick={cleanup}
                >
                    <Plus className="mr-2" />
                    Join an organisation
                </Link>
            </DropdownMenuItem>
        </>
    );
}
