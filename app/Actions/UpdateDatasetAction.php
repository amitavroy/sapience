<?php

namespace App\Actions;

use App\Models\Dataset;
use Illuminate\Support\Arr;

class UpdateDatasetAction
{
    /**
     * Update a dataset.
     */
    public function execute(array $validated, Dataset $dataset): Dataset
    {
        $dataset->update([
            'name' => Arr::get($validated, 'name'),
            'description' => Arr::get($validated, 'description'),
            'instructions' => Arr::get($validated, 'instructions'),
            'output_instructions' => Arr::get($validated, 'output_instructions'),
        ]);

        return $dataset->fresh();
    }
}
