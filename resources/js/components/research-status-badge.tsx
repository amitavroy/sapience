import { Badge } from '@/components/ui/badge';

interface ResearchStatusBadgeProps {
  status: string;
  className?: string;
}

export function ResearchStatusBadge({
  status,
  className,
}: ResearchStatusBadgeProps) {
  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'completed':
        return 'default';
      case 'pending':
        return 'secondary';
      case 'processing':
        return 'default';
      case 'awaiting_feedback':
        return 'default';
      case 'failed':
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'awaiting_feedback':
        return 'Awaiting Feedback';
      default:
        return status;
    }
  };

  return (
    <Badge variant={getStatusBadgeVariant(status)} className={className}>
      {getStatusLabel(status)}
    </Badge>
  );
}
