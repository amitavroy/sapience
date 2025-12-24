import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { store, update } from '@/routes/organisations/research';
import { type Organisation, type Research } from '@/types';
import { Form } from '@inertiajs/react';

interface ResearchFormProps {
  type: 'create' | 'edit';
  organisation: Organisation;
  research?: Research;
}

export default function ResearchForm({
  type,
  organisation,
  research,
}: ResearchFormProps) {
  const action =
    type === 'create'
      ? store(organisation.uuid)
      : update({
          organisation: organisation.uuid,
          research: research!.uuid,
        });

  const submitLabel = type === 'create' ? 'Create Research' : 'Update Research';

  return (
    <Form action={action} className="flex flex-col gap-6">
      {({ processing, errors }) => (
        <>
          <div className="grid gap-6">
            <div className="grid gap-2">
              <Label htmlFor="query">Query</Label>
              <Input
                id="query"
                type="text"
                name="query"
                required
                autoFocus
                defaultValue={research?.query || ''}
                placeholder="Enter research query"
              />
              <InputError message={errors.query} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <textarea
                id="description"
                name="description"
                rows={4}
                defaultValue={research?.description || ''}
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="Enter research description (optional)"
              />
              <InputError message={errors.description} />
            </div>

            <Button type="submit" className="mt-2 w-full" disabled={processing}>
              {processing && <Spinner />}
              {submitLabel}
            </Button>
          </div>
        </>
      )}
    </Form>
  );
}
