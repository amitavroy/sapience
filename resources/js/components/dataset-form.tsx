import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { store, update } from '@/routes/organisations/datasets';
import { type Dataset, type Organisation } from '@/types';
import { Form } from '@inertiajs/react';

interface DatasetFormProps {
  type: 'create' | 'edit';
  organisation: Organisation;
  dataset?: Dataset;
}

export default function DatasetForm({
  type,
  organisation,
  dataset,
}: DatasetFormProps) {
  const action =
    type === 'create'
      ? store(organisation.uuid)
      : update({
          organisation: organisation.uuid,
          dataset: dataset!.uuid,
        });

  const submitLabel = type === 'create' ? 'Create Dataset' : 'Update Dataset';

  const textareaClassName =
    'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50';

  return (
    <Form action={action} className="flex flex-col gap-6">
      {({ processing, errors }) => (
        <>
          <div className="grid gap-6">
            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                type="text"
                name="name"
                required
                autoFocus
                defaultValue={dataset?.name || ''}
                placeholder="Enter dataset name"
              />
              <InputError message={errors.name} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <textarea
                id="description"
                name="description"
                rows={4}
                defaultValue={dataset?.description || ''}
                className={textareaClassName}
                placeholder="Enter dataset description (optional)"
              />
              <InputError message={errors.description} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="instructions">Background</Label>
              <textarea
                id="instructions"
                name="instructions"
                rows={6}
                defaultValue={dataset?.instructions || ''}
                className={textareaClassName}
                placeholder="Enter background (optional)"
              />
              <InputError message={errors.instructions} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="steps">Steps</Label>
              <textarea
                id="steps"
                name="steps"
                rows={6}
                defaultValue={dataset?.steps || ''}
                className={textareaClassName}
                placeholder="Enter steps (optional)"
              />
              <InputError message={errors.steps} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="output_instructions">Output</Label>
              <textarea
                id="output_instructions"
                name="output_instructions"
                rows={6}
                defaultValue={dataset?.output_instructions || ''}
                className={textareaClassName}
                placeholder="Enter output (optional)"
              />
              <InputError message={errors.output_instructions} />
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
