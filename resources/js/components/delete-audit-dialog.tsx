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
import {
  index as auditsIndex,
  destroy as destroyAudit,
} from '@/routes/organisations/audits/index';
import { type Audit, type Organisation } from '@/types';
import { router } from '@inertiajs/react';
import { Trash2 } from 'lucide-react';
import { useState } from 'react';

interface DeleteAuditDialogProps {
  organisation: Organisation;
  audit: Audit;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteAuditDialog({
  organisation,
  audit,
  open,
  onOpenChange,
}: DeleteAuditDialogProps) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = () => {
    setDeleting(true);
    router.delete(
      destroyAudit.url({
        organisation: organisation.uuid,
        audit: { id: audit.id },
      }),
      {
        preserveScroll: false,
        onSuccess: () => {
          router.visit(auditsIndex.url({ organisation: organisation.uuid }));
        },
        onError: () => {
          alert('Failed to delete audit. Please try again.');
          setDeleting(false);
        },
        onFinish: () => {
          setDeleting(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="destructive">
          <Trash2 className="mr-2 size-4" />
          Delete Audit
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Delete Audit</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete the audit for "{audit.website_url}"?
          <span className="mt-2 block">
            This will permanently delete the audit and all its related data.
            This action cannot be undone.
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
  );
}
