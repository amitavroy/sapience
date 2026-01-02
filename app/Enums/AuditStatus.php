<?php

namespace App\Enums;

enum AuditStatus: string
{
    case Pending = 'pending';
    case InProgress = 'in_progress';
    case Summarised = 'summarised';
    case Completed = 'completed';
    case Failed = 'failed';
}
