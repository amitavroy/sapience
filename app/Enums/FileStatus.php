<?php

namespace App\Enums;

enum FileStatus: string
{
    case Pending = 'pending';
    case Completed = 'completed';
    case Invalid = 'invalid';
    case Processing = 'processing';
    case Failed = 'failed';
}
