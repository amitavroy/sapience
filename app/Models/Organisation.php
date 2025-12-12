<?php

namespace App\Models;

use App\Models\Concerns\HasUniqueId;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Organisation extends Model
{
    /** @use HasFactory<\Database\Factories\OrganisationFactory> */
    use HasFactory, HasUniqueId;

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'name',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'uuid' => 'string',
        ];
    }

    /**
     * Get the users that belong to the organisation.
     */
    public function users(): BelongsToMany
    {
        return $this->belongsToMany(User::class)
            ->withPivot('role')
            ->withTimestamps();
    }

    /**
     * Get the datasets that belong to the organisation.
     */
    public function datasets(): HasMany
    {
        return $this->hasMany(Dataset::class);
    }

    /**
     * Get the conversations that belong to the organisation.
     */
    public function conversations(): HasMany
    {
        return $this->hasMany(Conversation::class);
    }
}
