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
      case 'failed':
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  return (
    <Badge variant={getStatusBadgeVariant(status)} className={className}>
      {status}
    </Badge>
  );
}
