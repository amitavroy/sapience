<?php

namespace App\Actions;

use App\Models\Dataset;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Support\Arr;

class CreateDatasetAction
{
    /**
     * Create a new dataset.
     */
    public function execute(array $validated, Organisation $organisation, User $user): Dataset
    {
        return Dataset::create([
            'name' => Arr::get($validated, 'name'),
            'description' => Arr::get($validated, 'description'),
            'organisation_id' => $organisation->id,
            'owner_id' => $user->id,
            'is_active' => true,
        ]);
    }
}
