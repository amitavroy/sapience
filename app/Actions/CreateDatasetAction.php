<?php

namespace App\Actions;

use App\Models\Dataset;
use App\Models\Organisation;
use App\Models\User;
use App\Services\TypesenseService;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;

class CreateDatasetAction
{
    public function __construct(
        private TypesenseService $typesenseService
    ) {}

    /**
     * Create a new dataset.
     */
    public function execute(array $validated, Organisation $organisation, User $user): Dataset
    {
        return DB::transaction(function () use ($validated, $organisation, $user) {
            $dataset = Dataset::create([
                'name' => Arr::get($validated, 'name'),
                'description' => Arr::get($validated, 'description'),
                'organisation_id' => $organisation->id,
                'owner_id' => $user->id,
                'is_active' => true,
            ]);

            $this->typesenseService
                ->createCollection(
                    organisationId: $organisation->id,
                    datasetId: $dataset->id
                );

            return $dataset;
        });
    }
}
