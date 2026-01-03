import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { start as startResearch } from '@/routes/organisations/research';
import { type Organisation, type Research } from '@/types';
import { Form } from '@inertiajs/react';
import { useState } from 'react';

interface ResearchFeedbackFormProps {
  organisation: Organisation;
  research: Research;
  onSuccess?: () => void;
}

export function ResearchFeedbackForm({
  organisation,
  research,
  onSuccess,
}: ResearchFeedbackFormProps) {
  const [additionalContext, setAdditionalContext] = useState('');

  if (!research.interruption_data) {
    return null;
  }

  return (
    <Form
      action={
        startResearch({
          organisation: organisation.uuid,
          research: research.uuid,
        }).url
      }
      method="post"
      onSuccess={() => {
        onSuccess?.();
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
              Add any additional information that might help improve the search
              results.
            </p>
          </div>

          <Button type="submit" disabled={processing}>
            {processing ? 'Resuming...' : 'Resume Research'}
          </Button>
        </div>
      )}
    </Form>
  );
}

