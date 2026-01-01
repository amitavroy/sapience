import { Badge } from '@/components/ui/badge';

interface AuditStatusBadgeProps {
  status: 'pending' | 'in_progress' | 'summarised' | 'completed' | 'failed';
  className?: string;
}

export function AuditStatusBadge({ status, className }: AuditStatusBadgeProps) {
  const getStatusBadgeVariant = (
    status: 'pending' | 'in_progress' | 'summarised' | 'completed' | 'failed',
  ) => {
    switch (status) {
      case 'completed':
        return 'default';
      case 'pending':
        return 'secondary';
      case 'in_progress':
        return 'default';
      case 'summarised':
        return 'default';
      case 'failed':
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  const getStatusLabel = (
    status: 'pending' | 'in_progress' | 'summarised' | 'completed' | 'failed',
  ) => {
    switch (status) {
      case 'in_progress':
        return 'In Progress';
      case 'summarised':
        return 'Summarised';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      case 'pending':
      default:
        return 'Pending';
    }
  };

  return (
    <Badge variant={getStatusBadgeVariant(status)} className={className}>
      {getStatusLabel(status)}
    </Badge>
  );
}
