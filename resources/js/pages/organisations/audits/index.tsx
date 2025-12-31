import AuditsTable from '@/components/audits-table';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes/organisations';
import {
  index as auditsIndex,
  create as createAudit,
} from '@/routes/organisations/audits/index';
import {
  type Audit,
  type BreadcrumbItem,
  type Organisation,
  type PaginatedData,
} from '@/types';
import { Head, Link } from '@inertiajs/react';

interface IndexProps {
  organisation: Organisation;
  audits: PaginatedData<Audit>;
}

export default function AuditsIndex({ organisation, audits }: IndexProps) {
  const breadcrumbs: BreadcrumbItem[] = [
    {
      title: 'Organisations',
      href: dashboard(organisation.uuid).url,
    },
    {
      title: organisation.name,
      href: dashboard(organisation.uuid).url,
    },
    {
      title: 'Audits',
      href: auditsIndex.url({ organisation: organisation.uuid }),
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`Audits - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Audits</h1>
            <p className="text-muted-foreground">
              Manage audits for {organisation.name}
            </p>
          </div>
          <Link href={createAudit(organisation.uuid).url}>
            <Button>Create Audit</Button>
          </Link>
        </div>

        <AuditsTable audits={audits} />
      </div>
    </AppLayout>
  );
}
