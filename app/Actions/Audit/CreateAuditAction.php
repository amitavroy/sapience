<?php

namespace App\Actions\Audit;

use App\Models\Audit;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Support\Arr;

class CreateAuditAction
{
    /**
     * Create a new audit.
     */
    public function execute(array $validated, Organisation $organisation, User $user): Audit
    {
        return Audit::create([
            'website_url' => Arr::get($validated, 'website_url'),
            'organisation_id' => $organisation->id,
            'user_id' => $user->id,
            'status' => 'pending',
        ]);
    }
}
