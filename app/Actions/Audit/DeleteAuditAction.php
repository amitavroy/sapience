<?php

namespace App\Actions\Audit;

use App\Models\Audit;

class DeleteAuditAction
{
    /**
     * Delete an audit.
     */
    public function execute(Audit $audit): void
    {
        $audit->delete();
    }
}
