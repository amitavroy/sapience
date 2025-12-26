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
import { formatRelativeTime } from '@/lib/utils';
import {
  destroy as destroyResearch,
  edit as editResearch,
  show as showResearch,
} from '@/routes/organisations/research';
import { type Organisation, type Research, type User } from '@/types';
import { Link, router } from '@inertiajs/react';
import { Edit, Trash2 } from 'lucide-react';
import { useState } from 'react';

interface ResearchCardProps {
  research: Research;
  organisation: Organisation;
  currentUser: User;
  onDelete?: () => void;
}

export function ResearchCard({
  research,
  organisation,
  currentUser,
  onDelete,
}: ResearchCardProps) {
  const [deleting, setDeleting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const isOwner = research.user.id === currentUser.id;

  const handleDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    setDeleting(true);
    router.delete(
      destroyResearch.url({
        organisation: organisation.uuid,
        research: research.uuid,
      }),
      {
        preserveScroll: true,
        onSuccess: () => {
          setDialogOpen(false);
          if (onDelete) {
            onDelete();
          }
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

  const researchUrl = showResearch({
    organisation: organisation.uuid,
    research: research.uuid,
  }).url;

  return (
    <div className="group relative flex items-center justify-between px-4 py-3 transition-colors hover:bg-accent">
      <Link href={researchUrl} className="flex-1">
        <div className="flex flex-col">
          <div className="mb-1 flex items-center gap-2">
            <h3 className="font-semibold text-foreground group-hover:text-primary">
              {research.query}
            </h3>
            <ResearchStatusBadge status={research.status} className="text-xs" />
          </div>
          {research.instructions && (
            <div className="mb-1 text-sm text-muted-foreground">
              {research.instructions}
            </div>
          )}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>Created by {research.user.name}</span>
            <span>•</span>
            <span>{formatRelativeTime(research.created_at)}</span>
          </div>
        </div>
      </Link>
      {isOwner && (
        <div
          className="ml-4 flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          <Link
            href={
              editResearch({
                organisation: organisation.uuid,
                research: research.uuid,
              }).url
            }
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              variant="ghost"
              size="icon"
              className="size-8 text-muted-foreground hover:text-primary"
            >
              <Edit className="size-4" />
            </Button>
          </Link>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-muted-foreground hover:text-destructive"
                disabled={deleting}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                {deleting ? <Spinner /> : <Trash2 className="size-4" />}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogTitle>Delete Research</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete "{research.query}"?
                <span className="mt-2 block">
                  This will permanently delete the research and all its related
                  data. This action cannot be undone.
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
  );
}
