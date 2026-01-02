import { DeleteResearchDialog } from '@/components/delete-research-dialog';
import { ResearchLinksList } from '@/components/research-links-list';
import { ResearchReport } from '@/components/research-report';
import { ResearchStatusBadge } from '@/components/research-status-badge';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import AppLayout from '@/layouts/app-layout';
import { formatRelativeTime } from '@/lib/utils';
import { dashboard } from '@/routes/organisations';
import {
  edit as editResearch,
  index as researchIndex,
  start as startResearch,
} from '@/routes/organisations/research';
import { type BreadcrumbItem, type Organisation, type Research } from '@/types';
import { Form, Head, Link, usePoll } from '@inertiajs/react';
import { Edit, Play } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

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
  const [additionalContext, setAdditionalContext] = useState('');

  // Poll for status updates when research is active (has workflow_id) or processing/awaiting feedback
  // This ensures polling starts immediately after research begins, even if status hasn't updated yet
  const shouldPoll =
    research.workflow_id !== null ||
    research.status === 'processing' ||
    research.status === 'awaiting_feedback';

  // Use 1.5 second interval for faster updates while not being too aggressive
  const { start, stop } = usePoll(1500, {}, { autoStart: false });

  useEffect(() => {
    if (shouldPoll) {
      start();
    } else {
      stop();
    }

    return () => {
      stop();
    };
  }, [shouldPoll, start, stop]);

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
            {research.instructions && (
              <p className="mb-2 text-muted-foreground">
                {research.instructions}
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
              {research.status === 'pending' && (
                <Form
                  action={
                    startResearch({
                      organisation: organisation.uuid,
                      research: research.uuid,
                    }).url
                  }
                  method="post"
                  onSuccess={() => {
                    // Start polling immediately after form submission
                    start();
                  }}
                >
                  {({ processing }) => (
                    <Button type="submit" disabled={processing}>
                      <Play className="mr-2 size-4" />
                      {processing ? 'Starting...' : 'Start Research'}
                    </Button>
                  )}
                </Form>
              )}
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

        {research.status === 'processing' && (!research.research_links || research.research_links.length === 0) ? (
          <div className="rounded-xl border border-sidebar-border/70 p-12 dark:border-sidebar-border">
            <div className="flex flex-col items-center justify-center gap-4 text-center">
              <Spinner className="size-8 text-primary" />
              <div className="space-y-2">
                <h2 className="text-xl font-semibold">Processing Research</h2>
                <p className="text-muted-foreground max-w-md">
                  {research.interruption_data?.user_feedback
                    ? 'We\'re processing your feedback and continuing the research. This may take a few moments...'
                    : 'We\'re analyzing your query and generating search terms. This may take a few moments...'}
                </p>
              </div>
            </div>
          </div>
        ) : research.status === 'awaiting_feedback' && research.interruption_data ? (
          <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
            <div className="mb-6">
              <h2 className="mb-2 text-xl font-semibold">Context Clarification Needed</h2>
              <p className="text-muted-foreground">
                {research.interruption_data.question || 'Please review the generated search terms and provide any additional context or clarification to improve the search results.'}
              </p>
            </div>

            <div className="mb-6">
              <h3 className="mb-3 text-lg font-medium">Generated Search Terms</h3>
              <div className="flex flex-wrap gap-2">
                {research.interruption_data.search_terms?.map((term: string, index: number) => (
                  <span
                    key={index}
                    className="rounded-md bg-secondary px-3 py-1 text-sm"
                  >
                    {term}
                  </span>
                ))}
              </div>
            </div>

            {isOwner && (
              <Form
                action={
                  startResearch({
                    organisation: organisation.uuid,
                    research: research.uuid,
                  }).url
                }
                method="post"
                onSuccess={() => {
                  // Ensure polling continues after resuming
                  start();
                }}
              >
                {({ processing }) => (
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="additional_context">
                        Additional Context (Optional)
                      </Label>
                      <Input
                        id="additional_context"
                        name="additional_context"
                        type="text"
                        value={additionalContext}
                        onChange={(e) => setAdditionalContext(e.target.value)}
                        placeholder="Provide any additional context or clarification..."
                        className="mt-2"
                        disabled={processing}
                      />
                      <p className="mt-1 text-sm text-muted-foreground">
                        Add any additional information that might help improve the search results.
                      </p>
                    </div>

                    <Button type="submit" disabled={processing}>
                      {processing ? 'Resuming...' : 'Resume Research'}
                    </Button>
                  </div>
                )}
              </Form>
            )}
          </div>
        ) : research.status === 'completed' && research.report ? (
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
                  isProcessing={research.status === 'processing'}
                />
              </TabsContent>
            </Tabs>
          </div>
        ) : (
          <ResearchLinksList
            links={research.research_links || []}
            isProcessing={research.status === 'processing'}
          />
        )}
      </div>
    </AppLayout>
  );
}
