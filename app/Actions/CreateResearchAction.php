<?php

namespace App\Actions;

use App\Models\Organisation;
use App\Models\Research;
use App\Models\User;
use Illuminate\Support\Arr;

class CreateResearchAction
{
    /**
     * Create a new research.
     */
    public function execute(array $validated, Organisation $organisation, User $user): Research
    {
        return Research::create([
            'query' => Arr::get($validated, 'query'),
            'description' => Arr::get($validated, 'description'),
            'organisation_id' => $organisation->id,
            'user_id' => $user->id,
            'status' => 'pending',
        ]);
    }
}
