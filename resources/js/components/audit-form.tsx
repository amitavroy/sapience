import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { store } from '@/routes/organisations/audits/index';
import { type Audit, type Organisation } from '@/types';
import { Form } from '@inertiajs/react';

interface AuditFormProps {
  organisation: Organisation;
  audit?: Audit;
}

export default function AuditForm({ organisation, audit }: AuditFormProps) {
  const action = store(organisation.uuid);

  const submitLabel = 'Create Audit';

  return (
    <Form action={action} className="flex flex-col gap-6">
      {({ processing, errors }) => (
        <>
          <div className="grid gap-6">
            <div className="grid gap-2">
              <Label htmlFor="website_url">Website URL</Label>
              <Input
                id="website_url"
                type="url"
                name="website_url"
                required
                autoFocus
                defaultValue={audit?.website_url || ''}
                placeholder="https://example.com"
              />
              <InputError message={errors.website_url} />
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
