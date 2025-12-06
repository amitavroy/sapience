<?php

namespace App\Queries;

use App\Models\Organisation;
use Illuminate\Database\Eloquent\Relations\HasMany;

class GetOrganisationDatasetsQuery
{
    /**
     * Get the query builder for datasets of an organisation with eager loading.
     */
    public function execute(Organisation $organisation): HasMany
    {
        return $organisation->datasets()
            ->withCount('files')
            ->with('owner')
            ->latest();
    }
}
