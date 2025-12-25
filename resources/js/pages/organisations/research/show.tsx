import { DeleteResearchDialog } from '@/components/delete-research-dialog';
import { ResearchLinksList } from '@/components/research-links-list';
import { ResearchReport } from '@/components/research-report';
import { ResearchStatusBadge } from '@/components/research-status-badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import AppLayout from '@/layouts/app-layout';
import { formatRelativeTime } from '@/lib/utils';
import { dashboard } from '@/routes/organisations';
import {
  edit as editResearch,
  index as researchIndex,
} from '@/routes/organisations/research';
import { type BreadcrumbItem, type Organisation, type Research } from '@/types';
import { Head, Link } from '@inertiajs/react';
import { Edit } from 'lucide-react';
import { useState } from 'react';

interface ShowProps {
  organisation: Organisation;
  research: Research;
  isOwner: boolean;
}

export default function ResearchShow({
  organisation,
  research,
  isOwner,
}: ShowProps) {
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
      title: 'Research',
      href: researchIndex.url({ organisation: organisation.uuid }),
    },
    {
      title: research.query,
      href: '#',
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`${research.query} - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex-1">
            <div className="mb-2 flex items-center gap-3">
              <h1 className="text-2xl font-bold">{research.query}</h1>
              <ResearchStatusBadge status={research.status} />
            </div>
            {research.description && (
              <p className="mb-2 text-muted-foreground">
                {research.description}
              </p>
            )}
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>Created by {research.user.name}</span>
              <span>•</span>
              <span>Created {formatRelativeTime(research.created_at)}</span>
              {research.updated_at &&
                research.updated_at !== research.created_at && (
                  <>
                    <span>•</span>
                    <span>
                      Updated {formatRelativeTime(research.updated_at)}
                    </span>
                  </>
                )}
            </div>
          </div>
          {isOwner && (
            <div className="flex gap-2">
              <Link
                href={
                  editResearch({
                    organisation: organisation.uuid,
                    research: research.uuid,
                  }).url
                }
              >
                <Button variant="outline">
                  <Edit className="mr-2 size-4" />
                  Edit Research
                </Button>
              </Link>
              <DeleteResearchDialog
                organisation={organisation}
                research={research}
                open={dialogOpen}
                onOpenChange={setDialogOpen}
              />
            </div>
          )}
        </div>

        {research.status === 'completed' && research.report ? (
          <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
            <Tabs defaultValue="report">
              <TabsList>
                <TabsTrigger value="report">Report</TabsTrigger>
                <TabsTrigger value="links">Links</TabsTrigger>
              </TabsList>
              <TabsContent value="report" className="mt-4">
                <ResearchReport
                  report={research.report}
                  showContainer={false}
                />
              </TabsContent>
              <TabsContent value="links" className="mt-4">
                <ResearchLinksList
                  links={research.research_links || []}
                  showContainer={false}
                />
              </TabsContent>
            </Tabs>
          </div>
        ) : (
          <ResearchLinksList links={research.research_links || []} />
        )}
      </div>
    </AppLayout>
  );
}
