import { MarkdownContent } from '@/components/markdown-content';

interface ResearchReportProps {
  report: string;
  showContainer?: boolean;
}

export function ResearchReport({
  report,
  showContainer = true,
}: ResearchReportProps) {
  const content = (
    <>
      {showContainer && <h2 className="mb-4 text-lg font-semibold">Report</h2>}
      <MarkdownContent content={report} />
    </>
  );

  if (!showContainer) {
    return <>{content}</>;
  }

  return (
    <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
      {content}
    </div>
  );
}
