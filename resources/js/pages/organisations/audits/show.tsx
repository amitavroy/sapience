import { AuditLinks } from '@/components/audit-links';
import { AuditStatusBadge } from '@/components/audit-status-badge';
import { DeleteAuditDialog } from '@/components/delete-audit-dialog';
import { MarkdownContent } from '@/components/markdown-content';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import AppLayout from '@/layouts/app-layout';
import { formatRelativeTime } from '@/lib/utils';
import { dashboard } from '@/routes/organisations';
import {
  index as auditsIndex,
  show as showAudit,
  start as startAudit,
} from '@/routes/organisations/audits/index';
import { type Audit, type BreadcrumbItem, type Organisation } from '@/types';
import { Form, Head } from '@inertiajs/react';
import { Play } from 'lucide-react';
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
              {audit.status === 'pending' && (
                <Form
                  action={
                    startAudit({
                      organisation: organisation.uuid,
                      audit: { id: audit.id },
                    }).url
                  }
                  method="post"
                >
                  {({ processing }) => (
                    <Button type="submit" disabled={processing}>
                      <Play className="mr-2 size-4" />
                      {processing ? 'Starting...' : 'Start Research'}
                    </Button>
                  )}
                </Form>
              )}
              <DeleteAuditDialog
                organisation={organisation}
                audit={audit}
                open={dialogOpen}
                onOpenChange={setDialogOpen}
              />
            </div>
          )}
        </div>

        {audit.status === 'completed' && audit.report ? (
          <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
            <Tabs defaultValue="analysis">
              <TabsList>
                <TabsTrigger value="analysis">Analysis</TabsTrigger>
                <TabsTrigger value="report">Final Report</TabsTrigger>
                <TabsTrigger value="links">Audit Links</TabsTrigger>
              </TabsList>
              <TabsContent value="analysis" className="mt-4">
                {audit.analysis ? (
                  <div className="overflow-x-auto">
                    <MarkdownContent content={audit.analysis} />
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    No analysis available yet.
                  </p>
                )}
              </TabsContent>
              <TabsContent value="report" className="mt-4">
                <div className="overflow-x-auto">
                  <MarkdownContent content={audit.report} />
                </div>
              </TabsContent>
              <TabsContent value="links" className="mt-4">
                <AuditLinks auditLinks={audit.audit_links || []} />
              </TabsContent>
            </Tabs>
          </div>
        ) : (
          <>
            {audit.status === 'summarised' && audit.analysis && (
              <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
                <h2 className="mb-4 text-lg font-semibold">Analysis</h2>
                <MarkdownContent content={audit.analysis} />
              </div>
            )}

            {audit.report && audit.status !== 'completed' && (
              <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
                <h2 className="mb-4 text-lg font-semibold">Report</h2>
                <MarkdownContent content={audit.report} />
              </div>
            )}

            {!audit.report &&
              audit.status !== 'summarised' &&
              audit.status !== 'completed' && (
                <div className="rounded-xl border border-sidebar-border/70 p-8 text-center dark:border-sidebar-border">
                  <p className="text-muted-foreground">
                    No report available yet. The audit is still {audit.status}.
                  </p>
                </div>
              )}

            {audit.audit_links && audit.audit_links.length > 0 && (
              <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
                <h2 className="mb-4 text-lg font-semibold">Audit Links</h2>
                <AuditLinks auditLinks={audit.audit_links} />
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
}
