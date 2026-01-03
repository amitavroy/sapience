import { ResearchFeedbackForm } from '@/components/research-feedback-form';
import { type Organisation, type Research } from '@/types';

interface ResearchInterruptionUIProps {
  organisation: Organisation;
  research: Research;
  isOwner: boolean;
  onResumeSuccess?: () => void;
}

export function ResearchInterruptionUI({
  organisation,
  research,
  isOwner,
  onResumeSuccess,
}: ResearchInterruptionUIProps) {
  if (
    research.status !== 'awaiting_feedback' ||
    !research.interruption_data
  ) {
    return null;
  }

  return (
    <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
      <div className="mb-6">
        <h2 className="mb-2 text-xl font-semibold">
          Context Clarification Needed
        </h2>
        <p className="text-muted-foreground">
          {research.interruption_data.question ||
            'Please review the generated search terms and provide any additional context or clarification to improve the search results.'}
        </p>
      </div>

      <div className="mb-6">
        <h3 className="mb-3 text-lg font-medium">Generated Search Terms</h3>
        <div className="flex flex-wrap gap-2">
          {research.interruption_data.search_terms?.map(
            (term: string, index: number) => (
              <span
                key={index}
                className="rounded-md bg-secondary px-3 py-1 text-sm"
              >
                {term}
              </span>
            ),
          )}
        </div>
      </div>

      {isOwner && (
        <ResearchFeedbackForm
          organisation={organisation}
          research={research}
          onSuccess={onResumeSuccess}
        />
      )}
    </div>
  );
}

