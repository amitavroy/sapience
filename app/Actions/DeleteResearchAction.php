<?php

namespace App\Actions;

use App\Models\Research;
use Illuminate\Support\Facades\DB;

class DeleteResearchAction
{
    /**
     * Delete a research and its related links.
     */
    public function execute(Research $research): void
    {
        DB::transaction(function () use ($research) {
            // Delete related research links
            $research->researchLinks()->delete();

            // Delete the research record
            $research->delete();
        });
    }
}
