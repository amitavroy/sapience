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
  destroy as destroyResearch,
  index as researchIndex,
} from '@/routes/organisations/research';
import { type Organisation, type Research } from '@/types';
import { router } from '@inertiajs/react';
import { Trash2 } from 'lucide-react';
import { useState } from 'react';

interface DeleteResearchDialogProps {
  organisation: Organisation;
  research: Research;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteResearchDialog({
  organisation,
  research,
  open,
  onOpenChange,
}: DeleteResearchDialogProps) {
  const [deleting, setDeleting] = useState(false);

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
            This will permanently delete the research and all its related data.
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
