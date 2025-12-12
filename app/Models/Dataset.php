<?php

namespace App\Models;

use App\Models\Concerns\HasUniqueId;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Dataset extends Model
{
    /** @use HasFactory<\Database\Factories\DatasetFactory> */
    use HasFactory, HasUniqueId;

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'name',
        'description',
        'is_active',
        'owner_id',
        'organisation_id',
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
            'is_active' => 'boolean',
        ];
    }

    /**
     * Get the user who owns the dataset.
     */
    public function owner(): BelongsTo
    {
        return $this->belongsTo(User::class, 'owner_id');
    }

    /**
     * Get the organisation that the dataset belongs to.
     */
    public function organisation(): BelongsTo
    {
        return $this->belongsTo(Organisation::class);
    }

    /**
     * Get the files that belong to the dataset.
     */
    public function files(): BelongsToMany
    {
        return $this->belongsToMany(File::class)
            ->withTimestamps();
    }

    /**
     * Get the conversations that belong to the dataset.
     */
    public function conversations(): HasMany
    {
        return $this->hasMany(Conversation::class);
    }
}
