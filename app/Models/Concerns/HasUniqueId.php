<?php

namespace App\Models\Concerns;

use Illuminate\Support\Str;

trait HasUniqueId
{
    /**
     * Boot the trait.
     */
    protected static function bootHasUniqueId(): void
    {
        static::creating(function ($model) {
            if (empty($model->uuid)) {
                $model->uuid = (string) Str::uuid();
            }
        });
    }

    /**
     * Initialize the trait.
     */
    protected function initializeHasUniqueId(): void
    {
        $this->mergeFillable(['uuid']);
    }

    /**
     * Get the route key for the model.
     */
    public function getRouteKeyName(): string
    {
        return 'uuid';
    }
}
