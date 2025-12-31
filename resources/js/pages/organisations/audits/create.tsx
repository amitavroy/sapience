import AuditForm from '@/components/audit-form';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes/organisations';
import { index as auditsIndex } from '@/routes/organisations/audits/index';
import { type Audit, type BreadcrumbItem, type Organisation } from '@/types';
import { Head } from '@inertiajs/react';

interface CreateProps {
  organisation: Organisation;
  audit: Audit;
}

export default function AuditsCreate({ organisation, audit }: CreateProps) {
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
    {
      title: 'Create',
      href: '#',
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`Create Audit - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
        <div className="mb-4">
          <h1 className="text-2xl font-bold">Create Audit</h1>
          <p className="text-muted-foreground">
            Create a new audit for {organisation.name}
          </p>
        </div>

        <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
          <AuditForm organisation={organisation} audit={audit} />
        </div>
      </div>
    </AppLayout>
  );
}
