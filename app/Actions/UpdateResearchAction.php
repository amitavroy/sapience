<?php

namespace App\Actions;

use App\Models\Research;
use Illuminate\Support\Arr;

class UpdateResearchAction
{
    /**
     * Update a research.
     */
    public function execute(array $validated, Research $research): Research
    {
        $research->update([
            'query' => Arr::get($validated, 'query'),
            'instructions' => Arr::get($validated, 'instructions'),
        ]);

        return $research->fresh();
    }
}
