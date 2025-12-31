import { AuditStatusBadge } from '@/components/audit-status-badge';
import { DeleteAuditDialog } from '@/components/delete-audit-dialog';
import AppLayout from '@/layouts/app-layout';
import { formatRelativeTime } from '@/lib/utils';
import { dashboard } from '@/routes/organisations';
import {
  index as auditsIndex,
  show as showAudit,
} from '@/routes/organisations/audits/index';
import { type Audit, type BreadcrumbItem, type Organisation } from '@/types';
import { Head } from '@inertiajs/react';
import { useState } from 'react';

interface ShowProps {
  organisation: Organisation;
  audit: Audit;
  isOwner: boolean;
}

export default function AuditShow({ organisation, audit, isOwner }: ShowProps) {
  const [dialogOpen, setDialogOpen] = useState(false);

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
      title: audit.website_url,
      href: showAudit.url({
        organisation: organisation.uuid,
        audit: { id: audit.id },
      }),
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`${audit.website_url} - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex-1">
            <div className="mb-2 flex items-center gap-3">
              <h1 className="text-2xl font-bold">
                <a
                  href={audit.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  {audit.website_url}
                </a>
              </h1>
              <AuditStatusBadge status={audit.status} />
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>Created by {audit.user?.name || 'N/A'}</span>
              <span>•</span>
              <span>Created {formatRelativeTime(audit.created_at)}</span>
              {audit.updated_at && audit.updated_at !== audit.created_at && (
                <>
                  <span>•</span>
                  <span>Updated {formatRelativeTime(audit.updated_at)}</span>
                </>
              )}
            </div>
          </div>
          {isOwner && (
            <div className="flex gap-2">
              <DeleteAuditDialog
                organisation={organisation}
                audit={audit}
                open={dialogOpen}
                onOpenChange={setDialogOpen}
              />
            </div>
          )}
        </div>

        {audit.report && (
          <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
            <h2 className="mb-4 text-lg font-semibold">Report</h2>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <pre className="font-sans text-sm break-words whitespace-pre-wrap">
                {audit.report}
              </pre>
            </div>
          </div>
        )}

        {!audit.report && (
          <div className="rounded-xl border border-sidebar-border/70 p-8 text-center dark:border-sidebar-border">
            <p className="text-muted-foreground">
              No report available yet. The audit is still {audit.status}.
            </p>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
