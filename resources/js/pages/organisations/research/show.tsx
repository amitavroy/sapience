import { ResearchStatusBadge } from '@/components/research-status-badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import AppLayout from '@/layouts/app-layout';
import { formatRelativeTime } from '@/lib/utils';
import { dashboard } from '@/routes/organisations';
import {
  destroy as destroyResearch,
  edit as editResearch,
  index as researchIndex,
} from '@/routes/organisations/research';
import { type BreadcrumbItem, type Organisation, type Research } from '@/types';
import { Head, Link, router } from '@inertiajs/react';
import { Edit, Trash2 } from 'lucide-react';
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
  const [deleting, setDeleting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleDelete = () => {
    setDeleting(true);
    router.delete(
      destroyResearch.url({
        organisation: organisation.uuid,
        research: research.uuid,
      }),
      {
        preserveScroll: false,
        onSuccess: () => {
          router.visit(researchIndex.url({ organisation: organisation.uuid }));
        },
        onError: () => {
          alert('Failed to delete research. Please try again.');
          setDeleting(false);
        },
        onFinish: () => {
          setDeleting(false);
        },
      },
    );
  };

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
              <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="destructive">
                    <Trash2 className="mr-2 size-4" />
                    Delete Research
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogTitle>Delete Research</DialogTitle>
                  <DialogDescription>
                    Are you sure you want to delete "{research.query}"?
                    <span className="mt-2 block">
                      This will permanently delete the research and all its
                      related data. This action cannot be undone.
                    </span>
                  </DialogDescription>
                  <DialogFooter className="gap-2">
                    <DialogClose asChild>
                      <Button variant="secondary">Cancel</Button>
                    </DialogClose>
                    <Button
                      variant="destructive"
                      onClick={handleDelete}
                      disabled={deleting}
                    >
                      {deleting ? (
                        <>
                          <Spinner />
                          Deleting...
                        </>
                      ) : (
                        'Delete'
                      )}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          )}
        </div>

        {research.report && (
          <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
            <h2 className="mb-4 text-lg font-semibold">Report</h2>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <pre className="font-sans whitespace-pre-wrap">
                {research.report}
              </pre>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
